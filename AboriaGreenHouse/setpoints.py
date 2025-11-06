import numpy as np
import threading
from utils.utils import _CUSTOM_PRINT_FUNC

class GH_Setpoints:
    def __init__(self, mqtt_handler, mongo_db_handler, actuator_handler=None):        
        self.__temperature_setpoint = 25.0
        self.__humidity_setpoint = 60.0
        self.__light_setpoint = 10.0 # 0 - 18 lux
        self.__soil_ph_setpoint = 7.0
        self.__soil_ec_setpoint = 150.0
        self.__soil_temp_setpoint = 25.0
        self.__soil_humidity_setpoint = 80.0
        self.__water_flow_setpoint = 2 # L/h

        self.operation_mode = "autonomous"  # Default operation mode (can be "manual" or "autonomous")
        
        self.__control_threads_events = {
            "temperature": threading.Event(),
            "light": threading.Event(),
            "moisture": threading.Event() 
        }        

        self.__mqtt_handler = mqtt_handler
        self.__mongo_db_handler = mongo_db_handler
        self.__actuator_handler = actuator_handler

        self.__soil_humidity_hysteresis = 20.0  # Default hysteresis value for soil humidity control

        temp = self.__mongo_db_handler.get_latest_doc_where("setpoints", {"type": "temperature"})
        if temp is not None:
            self.__temperature_setpoint = int(temp["message"])

        hum = self.__mongo_db_handler.get_latest_doc_where("setpoints", {"type": "humidity"})
        if hum is not None:
            self.__humidity_setpoint = int(hum["message"])

        light = self.__mongo_db_handler.get_latest_doc_where("setpoints", {"type": "light_intensity"})
        if light is not None:
            self.__light_setpoint = int(light["message"])

        soil_ph = self.__mongo_db_handler.get_latest_doc_where("setpoints", {"type": "soil_ph"})
        if soil_ph is not None:
            self.__soil_ph_setpoint = int(soil_ph["message"])

        soil_ec = self.__mongo_db_handler.get_latest_doc_where("setpoints", {"type": "soil_ec"})
        if soil_ec is not None:
            self.__soil_ec_setpoint = int(soil_ec["message"])

        soil_temp = self.__mongo_db_handler.get_latest_doc_where("setpoints", {"type": "soil_temp"})
        if soil_temp is not None:
            self.__soil_temp_setpoint = int(soil_temp["message"])

        soil_humidity = self.__mongo_db_handler.get_latest_doc_where("setpoints", {"type": "soil_moisture"})
        if soil_humidity is not None:
            self.__soil_humidity_setpoint = int(soil_humidity["message"])

        water_flow = self.__mongo_db_handler.get_latest_doc_where("setpoints", {"type": "water_flow"})
        if water_flow is not None:
            self.__water_flow_setpoint = int(water_flow["message"])

        operation_mode = self.__mongo_db_handler.get_latest_doc_where("setpoints", {"type": "operation_mode"})
        if operation_mode is not None:
            self.operation_mode = operation_mode["message"]

    def set_operation_mode(self, mode: str) -> None:
        if mode not in ["manual", "autonomous"]:
            raise ValueError("Invalid operation mode. Choose 'manual' or 'autonomous'.")
        _CUSTOM_PRINT_FUNC(f"Setting operation mode to {mode}")
        self.operation_mode = mode

        if mode == "manual":
            # Stop all control threads if they are running
            for control_thread_event in self.__control_threads_events.values():
                if control_thread_event is not None:
                    # pause the thread
                    control_thread_event.clear()
            
            self.__actuator_handler.stop_all_actuators()
            
        if mode == "autonomous":
            self.__actuator_handler.stop_all_actuators()
            # Resume all control threads if they are paused
            for control_thread_event in self.__control_threads_events.values():
                if control_thread_event is not None:
                    # resume the thread
                    control_thread_event.set()

        _CUSTOM_PRINT_FUNC(f'initial setpoints: {self.get_all_setpoints()}')
                
    def get_operation_mode(self) -> str:
        """Get the current operation mode."""
        return self.operation_mode
    
    def set_control_thread_event(self, control_thread_name: str, event: threading.Event) -> None:
        if control_thread_name not in self.__control_threads_events:
            raise ValueError(f"Invalid control thread name: {control_thread_name}")
        _CUSTOM_PRINT_FUNC(f"Setting control thread event for {control_thread_name}")
        self.__control_threads_events[control_thread_name] = event

    def set_temperature_setpoint(self, temperature_setpoint: float) -> None:
        _CUSTOM_PRINT_FUNC(f"Setting temperature setpoint to {temperature_setpoint} C")
        self.__temperature_setpoint = temperature_setpoint

    def get_soil_humidity_hysteresis(self) -> float:
        """Get the hysteresis value for soil humidity control."""
        return  self.__soil_humidity_hysteresis
    
    def set_soil_humidity_hysteresis(self, hysteresis: float) -> None:
        """Set the hysteresis value for soil humidity control."""
        _CUSTOM_PRINT_FUNC(f"Setting soil humidity hysteresis to {hysteresis} %")
        self.__soil_humidity_hysteresis = hysteresis

    def get_temperature_setpoint(self) -> float:
        return self.__temperature_setpoint
    
    def set_humidity_setpoint(self, humidity_setpoint: float) -> None:
        _CUSTOM_PRINT_FUNC(f"Setting humidity setpoint to {humidity_setpoint} %")
        self.__humidity_setpoint = humidity_setpoint

    def get_humidity_setpoint(self) -> float:
        return self.__humidity_setpoint
    
    def set_light_setpoint(self, light_setpoint: float) -> None:
        _CUSTOM_PRINT_FUNC(f"Setting light setpoint to {light_setpoint} lux")
        self.__light_setpoint = light_setpoint

    def get_light_setpoint(self) -> float:
        return self.__light_setpoint
    
    def set_soil_ph_setpoint(self, soil_ph_setpoint: float) -> None:
        _CUSTOM_PRINT_FUNC(f"Setting soil pH setpoint to {soil_ph_setpoint}")
        self.__soil_ph_setpoint = soil_ph_setpoint

    def get_soil_ph_setpoint(self) -> float:
        return self.__soil_ph_setpoint
    
    def set_soil_ec_setpoint(self, soil_ec_setpoint: float) -> None:
        _CUSTOM_PRINT_FUNC(f"Setting soil EC setpoint to {soil_ec_setpoint} mS/cm")
        self.__soil_ec_setpoint = soil_ec_setpoint

    def get_soil_ec_setpoint(self) -> float:
        return self.__soil_ec_setpoint
    
    def set_soil_temp_setpoint(self, soil_temp_setpoint: float) -> None:
        _CUSTOM_PRINT_FUNC(f"Setting soil temperature setpoint to {soil_temp_setpoint} C")
        self.__soil_temp_setpoint = soil_temp_setpoint

    def get_soil_temp_setpoint(self) -> float:
        return self.__soil_temp_setpoint
    
    def set_soil_humidity_setpoint(self, soil_humidity_setpoint: float) -> None:
        _CUSTOM_PRINT_FUNC(f"Setting soil humidity setpoint to {soil_humidity_setpoint} %")
        self.__soil_humidity_setpoint = soil_humidity_setpoint

    def get_soil_humidity_setpoint(self) -> float:
        return self.__soil_humidity_setpoint
    
    def set_water_flow_setpoint(self, water_flow_setpoint: float) -> None:
        _CUSTOM_PRINT_FUNC(f"Setting water flow setpoint to {water_flow_setpoint} L/h")
        self.__water_flow_setpoint = water_flow_setpoint

    def get_water_flow_setpoint(self) -> float:
        return self.__water_flow_setpoint

    def get_all_setpoints(self) -> dict:
        return {
            "temperature_setpoint": self.__temperature_setpoint,
            "humidity_setpoint": self.__humidity_setpoint,
            "light_setpoint": self.__light_setpoint,
            "soil_ph_setpoint": self.__soil_ph_setpoint,
            "soil_ec_setpoint": self.__soil_ec_setpoint,
            "soil_temp_setpoint": self.__soil_temp_setpoint,
            "soil_humidity_setpoint": self.__soil_humidity_setpoint,
            "water_flow_setpoint": self.__water_flow_setpoint,
        }
