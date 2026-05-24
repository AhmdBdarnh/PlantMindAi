import datetime
import time
import threading
from utils.utils import _CUSTOM_PRINT_FUNC


class GH_Setpoints:
    def __init__(self, mqtt_handler, mongo_db_handler, actuator_handler=None):
        # Research-based defaults for lettuce (PlantMindAI_Lettuce_Research_Summary.pdf)
        self.__temperature_setpoint      = 21.0
        self.__humidity_setpoint         = 68.0
        self.__light_setpoint            = 600.0
        self.__soil_ph_setpoint          = 6.3
        self.__soil_ec_setpoint          = 1300.0
        self.__soil_temp_setpoint        = 21.0
        self.__soil_humidity_setpoint    = 70.0
        self.__soil_humidity_hysteresis  = 10.0
        self.__water_flow_setpoint       = 2.0
        self.__fertilizer_flow_setpoint  = 0.5
        self.operation_mode              = "autonomous"

        self.__control_threads_events = {
            "temperature": threading.Event(),
            "light":       threading.Event(),
            "moisture":    threading.Event(),
            "fertilizer":  threading.Event(),
        }

        self.__mqtt_handler    = mqtt_handler
        self.__mongo_db_handler = mongo_db_handler
        self.__actuator_handler = actuator_handler

        # Load the single setpoints document from MongoDB — overrides defaults if saved previously
        self._load_all_from_mongo()
        _CUSTOM_PRINT_FUNC(f"[Setpoints] Loaded: {self.get_all_setpoints()}")

    # ── MongoDB helpers ────────────────────────────────────────────────────────

    def _collection(self):
        return self.__mongo_db_handler._MongoDBHandler__db['setpoints']

    def _load_all_from_mongo(self) -> None:
        """Load all setpoints from the single MongoDB document."""
        try:
            doc = self._collection().find_one({'_id': 'greenhouse_setpoints'})
            if doc is None:
                _CUSTOM_PRINT_FUNC("[Setpoints] No saved setpoints found — using code defaults.")
                return
            self.__temperature_setpoint     = float(doc.get('temperature',     self.__temperature_setpoint))
            self.__humidity_setpoint        = float(doc.get('humidity',        self.__humidity_setpoint))
            self.__light_setpoint           = float(doc.get('light',           self.__light_setpoint))
            self.__soil_ph_setpoint         = float(doc.get('soil_ph',         self.__soil_ph_setpoint))
            self.__soil_ec_setpoint         = float(doc.get('soil_ec',         self.__soil_ec_setpoint))
            self.__soil_temp_setpoint       = float(doc.get('soil_temp',       self.__soil_temp_setpoint))
            self.__soil_humidity_setpoint   = float(doc.get('soil_moisture',   self.__soil_humidity_setpoint))
            self.__soil_humidity_hysteresis = float(doc.get('soil_hysteresis', self.__soil_humidity_hysteresis))
            self.__water_flow_setpoint      = float(doc.get('water_flow',      self.__water_flow_setpoint))
            self.__fertilizer_flow_setpoint = float(doc.get('fertilizer_flow', self.__fertilizer_flow_setpoint))
            # Always start in manual mode regardless of what was saved
            self.operation_mode             = 'manual'
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[Setpoints] Could not load from MongoDB: {e}")

    def _save(self, field: str, value) -> None:
        """Update one field inside the single setpoints document."""
        try:
            self._collection().update_one(
                {'_id': 'greenhouse_setpoints'},
                {'$set': {field: value, 'timestamp': datetime.datetime.now()}},
                upsert=True,
            )
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[Setpoints] Could not save '{field}' to MongoDB: {e}")

    def save_all_setpoints(self) -> None:
        """Replace the single setpoints document with all current values."""
        try:
            self._collection().replace_one(
                {'_id': 'greenhouse_setpoints'},
                {
                    '_id':            'greenhouse_setpoints',
                    'temperature':    self.__temperature_setpoint,
                    'humidity':       self.__humidity_setpoint,
                    'light':          self.__light_setpoint,
                    'soil_ph':        self.__soil_ph_setpoint,
                    'soil_ec':        self.__soil_ec_setpoint,
                    'soil_temp':      self.__soil_temp_setpoint,
                    'soil_moisture':  self.__soil_humidity_setpoint,
                    'soil_hysteresis':self.__soil_humidity_hysteresis,
                    'water_flow':     self.__water_flow_setpoint,
                    'fertilizer_flow':self.__fertilizer_flow_setpoint,
                    'operation_mode': self.operation_mode,
                    'timestamp':      datetime.datetime.now(),
                },
                upsert=True,
            )
            _CUSTOM_PRINT_FUNC(f"[Setpoints] All setpoints saved to MongoDB: {self.get_all_setpoints()}")
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[Setpoints] Could not save all setpoints: {e}")

    # ── Operation mode ─────────────────────────────────────────────────────────

    def set_operation_mode(self, mode: str) -> None:
        if mode not in ["manual", "autonomous"]:
            raise ValueError("Invalid operation mode. Choose 'manual' or 'autonomous'.")
        self.operation_mode = mode
        self._save("operation_mode", str(mode))
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
        self._save("temperature", float(value))
        _CUSTOM_PRINT_FUNC(f"[Setpoints] Temperature → {value} °C")

    def set_humidity_setpoint(self, value: float) -> None:
        self.__humidity_setpoint = float(value)
        self._save("humidity", float(value))
        _CUSTOM_PRINT_FUNC(f"[Setpoints] Humidity → {value} %")

    def set_light_setpoint(self, value: float) -> None:
        self.__light_setpoint = float(value)
        self._save("light", float(value))
        _CUSTOM_PRINT_FUNC(f"[Setpoints] Light → {value}")

    def set_soil_ph_setpoint(self, value: float) -> None:
        self.__soil_ph_setpoint = float(value)
        self._save("soil_ph", float(value))
        _CUSTOM_PRINT_FUNC(f"[Setpoints] Soil pH → {value}")

    def set_soil_ec_setpoint(self, value: float) -> None:
        self.__soil_ec_setpoint = float(value)
        self._save("soil_ec", float(value))
        _CUSTOM_PRINT_FUNC(f"[Setpoints] Soil EC → {value} µS/cm")

    def set_soil_temp_setpoint(self, value: float) -> None:
        self.__soil_temp_setpoint = float(value)
        self._save("soil_temp", float(value))
        _CUSTOM_PRINT_FUNC(f"[Setpoints] Soil temp → {value} °C")

    def set_soil_humidity_setpoint(self, value: float) -> None:
        self.__soil_humidity_setpoint = float(value)
        self._save("soil_moisture", float(value))
        _CUSTOM_PRINT_FUNC(f"[Setpoints] Soil moisture → {value} %")

    def set_soil_humidity_hysteresis(self, value: float) -> None:
        self.__soil_humidity_hysteresis = float(value)
        self._save("soil_hysteresis", float(value))
        _CUSTOM_PRINT_FUNC(f"[Setpoints] Soil hysteresis → {value} %")

    def set_water_flow_setpoint(self, value: float) -> None:
        self.__water_flow_setpoint = float(value)
        self._save("water_flow", float(value))
        _CUSTOM_PRINT_FUNC(f"[Setpoints] Water flow → {value} L/h")

    def set_fertilizer_flow_setpoint(self, value: float) -> None:
        self.__fertilizer_flow_setpoint = float(value)
        self._save("fertilizer_flow", float(value))
        _CUSTOM_PRINT_FUNC(f"[Setpoints] Fertilizer flow → {value} L/h")

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

    def get_fertilizer_flow_setpoint(self) -> float:
        return self.__fertilizer_flow_setpoint

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
            "fertilizer_flow":  self.__fertilizer_flow_setpoint,
            "operation_mode":   self.operation_mode,
        }
