import time
import threading
import importlib.util
import sys
from utils.utils import _CUSTOM_PRINT_FUNC


def _load_system_gpiod():
    """
    Load the system libgpiod v1 Python bindings (.so) directly via importlib,
    without touching sys.path so the venv packages (cv2, numpy, etc.) are unaffected.
    """
    if '_system_gpiod' in sys.modules:
        return sys.modules['_system_gpiod']
    so_path = '/usr/lib/python3/dist-packages/gpiod.cpython-311-aarch64-linux-gnu.so'
    spec = importlib.util.spec_from_file_location('gpiod', so_path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.modules['_system_gpiod'] = mod
    return mod


_gpiod = _load_system_gpiod()

_SAVE_INTERVAL_SEC = 1   # save water_amount to MongoDB every N seconds


class WaterFlowSensor:
    """
    Water flow sensor (YF-S201) — pulse counting, flow rate, total volume.
    Persists water_amount to MongoDB (system_state collection) every second.
    """
    PULSES_PER_LITRE = 450.0

    def __init__(self, mongo_db_handler=None, state_key="water_amount"):
        self.__mongo      = mongo_db_handler
        self.__state_key  = state_key
        self.__water_flow_running = False
        self.__flow_rate   = 0.0
        self.__water_amount = 0.0
        self.__counter     = 0
        self.__line        = None

        # Load saved total from MongoDB
        if self.__mongo is not None:
            try:
                saved = self.__mongo.get_state(self.__state_key)
                if saved is not None:
                    self.__water_amount = float(saved)
                    _CUSTOM_PRINT_FUNC(f"[WaterFlow] Loaded {self.__state_key}={self.__water_amount:.4f} L from MongoDB")
            except Exception as e:
                _CUSTOM_PRINT_FUNC(f"[WaterFlow] Could not load {self.__state_key} from MongoDB: {e}")

    def set_water_flow_sensor_pin(self, pin: int):
        chip = _gpiod.Chip('/dev/gpiochip4')
        self.__line = chip.get_line(pin)
        self.__line.request(
            consumer="Water_Flow",
            type=_gpiod.LINE_REQ_EV_RISING_EDGE,
            flags=_gpiod.LINE_REQ_FLAG_BIAS_PULL_UP,
        )
        self.__counter = 0
        self.__water_flow_running = True

        threading.Thread(target=self.__pulse_counter,  daemon=True).start()
        threading.Thread(target=self.__calc_flow_rate, daemon=True).start()
        threading.Thread(target=self.__persist_loop,   daemon=True).start()
        _CUSTOM_PRINT_FUNC(f"[WaterFlow] Sensor ready on GPIO {pin}")

    def __pulse_counter(self):
        while self.__water_flow_running:
            if self.__line.event_wait(sec=1):
                event = self.__line.event_read()
                if event.type == _gpiod.LineEvent.RISING_EDGE:
                    self.__counter += 1

    def __calc_flow_rate(self):
        while self.__water_flow_running:
            time.sleep(1)
            count = self.__counter
            self.__counter = 0
            # YF-S201: F(Hz) = 7.5 * Q(L/min)  →  Q = count / 7.5
            self.__flow_rate = count / 7.5
            self.__water_amount += self.__flow_rate / 60.0  # L/min → L per second

    def __persist_loop(self):
        """Save water_amount to MongoDB every _SAVE_INTERVAL_SEC seconds."""
        while self.__water_flow_running:
            time.sleep(_SAVE_INTERVAL_SEC)
            if self.__mongo is not None:
                try:
                    self.__mongo.upsert_state(self.__state_key, round(self.__water_amount, 4))
                except Exception as e:
                    _CUSTOM_PRINT_FUNC(f"[WaterFlow] Could not save {self.__state_key}: {e}")

    def get_water_flow_rate(self) -> float:
        return self.__flow_rate

    def get_total_water_amount(self) -> float:
        return self.__water_amount

    def stop(self):
        self.__water_flow_running = False
        if self.__mongo is not None:
            self.__mongo.upsert_state(self.__state_key, round(self.__water_amount, 4))
        if self.__line:
            try:
                self.__line.release()
            except Exception:
                pass

    def reset_water_amount(self):
        self.__water_amount = 0.0
        if self.__mongo is not None:
            self.__mongo.upsert_state(self.__state_key, 0.0)
        _CUSTOM_PRINT_FUNC(f"[WaterFlow] {self.__state_key} reset to 0.")
