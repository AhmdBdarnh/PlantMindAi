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
        # Water flow sensor variables
        self.__water_flow_running = False
        self.__flow_rate = 0.0

    # Water flow sensor functions
    def set_water_flow_sensor_pin(self, pin):
        """Set up the water flow sensor with the specified pin"""
        self.__water_flow_sensor_pin = pin
        # set the pin of RE & RD
        self.__water_flow_sensor_pin = self.chip.get_line(pin)        
        config = gpiod.line_request()
        config.consumer = "Water_Flow"
        config.request_type = gpiod.line_request.EVENT_BOTH_EDGES        
        self.__water_flow_sensor_pin.request(config=config, default_val=0)
        self.__counter = 0
        self.__water_flow_running = True
        self.__flow_rate = 0.0
        def water_flow_pulse_counter():
            while self.__water_flow_running:
                if self.__water_flow_sensor_pin.event_wait(timedelta(seconds=1)):
                    event = self.__water_flow_sensor_pin.event_read()
                    if event.event_type == gpiod.line_event.RISING_EDGE:
                        self.__counter += 1
        
        def calculate_flow_rate():
            start_time = time.time()
            PULSES_PER_LITRE = 450.0  # pulses per litre for the flow sensor
            while self.__water_flow_running:
                time.sleep(1)
                elapsed_time = time.time() - start_time
                self.__flow_rate = (self.__counter / PULSES_PER_LITRE) / (elapsed_time / 60.0)  # litres per minute
                print(f"Flow Rate: {self.__flow_rate:.2f} L/min")
                self.__counter = 0  # reset the counter for the next interval
                start_time = time.time()  # reset the start time for the next interval                

        # start a thread to count the pulses
        self.__water_flow_thread = threading.Thread(target=water_flow_pulse_counter, daemon=True)
        self.__water_flow_thread.start()

        # start a thread to calculate the flow rate
        self.__flow_rate_thread = threading.Thread(target=calculate_flow_rate, daemon=True)
        self.__flow_rate_thread.start()

    def get_water_flow_rate(self):
        """Get water flow rate in liters per minute"""
        try:
            return self.__flow_rate
        except RuntimeError as err:
            print(f'Sensor Error: {err.args[0]}')
            return 0    
        except KeyboardInterrupt:
            print("Stopping water flow sensor thread.")
            self.__water_flow_running = False
            self.__water_flow_thread.join()
            self.__flow_rate_thread.join()
            return self.__flow_rate

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
        #     print(f'Sensor Error: {err.args[0]}')            
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