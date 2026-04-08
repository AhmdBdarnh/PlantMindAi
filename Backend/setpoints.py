import datetime
import time
import threading
from utils.utils import _CUSTOM_PRINT_FUNC


class GH_Setpoints:
    def __init__(self, mqtt_handler, mongo_db_handler, actuator_handler=None):
        # Research-based defaults for lettuce (PlantMindAI_Lettuce_Research_Summary.pdf)
        self.__temperature_setpoint      = 23.0
        self.__humidity_setpoint         = 70.0
        self.__light_setpoint            = 10.0
        self.__soil_ph_setpoint          = 5.8
        self.__soil_ec_setpoint          = 150.0
        self.__soil_temp_setpoint        = 25.0
        self.__soil_humidity_setpoint    = 70.0
        self.__soil_humidity_hysteresis  = 20.0
        self.__water_flow_setpoint       = 2.0
        self.operation_mode              = "autonomous"

        self.__control_threads_events = {
            "temperature": threading.Event(),
            "light":       threading.Event(),
            "moisture":    threading.Event(),
        }

        self.__mqtt_handler    = mqtt_handler
        self.__mongo_db_handler = mongo_db_handler
        self.__actuator_handler = actuator_handler

        # Load latest values from MongoDB — overrides defaults if saved previously
        self._load_from_mongo("temperature",    lambda v: setattr(self, '_GH_Setpoints__temperature_setpoint',     float(v)))
        self._load_from_mongo("humidity",       lambda v: setattr(self, '_GH_Setpoints__humidity_setpoint',        float(v)))
        self._load_from_mongo("light_intensity",lambda v: setattr(self, '_GH_Setpoints__light_setpoint',           float(v)))
        self._load_from_mongo("soil_ph",        lambda v: setattr(self, '_GH_Setpoints__soil_ph_setpoint',         float(v)))
        self._load_from_mongo("soil_ec",        lambda v: setattr(self, '_GH_Setpoints__soil_ec_setpoint',         float(v)))
        self._load_from_mongo("soil_temp",      lambda v: setattr(self, '_GH_Setpoints__soil_temp_setpoint',       float(v)))
        self._load_from_mongo("soil_moisture",  lambda v: setattr(self, '_GH_Setpoints__soil_humidity_setpoint',   float(v)))
        self._load_from_mongo("soil_hysteresis",lambda v: setattr(self, '_GH_Setpoints__soil_humidity_hysteresis', float(v)))
        self._load_from_mongo("water_flow",     lambda v: setattr(self, '_GH_Setpoints__water_flow_setpoint',      float(v)))
        self._load_from_mongo("operation_mode", lambda v: setattr(self, 'operation_mode',                          str(v)))

        _CUSTOM_PRINT_FUNC(f"[Setpoints] Loaded: {self.get_all_setpoints()}")

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _load_from_mongo(self, type_key: str, apply_fn) -> None:
        """Load the latest saved value for type_key and apply it."""
        try:
            doc = self.__mongo_db_handler.get_latest_doc_where("setpoints", {"type": type_key})
            if doc is not None:
                apply_fn(doc["message"])
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[Setpoints] Could not load '{type_key}' from MongoDB: {e}")

    def _save(self, type_key: str, value) -> None:
        """Persist a setpoint value to MongoDB."""
        try:
            self.__mongo_db_handler._MongoDBHandler__db['setpoints'].insert_one({
                'type':      type_key,
                'message':   str(value),
                'timestamp': datetime.datetime.now(),
            })
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[Setpoints] Could not save '{type_key}' to MongoDB: {e}")

    # ── Operation mode ─────────────────────────────────────────────────────────

    def set_operation_mode(self, mode: str) -> None:
        if mode not in ["manual", "autonomous"]:
            raise ValueError("Invalid operation mode. Choose 'manual' or 'autonomous'.")
        self.operation_mode = mode
        self._save("operation_mode", mode)
        _CUSTOM_PRINT_FUNC(f"[Setpoints] Operation mode → {mode}")

        if mode == "manual":
            for event in self.__control_threads_events.values():
                if isinstance(event, threading.Event):
                    event.clear()
            time.sleep(0.3)
            self.__actuator_handler.stop_all_actuators()

        if mode == "autonomous":
            self.__actuator_handler.stop_all_actuators()
            for event in self.__control_threads_events.values():
                if isinstance(event, threading.Event):
                    event.set()

    def get_operation_mode(self) -> str:
        return self.operation_mode

    def set_control_thread_event(self, name: str, event: threading.Event) -> None:
        if name not in self.__control_threads_events:
            raise ValueError(f"Invalid control thread name: {name}")
        self.__control_threads_events[name] = event

    # ── Setters (each auto-saves to MongoDB) ───────────────────────────────────

    def set_temperature_setpoint(self, value: float) -> None:
        self.__temperature_setpoint = float(value)
        self._save("temperature", value)
        _CUSTOM_PRINT_FUNC(f"[Setpoints] Temperature → {value} °C")

    def set_humidity_setpoint(self, value: float) -> None:
        self.__humidity_setpoint = float(value)
        self._save("humidity", value)
        _CUSTOM_PRINT_FUNC(f"[Setpoints] Humidity → {value} %")

    def set_light_setpoint(self, value: float) -> None:
        self.__light_setpoint = float(value)
        self._save("light_intensity", value)
        _CUSTOM_PRINT_FUNC(f"[Setpoints] Light → {value}")

    def set_soil_ph_setpoint(self, value: float) -> None:
        self.__soil_ph_setpoint = float(value)
        self._save("soil_ph", value)
        _CUSTOM_PRINT_FUNC(f"[Setpoints] Soil pH → {value}")

    def set_soil_ec_setpoint(self, value: float) -> None:
        self.__soil_ec_setpoint = float(value)
        self._save("soil_ec", value)
        _CUSTOM_PRINT_FUNC(f"[Setpoints] Soil EC → {value} mS/cm")

    def set_soil_temp_setpoint(self, value: float) -> None:
        self.__soil_temp_setpoint = float(value)
        self._save("soil_temp", value)
        _CUSTOM_PRINT_FUNC(f"[Setpoints] Soil temp → {value} °C")

    def set_soil_humidity_setpoint(self, value: float) -> None:
        self.__soil_humidity_setpoint = float(value)
        self._save("soil_moisture", value)
        _CUSTOM_PRINT_FUNC(f"[Setpoints] Soil moisture → {value} %")

    def set_soil_humidity_hysteresis(self, value: float) -> None:
        self.__soil_humidity_hysteresis = float(value)
        self._save("soil_hysteresis", value)
        _CUSTOM_PRINT_FUNC(f"[Setpoints] Soil hysteresis → {value} %")

    def set_water_flow_setpoint(self, value: float) -> None:
        self.__water_flow_setpoint = float(value)
        self._save("water_flow", value)
        _CUSTOM_PRINT_FUNC(f"[Setpoints] Water flow → {value} L/h")

    # ── Getters ────────────────────────────────────────────────────────────────

    def get_temperature_setpoint(self) -> float:
        return self.__temperature_setpoint

    def get_humidity_setpoint(self) -> float:
        return self.__humidity_setpoint

    def get_light_setpoint(self) -> float:
        return self.__light_setpoint

    def get_soil_ph_setpoint(self) -> float:
        return self.__soil_ph_setpoint

    def get_soil_ec_setpoint(self) -> float:
        return self.__soil_ec_setpoint

    def get_soil_temp_setpoint(self) -> float:
        return self.__soil_temp_setpoint

    def get_soil_humidity_setpoint(self) -> float:
        return self.__soil_humidity_setpoint

    def get_soil_humidity_hysteresis(self) -> float:
        return self.__soil_humidity_hysteresis

    def get_water_flow_setpoint(self) -> float:
        return self.__water_flow_setpoint

    def get_all_setpoints(self) -> dict:
        return {
            "temperature":      self.__temperature_setpoint,
            "humidity":         self.__humidity_setpoint,
            "light":            self.__light_setpoint,
            "soil_ph":          self.__soil_ph_setpoint,
            "soil_ec":          self.__soil_ec_setpoint,
            "soil_temp":        self.__soil_temp_setpoint,
            "soil_moisture":    self.__soil_humidity_setpoint,
            "soil_hysteresis":  self.__soil_humidity_hysteresis,
            "water_flow":       self.__water_flow_setpoint,
            "operation_mode":   self.operation_mode,
        }
