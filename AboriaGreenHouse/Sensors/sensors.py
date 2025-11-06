import time
import threading
import board
import busio
import gpiod
import adafruit_ads1x15.ads1115 as ads
from datetime import timedelta

# Import the separated sensor drivers
from .soil import SoilSensor
from .air import AirSensor
from .electricity import ElectricitySensor
from .light import LightSensor
from .water import WaterFlowSensor
from utils.utils import _CUSTOM_PRINT_FUNC

class GH_Sensors:
    """
    Main class for greenhouse sensors that coordinates all sensor types:
    - Soil sensors (moisture, pH, EC, humidity, temperature)
    - Air sensors (temperature, humidity)
    - Electricity sensors (voltage, current, power, energy, frequency, power factor)
    - Light sensors (intensity)
    - Water flow sensor
    """
    def __init__(self, general_i2c):
        self.__general_i2c = general_i2c        
        self.__Vref = 5.0 # ads source voltage
        self.__ads_resolution = 65535.0 # maximum resolution for ads sensor (16-bit)
        
        # ads channels
        self.__ads_channels = [ads.P0, ads.P1, ads.P2, ads.P3]
        self.__ads_sensor = ads.ADS1115(self.__general_i2c)
        
        # gpiod
        self.chip = gpiod.chip('gpiochip4')
        
        # Initialize sensor drivers
        self.soil_sensor = SoilSensor(self.__ads_sensor, self.__ads_channels)
        self.air_sensor = AirSensor()
        self.electricity_sensor = ElectricitySensor()
        self.light_sensor = LightSensor(ads_sensor=self.__ads_sensor, ads_channels=self.__ads_channels, I2C=self.__general_i2c)        
        self.water_flow_sensor = WaterFlowSensor()

    def set_water_flow_sensor_pin(self, pin):
        """Set up the water flow sensor with the specified pin"""
        self.water_flow_sensor.set_water_flow_sensor_pin(pin)

    def get_water_flow_rate(self):
        """Get water flow rate in liters per minute"""
        return self.water_flow_sensor.get_water_flow_rate()

    def get_total_water_amount(self):
        """Get total water amount in liters"""
        return self.water_flow_sensor.get_total_water_amount()

    def reset_water_amount(self):
        """Reset the total water amount to zero"""
        return self.water_flow_sensor.reset_water_amount()

    # Soil sensor functions - delegated to soil_sensor
    def set_soil_sensor_pins(self):
        """Set up the soil sensor pins"""
        self.soil_sensor.set_soil_sensor_pins()

    def get_ph(self):
        """Get soil pH value"""
        return self.soil_sensor.get_ph()

    def get_ec(self):
        """Get soil EC (Electrical Conductivity) value"""
        return self.soil_sensor.get_ec()

    def get_soil_humidity(self):
        """Get soil humidity value"""
        return self.soil_sensor.get_soil_humidity()
    
    def get_soil_temperature(self):
        """Get soil temperature value"""
        return self.soil_sensor.get_soil_temperature()

    def get_soil_values(self):
        """
        Get all soil values from the sensor.
        Returns ph_val, ec_val, humi_val, temp_val respectively.
        """
        return self.soil_sensor.get_soil_values()

    def set_soil_moisture_ads1115_channel(self, ch):
        """Set the ADS1115 channel for soil moisture sensor"""
        self.soil_sensor.set_soil_moisture_ads1115_channel(ch)

    def calibrate_soil_moisture_ads1115(self, dry_value, wet_value):
        """Calibrate soil moisture sensor with dry and wet values"""
        self.soil_sensor.calibrate_soil_moisture_ads1115(dry_value, wet_value)

    def get_soil_moisture_ads1115(self):
        """Get soil moisture percentage from ADS1115"""
        return self.soil_sensor.get_soil_moisture_ads1115()

    # Air sensor functions - delegated to air_sensor
    def set_dht22_pin(self, pin):
        """Set up the DHT22 sensor with the specified pin"""
        self.air_sensor.set_dht22_pin(pin)

    def get_air_temperature_C(self):
        """Get air temperature in Celsius"""
        return self.air_sensor.get_air_temperature_C()
    
    def get_air_temperature_F(self):
        """Get air temperature in Fahrenheit"""
        return self.air_sensor.get_air_temperature_F()

    def get_air_humidity(self):
        """Get air humidity percentage"""
        return self.air_sensor.get_air_humidity()

    # Light sensor functions - delegated to light_sensor
    def set_light_intensity_ads1115_channel(self, ch):
        """Set the ADS1115 channel for light intensity sensor"""
        return self.light_sensor.set_light_intensity_ads1115_channel(ch)

    def get_light_intensity(self):
        """Get light intensity in lux"""
        return self.light_sensor.get_light_intensity()

    def get_light_intensity_veml(self):
        # """Get light intensity in lux using VEML sensor"""
        # self.__general_i2c.try_lock()
        # try:            
        #     return self.light_sensor.get_light_intensity_veml()
        # except RuntimeError as err:
        #     _CUSTOM_PRINT_FUNC(f'Sensor Error: {err.args[0]}')            
        #     return 0
        # finally:
        #     self.__general_i2c.unlock()

        return 0

    # Electricity sensor functions - delegated to electricity_sensor
    def set_electricity_sensor_pin(self):
        """Set up the electricity sensor"""
        return self.electricity_sensor.set_electricity_sensor_pin()
    
    def get_electricity_values(self):
        """
        Get electricity values from the sensor.
        Returns voltage, current, power, energy, frequency, power_factor, alarm respectively.
        """
        return self.electricity_sensor.get_electricity_values()
    
    def reset_energy(self):
        """Reset the energy value in the electricity sensor"""
        return self.electricity_sensor.reset_energy()
    
    def get_last_resource_reset_time(self):
        """Get the last time the resource was reset"""
        return self.electricity_sensor.get_last_reset_time()
    
    def set_last_resource_reset_time(self, reset_time):
        """Set the last time the resource was reset"""
        self.electricity_sensor.set_last_resource_reset_time(reset_time)