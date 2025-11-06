from adafruit_ads1x15.analog_in import AnalogIn
import adafruit_veml7700

class LightSensor:
    """
    Class for handling light-related sensor functionality including:
    - Light intensity via ADS1115
    """
    def __init__(self, ads_sensor=None, ads_channels=None, I2C=None):
        self.__ads_sensor = ads_sensor
        self.__ads_channels = ads_channels
        self.__light_sensor_resistance = 10000.0 # about 10K ohm
        self.__last_voltage = 0.0
        self.__last_current = 0.0
        self.__last_lux = 0.0        

        # Initialize the light sensor veml7700
        # try:
        #     I2C.try_lock()
        #     try:
        #         self.__veml_sensor = adafruit_veml7700.VEML7700(I2C)
        #     except ValueError as err:
        #         print(f'Sensor Error: {err.args[0]}')
        #         self.__veml_sensor = None
        #         self.__last_veml_lux = 0.0
        #     finally:
        #         I2C.unlock()

        # except IOError as err:
        #     print(f'Sensor Error: {err.args[0]}')
        #     self.__veml_sensor = None
        #     self.__last_veml_lux = 0.0          
        # except RuntimeError as err:
        #     print(f'Sensor Error: {err.args[0]}')
        #     self.__veml_sensor = None
        #     self.__last_veml_lux = 0.0

        
    def set_light_intensity_ads1115_channel(self, ch):
        """Set the ADS1115 channel for light intensity sensor"""
        try:
            self.ads_light = AnalogIn(self.__ads_sensor, self.__ads_channels[ch])
            self.__last_voltage = 0.0
            self.__last_current = 0.0
            self.__last_lux = 0.0
            # self.__ads_sensor.gain = ads.GAIN_ONE # 1x gain
            return True
        except RuntimeError as err:
            print(f'Sensor Error: {err.args[0]}')
            return False

    def __get_lux_raw(self):
        """Get raw light sensor value"""
        try:            
            val = self.ads_light.value
            return val
        except RuntimeError as err:
            print(f'Sensor Error: {err.args[0]}')
            return 0.0

    def __get_lux_voltage(self, ads_reading = 0.0):
        """Get light sensor voltage"""
        try:
            self.__last_voltage = self.ads_light.voltage
            return self.__last_voltage
        except RuntimeError as err:
            print(f'Sensor Error: {err.args[0]}')
            return self.__last_voltage

    def __get_lux_current(self, voltage = 0.0):
        """Get light sensor current"""
        try:       
            self.__last_current = voltage / self.__light_sensor_resistance     
            return self.__last_current
        except RuntimeError as err:
            print(f'Sensor Error: {err.args[0]}')
            return self.__last_current
    
    def get_light_intensity(self):
        """Get light intensity in lux"""
        try:
            self.__last_lux = self.__get_lux_current(self.__get_lux_voltage()) * 1000000.0 * 2.0
            return self.__last_lux
        except RuntimeError as err:
            print(f'Sensor Error: {err.args[0]}')
            return self.__last_lux


    def get_light_intensity_veml(self):
        """Get light intensity in lux using VEML7700"""
        try:
            self.__last_veml_lux = self.__veml_sensor.lux
            return self.__last_veml_lux
        except RuntimeError as err:
            print(f'Sensor Error: {err.args[0]}')
            return self.__last_veml_lux
                        