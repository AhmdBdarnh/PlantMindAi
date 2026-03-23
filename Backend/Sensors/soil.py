import serial
import struct
import numpy as np
from adafruit_ads1x15.analog_in import AnalogIn

from utils.utils import _CUSTOM_PRINT_FUNC


class SoilSensor:
    """
    Class for handling soil-related sensor functionality including:
    - Soil moisture, pH, EC, humidity, and temperature via UART
    - Soil moisture via ADS1115
    """
    def __init__(self, ads_sensor=None, ads_channels=None):
        self.__ads_sensor = ads_sensor
        self.__ads_channels = ads_channels
        
        # moisture sensor calibration values
        self.__MOISTURE_SENSOR_VERY_DRY_VAL = 18000
        self.__MOISTURE_SENSOR_VERY_WET_VAL = 7000
        
    def set_soil_sensor_pins(self):
        """Set up the UART configuration for soil sensors"""
        # set the uart configurations
        self.__moisture_uart = serial.Serial("/dev/ttyAMA0", baudrate=4800, bytesize=8, parity='N', stopbits=1, timeout=1)

    def __send_modbus_request(self):
        """Send modbus request to soil sensor"""
        modbus_req = [0x01, 0x03, 0x00, 0x00, 0x00, 0x04, 0x44, 0x09]
        self.__moisture_uart.write(modbus_req)
    
    def __get_modbus_response(self):
        """Get modbus response from soil sensor"""
        # 01 e1 00 33 5b 05 01 03 08 03 87
        response = self.__moisture_uart.read(11) # expected 11 bytes to be received        
        self.__moisture_uart.reset_input_buffer()
        # _CUSTOM_PRINT_FUNC(f'soil response: {response.hex()}')
        return response if len(response) >= 11 else None

    def get_ph(self):
        """Get soil pH value"""
        try:        
            self.__send_modbus_request()
            resp = self.__get_modbus_response()

            if resp == None:
                return 0.0

            if resp[1] != 0x03:
                _CUSTOM_PRINT_FUNC("Invalid response for Soil PH request!")
                return 0.0
            
            ph_val = struct.unpack(">H", resp[9:11])[0] / 10.0

            return ph_val
        except RuntimeError as err:
            _CUSTOM_PRINT_FUNC(f"Sensor Error: {err.args[0]}")
            return 0.0

    def get_ec(self):
        """Get soil EC (Electrical Conductivity) value"""
        try:            
            self.__send_modbus_request()
            resp = self.__get_modbus_response()

            if resp == None:
                return 0.0

            if resp[1] != 0x03:
                _CUSTOM_PRINT_FUNC("Invalid response for Soil EC request!")
                return 0.0
            
            ec_val = struct.unpack(">H", resp[7:9])[0]

            return ec_val
        except RuntimeError as err:
            _CUSTOM_PRINT_FUNC(f"Sensor Error: {err.args[0]}")
            return 0.0

    def get_soil_humidity(self):
        """Get soil humidity value"""
        try:
            self.__send_modbus_request()
            resp = self.__get_modbus_response()

            if resp == None:
                return 0.0

            if resp[1] != 0x03:
                _CUSTOM_PRINT_FUNC("Invalid response for Soil Humidity request!")
                return 0.0
            
            humi_val = struct.unpack(">H", resp[3:5])[0] / 10.0

            return humi_val
        except RuntimeError as err:
            _CUSTOM_PRINT_FUNC(f'Sensor Error: {err.args[0]}')
            return 0.0
    
    def get_soil_temperature(self):
        """Get soil temperature value"""
        try:            
            self.__send_modbus_request()
            resp = self.__get_modbus_response()

            if resp == None:
                return 0.0
            
            if resp[1] != 0x03:
                _CUSTOM_PRINT_FUNC("Invalid response for Soil Temperature request!")
                return 0.0
            
            temp_val = struct.unpack(">H", resp[5:7])[0] / 10.0

            return temp_val
        except RuntimeError as err:
            _CUSTOM_PRINT_FUNC(f'Sensor Error: {err.args[0]}')
            return 0.0

    def get_soil_values(self):
        """
        Get all soil values from the sensor.
        Returns ph_val, ec_val, humi_val, temp_val respectively.
        """
        try:
            self.__send_modbus_request()
            resp = self.__get_modbus_response()

            if resp == None:
                return 0.0, 0.0, 0.0, 0.0

            if resp[1] != 0x03:
                _CUSTOM_PRINT_FUNC("Invalid response for Soil Values request!")
                return 0.0, 0.0, 0.0, 0.0
            
            ph_val = struct.unpack(">H", resp[9:11])[0] / 10.0
            ec_val = struct.unpack(">H", resp[7:9])[0]
            humi_val = struct.unpack(">H", resp[3:5])[0] / 10.0
            temp_val = struct.unpack(">H", resp[5:7])[0] / 10.0

            return ph_val, ec_val, humi_val, temp_val
        except RuntimeError as err:
            _CUSTOM_PRINT_FUNC(f'Sensor Error: {err.args[0]}')
            return 0.0, 0.0, 0.0, 0.0

    # ADS1115 soil moisture functions
    def set_soil_moisture_ads1115_channel(self, ch):
        """Set the ADS1115 channel for soil moisture sensor"""
        self.__ads_moisture = AnalogIn(self.__ads_sensor, self.__ads_channels[ch])

    def calibrate_soil_moisture_ads1115(self, dry_value, wet_value):
        """Calibrate soil moisture sensor with dry and wet values"""
        self.__MOISTURE_SENSOR_VERY_DRY_VAL = dry_value
        self.__MOISTURE_SENSOR_VERY_WET_VAL = wet_value

    def get_soil_moisture_ads1115(self):
        """Get soil moisture percentage from ADS1115"""
        try:
            moisture_raw = self.__ads_moisture.value
            moisture_perc = np.interp(moisture_raw, [self.__MOISTURE_SENSOR_VERY_WET_VAL, self.__MOISTURE_SENSOR_VERY_DRY_VAL], [100, 0])
            return moisture_perc
        except RuntimeError as err:
            _CUSTOM_PRINT_FUNC(f'Sensor Error: {err.args[0]}')
            return 0.0
