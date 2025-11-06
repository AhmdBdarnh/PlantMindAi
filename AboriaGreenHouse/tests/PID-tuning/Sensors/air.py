import adafruit_dht

class AirSensor:
    """
    Class for handling air-related sensor functionality including:
    - Temperature and humidity via DHT22 sensor
    """
    def __init__(self):
        self.__prev_temp = 0.0
        self.__prev_temp_F = 0.0
        self.__prev_hum = 0.0
        
    def set_dht22_pin(self, pin):
        """Set up the DHT22 sensor with the specified pin"""
        self.__dht22 = adafruit_dht.DHT22(pin)
        self.__prev_temp = 0.0
        self.__prev_temp_F = 0.0
        self.__prev_hum = 0.0

    def get_air_temperature_C(self):
        """Get air temperature in Celsius"""
        try:
            tempC = self.__dht22.temperature
            if tempC == None:
                return self.__prev_temp
            
            self.__prev_temp = tempC
            return tempC
        except RuntimeError as err:
            print(f"Sensors: {err.args[0]}")
            return self.__prev_temp
    
    def get_air_temperature_F(self):
        """Get air temperature in Fahrenheit"""
        try:
            tempC = self.get_air_temperature_C()
            if tempC == None:
                return self.__prev_temp_F
            
            self.__prev_temp_F = tempC * (9.0/5.0) + 32.0
            return self.__prev_temp_F
        except RuntimeError as err:
            print(f"Sensors: {err.args[0]}")
            return self.__prev_temp_F

    def get_air_humidity(self):
        """Get air humidity percentage"""
        try:
            hum = self.__dht22.humidity
            if hum == None:
                return self.__prev_hum

            self.__prev_hum = hum
            return hum
        except RuntimeError as err:
            print(f"Sensors: {err.args[0]}")
            return self.__prev_hum
