import time
import datetime
import board
import busio
import os
from Sensors.sensors import GH_Sensors
from Actuators.actuators import GH_Actuators
from mqtt_handler import MqttHandler
from mongo_db_handler import MongoDBHandler
from aws_s3_handler import S3Handler
from rpi_camera import GH_Camera
from setpoints import GH_Setpoints
from serial_logger import serial_logger_task
import threading
import numpy as np
from simple_pid import PID
from flask import Flask, render_template, Response, jsonify, request
from flask_cors import CORS

from utils.utils import set_serial_log_enabled
from utils.utils import _CUSTOM_PRINT_FUNC

IMAGE_CAP_INTERVAL = 6  # hours interval to capture the image (every x hours)
RESOURCES_CONSUMPTION_LOG_AND_RESET_INTERVAL = 1  # hours interval to log and reset the resources consumption

# initialize the mqtt handler 
mqtt_handler = MqttHandler("114fcbcf879e4e88a21d9f0bd7ab1ccc.s1.eu.hivemq.cloud", 8883, "SmartGreenHouse", "SmartGreenHouse2025")
# mosquitto_pub -h 114fcbcf879e4e88a21d9f0bd7ab1ccc.s1.eu.hivemq.cloud -p 8883 -u "SmartGreenHouse" -P "SmartGreenHouse2025" -t "env_monitoring_system/actuators/light/dc" -m 2048
# mosquitto_sub -h 114fcbcf879e4e88a21d9f0bd7ab1ccc.s1.eu.hivemq.cloud -p 8883 -u "SmartGreenHouse" -P "SmartGreenHouse2025" -t "env_monitoring_system/actuators/light/dc" 
# initialize the mongo db handler
mongo_db_handler = MongoDBHandler(
    "mongodb+srv://PlantMind:ShenkarPlantMind@plantmindai.lma5ro9.mongodb.net/?retryWrites=true&w=majority&appName=PlantMindAi", "GreenHouse"
)

# # dht22 setup
dht22_pin = board.D26

# water flow sensor setup
water_flow_sensor_pin = 12
# #ads1115 soil moisture setup
ads1115_soil_ch = 0
# # ads1115 light setup
ads1115_light_ch = 1
# # initialize the i2c
i2c = busio.I2C(board.SCL, board.SDA)

# initialize the application sensors
env_sensors = GH_Sensors(i2c)
env_sensors.set_dht22_pin(dht22_pin)
env_sensors.set_soil_moisture_ads1115_channel(ads1115_soil_ch)
env_sensors.set_light_intensity_ads1115_channel(ads1115_light_ch)
env_sensors.calibrate_soil_moisture_ads1115(18000, 7000)
env_sensors.set_soil_sensor_pins()
env_sensors.set_electricity_sensor_pin()
env_sensors.set_water_flow_sensor_pin(water_flow_sensor_pin)

# initialize the application actuators
env_actuators = GH_Actuators(0x30, i2c, 'big')

# initialize the setpoints
setpoints = GH_Setpoints(mqtt_handler, mongo_db_handler, env_actuators)

# reset the esp
while not env_actuators.restart_esp32():
    _CUSTOM_PRINT_FUNC("Restarting ESP32...")
    time.sleep(5)

last_date_time = datetime.datetime.now()
_CUSTOM_PRINT_FUNC("Initializing actuators...", end='')
while datetime.datetime.now() - last_date_time < datetime.timedelta(seconds=10):
    _CUSTOM_PRINT_FUNC(".", end='')
    time.sleep(1)

# pin 16, channel 0, frequency 5000 Hz, duty cycle 0
while not env_actuators.setup_light_strip_1_esp32(pin=16, channel=0, timer_src=0, frequency=5000, duty_cycle=0):
    _CUSTOM_PRINT_FUNC("sending light strip 1 setup command again...")
    time.sleep(5)

time.sleep(1)

# pin 15, channel 0, frequency 5000 Hz, duty cycle 0
while not env_actuators.setup_light_strip_2_esp32(pin=15, channel=5, timer_src=0, frequency=5000, duty_cycle=0):
    _CUSTOM_PRINT_FUNC("sending light strip 2 setup command again...")
    time.sleep(5)

time.sleep(1)

# pin 17, channel 1, frequency 10 Hz, duty cycle 0
while not env_actuators.setup_heater_esp32(pin=17, channel=1, timer_src=1, frequency=50, duty_cycle=0):
    _CUSTOM_PRINT_FUNC("sending heater setup command again...")
    time.sleep(5)

time.sleep(1)
# pin 18, channel 2, frequency 25000 Hz, duty cycle 0
while not env_actuators.setup_heater_fan_esp32(pin=18, channel=2, timer_src=0, frequency=5000, duty_cycle=0):
    _CUSTOM_PRINT_FUNC("sending heater fan setup command again...")
    time.sleep(5)

time.sleep(1)
# pin 19, channel 3, frequency 25000 Hz, duty cycle 0
while not env_actuators.setup_fan_esp32(pin=19, channel=3, timer_src=0, frequency=5000, duty_cycle=0):
    _CUSTOM_PRINT_FUNC("sending fan setup command again...")
    time.sleep(5)

time.sleep(5)
# pin 23, channel 4, frequency 1000 Hz, duty cycle 0
while not env_actuators.setup_water_pump_esp32(pin=33, channel=4, timer_src=2, frequency=1000, duty_cycle=0):
    _CUSTOM_PRINT_FUNC("sending water pump setup command again...")
    time.sleep(5)

time.sleep(1)

def set_all_light_strip_dc(duty_cycle = 0):
    """Set the duty cycle for both light strips"""
    while not env_actuators.set_light_strip_1_duty_cycle(duty_cycle):
        _CUSTOM_PRINT_FUNC("Setting light strip 1 duty cycle again...")
        time.sleep(0.1)

    while not env_actuators.set_light_strip_2_duty_cycle(duty_cycle):
        _CUSTOM_PRINT_FUNC("Setting light strip 2 duty cycle again...")
        time.sleep(0.1)

    return True

def set_all_heater_dc(duty_cycle = 0):
    """Set the duty cycle for both heater and heater fan"""
    while not env_actuators.set_heater_duty_cycle(duty_cycle):
        _CUSTOM_PRINT_FUNC("Setting heater duty cycle again...")
        time.sleep(0.1)

    while not env_actuators.set_heater_fan_duty_cycle(duty_cycle):
        _CUSTOM_PRINT_FUNC("Setting heater fan duty cycle again...")
        time.sleep(0.1)

    return True

prev_light_dc_value = 0
prev_heater_dc_value = 0
prev_water_pump_dc_value = 0
prev_fan_dc_value = 0

def set_actuators_manual_values():
    global prev_light_dc_value, prev_heater_dc_value, prev_water_pump_dc_value, prev_fan_dc_value

    if prev_fan_dc_value != env_actuators.get_mqtt_dc_value_fan():
        if not env_actuators.set_fan_duty_cycle(env_actuators.get_mqtt_dc_value_fan()):
            _CUSTOM_PRINT_FUNC("Failed to set fan duty cycle, retrying...")
            time.sleep(0.1)
        prev_fan_dc_value = env_actuators.get_mqtt_dc_value_fan()
    
    if prev_heater_dc_value != env_actuators.get_mqtt_dc_value_heater():
        if not set_all_heater_dc(env_actuators.get_mqtt_dc_value_heater()):
            _CUSTOM_PRINT_FUNC("Failed to set heater duty cycle, retrying...")
            time.sleep(0.1)
        prev_heater_dc_value = env_actuators.get_mqtt_dc_value_heater()

    if prev_light_dc_value != env_actuators.get_mqtt_dc_value_light_strip():
        if not set_all_light_strip_dc(env_actuators.get_mqtt_dc_value_light_strip()):
            _CUSTOM_PRINT_FUNC("Failed to set light strip duty cycle, retrying...")
            time.sleep(0.1)
        prev_light_dc_value = env_actuators.get_mqtt_dc_value_light_strip()

    if prev_water_pump_dc_value != env_actuators.get_mqtt_dc_value_water_pump():
        if not env_actuators.set_water_pump_duty_cycle(env_actuators.get_mqtt_dc_value_water_pump()):
            _CUSTOM_PRINT_FUNC("Failed to set water pump duty cycle, retrying...")
            time.sleep(0.1)
        prev_water_pump_dc_value = env_actuators.get_mqtt_dc_value_water_pump()
    

# set the subscriptions and publications
mqtt_handler.set_subscription("env_monitoring_system/actuators/heater/dc", env_actuators.set_mqtt_dc_value_heater)
mqtt_handler.set_subscription("env_monitoring_system/actuators/light/dc", env_actuators.set_mqtt_dc_value_light_strip)
mqtt_handler.set_subscription("env_monitoring_system/actuators/water_pump/dc", env_actuators.set_mqtt_dc_value_water_pump)
mqtt_handler.set_subscription("env_monitoring_system/actuators/fan/dc", env_actuators.set_mqtt_dc_value_fan)
mqtt_handler.set_subscription("loops/setpoints/temperature", setpoints.set_temperature_setpoint)
mqtt_handler.set_subscription("loops/setpoints/light_intensity", setpoints.set_light_setpoint)
mqtt_handler.set_subscription("loops/setpoints/soil_moisture", setpoints.set_soil_humidity_setpoint)
mqtt_handler.set_subscription("loops/setpoints/water_flow", setpoints.set_water_flow_setpoint)
mqtt_handler.set_subscription("loops/setpoints/operation_mode", setpoints.set_operation_mode)

# set the publications
mqtt_handler.set_publish("env_monitoring_system/sensors/air_temperature_C", 0)
mqtt_handler.set_publish("env_monitoring_system/sensors/air_humidity", 0)
mqtt_handler.set_publish("env_monitoring_system/sensors/light_intensity", 0)
mqtt_handler.set_publish("env_monitoring_system/sensors/soil_ph", 0)
mqtt_handler.set_publish("env_monitoring_system/sensors/soil_ec", 0)
mqtt_handler.set_publish("env_monitoring_system/sensors/soil_temp", 0)
mqtt_handler.set_publish("env_monitoring_system/sensors/soil_humidity", 0)
mqtt_handler.set_publish("env_monitoring_system/sensors/water_flow", 0)
mqtt_handler.set_publish("env_monitoring_system/sensors/voltage", 0)
mqtt_handler.set_publish("env_monitoring_system/sensors/current", 0)
mqtt_handler.set_publish("env_monitoring_system/resources/energy", 0)
mqtt_handler.set_publish("env_monitoring_system/resources/water_amount", 0)
mqtt_handler.set_publish("env_monitoring_system/actuators/heater/state", 0)
mqtt_handler.set_publish("env_monitoring_system/actuators/light/state", 0)
mqtt_handler.set_publish("env_monitoring_system/actuators/water_pump/state", 0)
mqtt_handler.set_publish("env_monitoring_system/actuators/fan/state", 0)

# create the collections in the database
mongo_db_handler.create_collection("sensors_data", "air temp", mongo_db_handler.sensor_field_doc_temp("dht22.temperature", "temperature", 0.0, "C"))
mongo_db_handler.create_collection("sensors_data", "air humidity", mongo_db_handler.sensor_field_doc_temp("dht22.humidity", "humidity", 0.0, "%"))
mongo_db_handler.create_collection("sensors_data", "light intensity", mongo_db_handler.sensor_field_doc_temp("ads1115.light_intensity", "intensity", 0.0, "Lux"))
mongo_db_handler.create_collection("sensors_data", "soil ph", mongo_db_handler.sensor_field_doc_temp("soil_ph", "ph", 0.0, "pH"))
mongo_db_handler.create_collection("sensors_data", "soil ec", mongo_db_handler.sensor_field_doc_temp("soil_ec", "ec", 0.0, "uS/cm"))
mongo_db_handler.create_collection("sensors_data", "soil temp", mongo_db_handler.sensor_field_doc_temp("soil_temp", "temperature", 0.0, "C"))
mongo_db_handler.create_collection("sensors_data", "soil humidity", mongo_db_handler.sensor_field_doc_temp("soil_humidity", "humidity", 0.0, "%"))
mongo_db_handler.create_collection("sensors_data", "water flow", mongo_db_handler.sensor_field_doc_temp("water_flow", "flow", 0.0, "L/min"))
mongo_db_handler.create_collection("sensors_data", "voltage", mongo_db_handler.sensor_field_doc_temp("pzem-004t.voltage", "voltage", 0.0, "V"))
mongo_db_handler.create_collection("sensors_data", "current", mongo_db_handler.sensor_field_doc_temp("pzem-004t.current", "current", 0.0, "A"))
mongo_db_handler.create_collection("resources", "energy consumption", mongo_db_handler.resource_field_doc_temp("pzem-004t.energy", "energy_consumption", 0.0, "Wh"))
mongo_db_handler.create_collection("resources", "water consumption", mongo_db_handler.resource_field_doc_temp( "water_flow.total_amount", "water_amount", 0.0, "L"))


# create the actuators collections in the database
mongo_db_handler.create_collection("actuators_data", "heater", mongo_db_handler.actuator_field_doc_temp("heater", "heater", 0))
mongo_db_handler.create_collection("actuators_data", "light", mongo_db_handler.actuator_field_doc_temp("light", "light", 0))
mongo_db_handler.create_collection("actuators_data", "water pump", mongo_db_handler.actuator_field_doc_temp("water_pump", "water pump", 0))
mongo_db_handler.create_collection("actuators_data", "fan", mongo_db_handler.actuator_field_doc_temp("fan", "fan", 0))

# create the setpoints collections in the database
mongo_db_handler.create_collection("plant_images", "plant image", {"_id": "", "image": "", "timestamp": datetime.datetime.now()})

s3_handler = S3Handler("smartgreenhouse-2025", "eu-north-1")

# a function to toggle light on max and off again after shot
def toggle_flash_light(state = 1):
    if state == 1:
        if setpoints.get_operation_mode() == "autonomous":
            setpoints.set_control_thread_event("light", False)  # Pause light control thread
        # Turn on both light strips to full power
        while not env_actuators.set_light_strip_1_duty_cycle(4095):
            _CUSTOM_PRINT_FUNC("Turning on light strip 1 for camera flash...")
            time.sleep(0.1)

        while not env_actuators.set_light_strip_2_duty_cycle(4095):
            _CUSTOM_PRINT_FUNC("Turning on light strip 2 for camera flash...")
            time.sleep(0.1)
    else:
        if setpoints.get_operation_mode() == "autonomous":
            setpoints.set_control_thread_event("light", True)
        
# init the camera
camera = GH_Camera()

temperature_semaphore = threading.Semaphore(1)
temperature_pause_event = threading.Event()
temperature_pause_event.set()

light_semaphore = threading.Semaphore(1)
light_pause_event = threading.Event()
light_pause_event.set()

soil_semaphore = threading.Semaphore(1)
soil_pause_event = threading.Event()
soil_pause_event.set()

electricity_semaphore = threading.Semaphore(1)
electricity_pause_event = threading.Event()
electricity_pause_event.set()

water_flow_semaphore = threading.Semaphore(1)

def temperature_sp_adjustment_task():
    # PID controller parameters - easily tunable
    KP_TEMP = 1034.05  # Proportional gain
    KI_TEMP = 1.52  # Integral gain
    KD_TEMP = 0.0  # Derivative gain
    
    # Output limits for bidirectional control (-1 to 1)
    # Negative values for cooling, positive for heating
    OUTPUT_LIMITS = (-1, 1)
    
    # Sample time in seconds
    SAMPLE_TIME = 10
    
    # Deadband to prevent rapid switching between heating and cooling
    DEADBAND = 0.2  # °C
    
    # Actuator power limits
    MIN_POWER = 500
    MAX_POWER = 4095
    POWER_RANGE = MAX_POWER - MIN_POWER
    
    # Create a single PID controller for both heating and cooling
    # Error = setpoint - measurement
    # Positive error (temp < setpoint) produces positive output (heating)
    # Negative error (temp > setpoint) produces negative output (cooling)
    temperature_pid = PID(KP_TEMP, KI_TEMP, KD_TEMP, 
                         setpoint=0, 
                         sample_time=SAMPLE_TIME, 
                         output_limits=OUTPUT_LIMITS)
    temperature_pid.proportional_on_measurement = False  # Use error directly
    
    while True:
        temperature_pause_event.wait()  # Wait until the event is set
        
        # Read temperature setpoint safely
        temperature_set_point = setpoints.get_temperature_setpoint()
        
        # Update setpoint for the controller
        temperature_pid.setpoint = temperature_set_point
        
        # Read temperature safely
        try:
            temperature_semaphore.acquire()
            current_temp = env_sensors.get_air_temperature_C()
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error reading temperature: {e}")
            continue
        finally:
            temperature_semaphore.release()
        
        # Calculate control output using PID
        # Positive output = heating needed
        # Negative output = cooling needed
        # Output near zero = within deadband
        raw_output = temperature_pid(current_temp)
        
        # Anti-windup logic: If output is saturated, prevent integral accumulation
        if (raw_output >= OUTPUT_LIMITS[1] and (temperature_set_point - current_temp) > 0) or \
           (raw_output <= OUTPUT_LIMITS[0] and (temperature_set_point - current_temp) < 0):
            # Skip integral accumulation when output is clamped
            temperature_pid._integral -= (temperature_set_point - current_temp) * KI_TEMP * SAMPLE_TIME
        
        control_output = raw_output

        # Apply deadband to prevent oscillation
        if abs(temperature_set_point - current_temp) < DEADBAND:
            # Within deadband - no action needed
            control_output = 0
        
        # Apply control based on output sign
        if control_output > 0:  # Positive output = heating
            # Scale heating power from 0-1 range to MIN_POWER-MAX_POWER range
            heat_power_scaled = control_output # This is 0 to 1
            heater_duty_cycle = int(MIN_POWER + (POWER_RANGE * heat_power_scaled))
            heater_duty_cycle = max(MIN_POWER, min(MAX_POWER, heater_duty_cycle)) # Clamp to be safe
            
            # Apply heating
            while not env_actuators.set_heater_duty_cycle(heater_duty_cycle):
                time.sleep(0.1)

            while not env_actuators.set_heater_fan_duty_cycle(heater_duty_cycle):  # Heater fan matches heater
                time.sleep(0.1)

            while not env_actuators.set_fan_duty_cycle(0): # Cooling fan off
                time.sleep(0.1)
            
        elif control_output < 0:  # Negative output = cooling
            # Scale cooling power from 0-1 range (abs value) to MIN_POWER-MAX_POWER range
            cool_power_scaled = abs(control_output) # This is 0 to 1
            fan_duty_cycle = int(MIN_POWER + (POWER_RANGE * cool_power_scaled))
            fan_duty_cycle = max(MIN_POWER, min(MAX_POWER, fan_duty_cycle)) # Clamp to be safe
            
            # Turn off heating
            while not env_actuators.set_heater_duty_cycle(0):
                time.sleep(0.1)
            while not env_actuators.set_heater_fan_duty_cycle(0):
                time.sleep(0.1)
            
            # Apply cooling
            while not env_actuators.set_fan_duty_cycle(fan_duty_cycle):
                time.sleep(0.1)
            
        else:  # Output is zero (within deadband or exactly at setpoint)
            # Turn everything off
            while not env_actuators.set_heater_duty_cycle(0):
                time.sleep(0.1)

            while not env_actuators.set_heater_fan_duty_cycle(0):
                time.sleep(0.1)

            while not env_actuators.set_fan_duty_cycle(0):
                time.sleep(0.1)
        
        time.sleep(SAMPLE_TIME)


def light_sp_adjustment_task():
    # PID controller parameters - easily tunable
    KP_LIGHT = 20  # Proportional gain -> 75 
    KI_LIGHT = 7.5  # Integral gain -> 55
    KD_LIGHT = 0.1  # Derivative gain -> 22
    
    # Output limits (0-4095 for direct duty cycle)
    OUTPUT_LIMITS = (0, 4095)
    
    # Sample time in seconds
    SAMPLE_TIME = 0.1
    
    # Create PID controller for light
    light_pid = PID(KP_LIGHT, KI_LIGHT, KD_LIGHT, setpoint=0, sample_time=SAMPLE_TIME, output_limits=OUTPUT_LIMITS)
    light_pid.proportional_on_measurement = False  # Use error directly
    
    # Previous setpoint to detect changes
    prev_set_point = 0
    
    while True:
        light_pause_event.wait()  # Wait until the event is set
        
        # Read light setpoint
        light_set_point = setpoints.get_light_setpoint()
        
        # Update PID setpoint
        light_pid.setpoint = light_set_point
        
        # Read light intensity safely
        try:
            light_semaphore.acquire()
            light_intensity = env_sensors.get_light_intensity()
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error reading light sensor: {e}")
            continue
        finally:
            light_semaphore.release()
        
        # If setpoint changes, reset the PID controller to avoid integral windup
        if prev_set_point != light_set_point:
            light_pid.reset()
            prev_set_point = light_set_point
        
        # Only adjust if setpoint is greater than 0 (we want some light)
        if light_set_point > 0:
            # Calculate duty cycle using PID
            duty_cycle = light_pid(light_intensity)
            
            # Apply duty cycle to light
            while not env_actuators.set_light_strip_1_duty_cycle(int(duty_cycle)):
                time.sleep(0.1)
                
            while not env_actuators.set_light_strip_2_duty_cycle(int(duty_cycle)):
                time.sleep(0.1)
        else:
            # Turn off lights if setpoint is 0
            while not env_actuators.set_light_strip_1_duty_cycle(0):
                time.sleep(0.1)
                        
            while not env_actuators.set_light_strip_2_duty_cycle(0):
                time.sleep(0.1)

            # Reset PID to prevent integral windup
            light_pid.reset()
        
        time.sleep(SAMPLE_TIME)


def set_soil_moisture_setpoint_task():
    PUMP_DUTY_CYCLE = 4096  # Full power for the pump
    WATER_Q = 500  # milliliters per cycle
    SLEEP_INTERVAL = 0.5 * 60  # seconds (5 minutes)

    irrigating = False  # Tracks irrigation state

    while True:
        soil_pause_event.wait()  # Wait until the event is set

        # Read the setpoint and hysteresis from user settings
        mo_set_point = setpoints.get_soil_humidity_setpoint()
        hysteresis = setpoints.get_soil_humidity_hysteresis()  # Assume you add this function

        start_threshold = mo_set_point - hysteresis

        # Read the soil moisture value
        soil_semaphore.acquire()
        try:
            _, _, soil_humidity, _ = env_sensors.get_soil_values()
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error reading soil moisture: {e}")
        finally:
            soil_semaphore.release()

        _CUSTOM_PRINT_FUNC(f"[Soil] Moisture: {soil_humidity:.2f}%, Setpoint: {mo_set_point:.2f}%, Threshold: {start_threshold:.2f}%")

        # Hysteresis logic
        if not irrigating and soil_humidity <= start_threshold:
            irrigating = True
            _CUSTOM_PRINT_FUNC("💧 Starting irrigation...")

        elif irrigating and soil_humidity >= mo_set_point:
            irrigating = False
            _CUSTOM_PRINT_FUNC("✅ Stopping irrigation...")

        if irrigating:
            # while env_sensors.get_water_flow_rate() <= 0:
            #     print("Waiting for water flow to update...")
            #     time.sleep(0.1)
            # Start pump
            while not env_actuators.set_water_pump_duty_cycle(PUMP_DUTY_CYCLE):
                time.sleep(0.1)
            _CUSTOM_PRINT_FUNC("Water pump ON")
            
            total_added = 0
            last_water_amount = env_sensors.get_total_water_amount()
            while total_added < WATER_Q:                
                # Read water flow rate
                total_added = (env_sensors.get_total_water_amount() - last_water_amount) * 1000
                time.sleep(1)
                
            # Stop pump after adding required water
            while not env_actuators.set_water_pump_duty_cycle(0):
                time.sleep(0.1)
            _CUSTOM_PRINT_FUNC("Water pump OFF")

        else:
            _CUSTOM_PRINT_FUNC("No irrigation needed. System idle.")

        time.sleep(SLEEP_INTERVAL)


serial_logger_thread = None
last_sensor_update = datetime.datetime.now() - datetime.timedelta(seconds=10)

def get_last_sensor_update():
    """Get the last sensor update time"""
    global last_sensor_update
    return last_sensor_update.strftime('%Y-%m-%d %H:%M:%S')

def app_task():
    global serial_logger_thread, last_sensor_update, env_sensors, env_actuators, setpoints, camera, s3_handler, mqtt_handler, mongo_db_handler
    setpoints.set_operation_mode("manual")  # Set initial operation mode to manual
    env_actuators.stop_all_actuators()  # Stop all actuators when mode changes
    last_time_captured = datetime.datetime.now() - datetime.timedelta(hours=IMAGE_CAP_INTERVAL)
    last_sensor_update = datetime.datetime.now() - datetime.timedelta(seconds=10)
    last_actuators_update = datetime.datetime.now() - datetime.timedelta(seconds=1)
    
    # retrieve last time energy was reset from local file
    try:
        with open('consumption/last_resources_reset.txt', 'r') as file:
            last_resources_reset_and_log = datetime.datetime.strptime(file.read().strip(), '%Y-%m-%d %H:%M:%S')
            env_sensors.set_last_resource_reset_time(last_resources_reset_and_log.strftime('%Y-%m-%d %H:%M:%S'))
            # last_resources_reset_and_log = last_resources_reset_and_log - datetime.timedelta(hours=RESOURCES_CONSUMPTION_LOG_AND_RESET_INTERVAL)
            _CUSTOM_PRINT_FUNC(f"Last resources reset and log time was : {last_resources_reset_and_log}")
    except FileNotFoundError:
        _CUSTOM_PRINT_FUNC("No previous resources reset time found, setting to current time minus interval.")        
        last_resources_reset_and_log = datetime.datetime.now() - datetime.timedelta(hours=RESOURCES_CONSUMPTION_LOG_AND_RESET_INTERVAL)
        _CUSTOM_PRINT_FUNC(f"Last resources reset and log time was : {last_resources_reset_and_log}")

    prev_light_duty_cycle = 0.0
    prev_heater_duty_cycle = 0.0
    prev_heater_fan_duty_cycle = 0.0
    prev_fan_duty_cycle = 0.0
    prev_water_pump_duty_cycle = 0.0

    # take a temp photo 
    # for _ in range(3):
    #     path = camera.capture_store_image(0, True)
    #     if path:
    #         _CUSTOM_PRINT_FUNC(f"Captured initial image for camera flash: {path}")        
    #         os.remove(path)
    #     else:
    #         _CUSTOM_PRINT_FUNC("Failed to capture initial image for camera flash.")
    #     time.sleep(1)
    
    while True:

        if (datetime.datetime.now() - last_sensor_update).total_seconds() > 10:
            temperature_semaphore.acquire()
            try:
                air_temp_c = env_sensors.get_air_temperature_C()
                air_temp_f = env_sensors.get_air_temperature_F()
                air_humidity = env_sensors.get_air_humidity()
            finally:
                temperature_semaphore.release()

            light_semaphore.acquire()
            try:
                light_intensity = env_sensors.get_light_intensity()
            finally:
                light_semaphore.release()

            soil_semaphore.acquire()
            try:
                soil_ph, soil_ec, soil_humidity, soil_temp = env_sensors.get_soil_values()
            finally:
                soil_semaphore.release()

            electricity_semaphore.acquire()
            try:
                voltage, current, power, energy, frequency, power_factor, alarm = env_sensors.get_electricity_values()
                # _CUSTOM_PRINT_FUNC(f"Voltage: {voltage:.2f} V")
                # _CUSTOM_PRINT_FUNC(f"Current: {current:.2f} A")
                # _CUSTOM_PRINT_FUNC(f"Power: {power:.2f} W")
                # _CUSTOM_PRINT_FUNC(f"Energy: {energy:.2f} Wh")
                # _CUSTOM_PRINT_FUNC(f"Frequency: {frequency:.2f} Hz")
                # _CUSTOM_PRINT_FUNC(f"Power Factor: {power_factor:.2f}")
                # _CUSTOM_PRINT_FUNC(f"Alarm: {alarm}")
                # send the data to the mqtt broker
                # mqtt_handler.publish("env_monitoring_system/sensors/power", power)
                # mqtt_handler.publish("env_monitoring_system/sensors/energy", energy)
                # mqtt_handler.publish("env_monitoring_system/sensors/frequency", frequency)
                # mqtt_handler.publish("env_monitoring_system/sensors/power_factor", power_factor)
                # mqtt_handler.publish("env_monitoring_system/sensors/alarm", alarm)
            except Exception as e:
                _CUSTOM_PRINT_FUNC(f"Error reading electricity sensor: {e}")
            finally:
                electricity_semaphore.release()

            # _CUSTOM_PRINT_FUNC("**************************************************")
            # _CUSTOM_PRINT_FUNC(f'Air Temperature (C): {air_temp_c} C')
            # _CUSTOM_PRINT_FUNC(f'Air Temperature (F): {air_temp_f} F')
            # _CUSTOM_PRINT_FUNC(f'Air Humidity (%): {air_humidity} %')
            # _CUSTOM_PRINT_FUNC("**************************************************")
            # _CUSTOM_PRINT_FUNC(f'ADS1115 Light Intensity (Lux): {light_intensity} Lux | veml = {env_sensors.get_light_intensity_veml()} lux')
            # _CUSTOM_PRINT_FUNC("**************************************************")
            # _CUSTOM_PRINT_FUNC(f'Soil PH: {soil_ph}')
            # _CUSTOM_PRINT_FUNC(f'Soil EC (uS/cm): {soil_ec} uS/cm')
            # _CUSTOM_PRINT_FUNC(f'Soil Temperature (C): {soil_temp} C')
            # _CUSTOM_PRINT_FUNC(f'Soil Humidity (%): {soil_humidity} %')
            # _CUSTOM_PRINT_FUNC("**************************************************")
            # _CUSTOM_PRINT_FUNC(f'Water Flow: {water_flow} L/min')            
            # _CUSTOM_PRINT_FUNC("**************************************************")
            # _CUSTOM_PRINT_FUNC(f'Voltage: {voltage} V')
            # _CUSTOM_PRINT_FUNC(f'Current: {current} A')
            # _CUSTOM_PRINT_FUNC(f'Power: {power} W')
            # _CUSTOM_PRINT_FUNC(f'Energy: {energy} Wh')
            # _CUSTOM_PRINT_FUNC(f'Frequency: {frequency} Hz')
            # _CUSTOM_PRINT_FUNC(f'Power Factor: {power_factor}')
            # _CUSTOM_PRINT_FUNC(f'Alarm: {alarm}')
            # _CUSTOM_PRINT_FUNC("**************************************************")
                
            # send the data to the mqtt broker
            mqtt_handler.publish("env_monitoring_system/sensors/air_temperature_C", air_temp_c)
            mqtt_handler.publish("env_monitoring_system/sensors/air_humidity", air_humidity)
            mqtt_handler.publish("env_monitoring_system/sensors/light_intensity", light_intensity)
            mqtt_handler.publish("env_monitoring_system/sensors/soil_ph", soil_ph)
            mqtt_handler.publish("env_monitoring_system/sensors/soil_ec", soil_ec)
            mqtt_handler.publish("env_monitoring_system/sensors/soil_temp", soil_temp)
            mqtt_handler.publish("env_monitoring_system/sensors/soil_humidity", soil_humidity)                        
            mqtt_handler.publish("env_monitoring_system/sensors/voltage", voltage)
            mqtt_handler.publish("env_monitoring_system/sensors/current", current)
            mqtt_handler.publish("env_monitoring_system/resources/energy", energy)
            mqtt_handler.publish("env_monitoring_system/resources/water_amount", env_sensors.get_total_water_amount())
            # send to database
            mongo_db_handler.insert_sensor_data("air temp", air_temp_c)
            mongo_db_handler.insert_sensor_data("air humidity", air_humidity)
            mongo_db_handler.insert_sensor_data("light intensity", light_intensity)
            mongo_db_handler.insert_sensor_data("soil ph", soil_ph)
            mongo_db_handler.insert_sensor_data("soil ec", soil_ec)
            mongo_db_handler.insert_sensor_data("soil temp", soil_temp)
            mongo_db_handler.insert_sensor_data("soil humidity", soil_humidity)

            last_sensor_update = datetime.datetime.now()

        # update energy & water amount in database every 1 hour
        if (datetime.datetime.now() - last_resources_reset_and_log).total_seconds() > RESOURCES_CONSUMPTION_LOG_AND_RESET_INTERVAL * 3600:
            electricity_semaphore.acquire()
            try:
                _, _, _, energy_cons, _, _, _ = env_sensors.get_electricity_values()
                mqtt_handler.publish("env_monitoring_system/resources/energy", energy_cons)
                # send to database
                mongo_db_handler.insert_resource_data("energy consumption", energy_cons)
                mongo_db_handler.resource_field_doc_temp("pzem-004t.energy", "energy_consumption", energy_cons, "Wh")
                # reset the energy consumption for the electricity sensor
                env_sensors.reset_energy()

            except Exception as e:
                _CUSTOM_PRINT_FUNC(f"Error reading electricity sensor: {e}")
            finally:
                electricity_semaphore.release()

            # water amount
            water_flow_semaphore.acquire()
            try:
                water_amount = env_sensors.get_total_water_amount()
                # _CUSTOM_PRINT_FUNC(f"Total Water Amount: {water_flow:.2f} L")
                # send the data to the mqtt broker
                mqtt_handler.publish("env_monitoring_system/resources/water_amount", water_amount)
                # send to database
                mongo_db_handler.insert_resource_data("water consumption", water_amount)         
                
                env_sensors.reset_water_amount()
            except Exception as e:
                _CUSTOM_PRINT_FUNC(f"Error reading water flow sensor: {e}")
            finally:
                water_flow_semaphore.release()

            # reset the last resources reset time
            last_resources_reset_and_log = datetime.datetime.now()

            # reset the energy and water amount in local files
            with open('consumption/last_resources_reset.txt', 'w') as file:
                file.write(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            
            _CUSTOM_PRINT_FUNC(f"Last resources reset and log time updated to: {last_resources_reset_and_log}")
        
        # update the actuators data
        if (datetime.datetime.now() - last_actuators_update).total_seconds() > 1:
            last_actuators_update = datetime.datetime.now()

            set_actuators_manual_values()  # Set manual values if any
            # read the water flow rate safely
            water_flow_semaphore.acquire()
            try:
                water_flow = env_sensors.get_water_flow_rate()
                # _CUSTOM_PRINT_FUNC(f"Flow Rate: {water_flow:.2f} L/min")
                mongo_db_handler.insert_sensor_data("water flow", water_flow)                
                mqtt_handler.publish("env_monitoring_system/sensors/water_flow", water_flow)
            finally:
                water_flow_semaphore.release()

            # read the actuators data
            heater_duty_cycle = env_actuators.get_heater_duty_cycle()
            light_duty_cycle = env_actuators.get_light_strip_1_duty_cycle()
            water_pump_duty_cycle = env_actuators.get_water_pump_duty_cycle()
            fan_duty_cycle = env_actuators.get_fan_duty_cycle()
            

            if heater_duty_cycle != prev_heater_duty_cycle:
                prev_heater_duty_cycle = heater_duty_cycle
                # send the data to the mqtt broker
                if heater_duty_cycle == 0:
                    mqtt_handler.publish(
                        "env_monitoring_system/actuators/heater/state", 'Off')
                else:
                    mqtt_handler.publish(
                        "env_monitoring_system/actuators/heater/state", f'On at {heater_duty_cycle * 100 / 4095:.2f}%')
                    
                # send to database
                mongo_db_handler.insert_actuator_data(
                    "heater", heater_duty_cycle)
            
            if light_duty_cycle != prev_light_duty_cycle:
                prev_light_duty_cycle = light_duty_cycle
                # send the data to the mqtt broker
                if light_duty_cycle == 0:
                    mqtt_handler.publish(
                        "env_monitoring_system/actuators/light/state", 'Off')
                else:
                    mqtt_handler.publish(
                        "env_monitoring_system/actuators/light/state", f'On at {light_duty_cycle * 100 / 4095:.2f}%')
                    
                # send to database
                mongo_db_handler.insert_actuator_data(
                    "light", light_duty_cycle)
                    
            if water_pump_duty_cycle != prev_water_pump_duty_cycle:
                prev_water_pump_duty_cycle = water_pump_duty_cycle
                # send the data to the mqtt broker
                if water_pump_duty_cycle == 0:
                    mqtt_handler.publish(
                        "env_monitoring_system/actuators/water_pump/state", 'Off')
                else:
                    mqtt_handler.publish(
                        "env_monitoring_system/actuators/water_pump/state", f'On at {water_pump_duty_cycle * 100 / 4095:.2f}%')
                    
                # send to database
                mongo_db_handler.insert_actuator_data(
                    "water pump", water_pump_duty_cycle)
                    
            if fan_duty_cycle != prev_fan_duty_cycle:
                prev_fan_duty_cycle = fan_duty_cycle
                # send the data to the mqtt broker
                if fan_duty_cycle == 0:
                    mqtt_handler.publish(
                        "env_monitoring_system/actuators/fan/state", 'Off')
                else:
                    mqtt_handler.publish(
                        "env_monitoring_system/actuators/fan/state", f'On at {fan_duty_cycle * 100 / 4095:.2f}%')
                
                # send to database
                mongo_db_handler.insert_actuator_data(
                    "fan", fan_duty_cycle)

        # capture the image every 6 hours
        if (datetime.datetime.now() - last_time_captured).total_seconds() > IMAGE_CAP_INTERVAL * 3600:
            last_time_captured = datetime.datetime.now()
            _CUSTOM_PRINT_FUNC("Capturing images from cameras...")
            toggle_flash_light(1)  # Turn on flash light for cameras
            # capture the image
            s3_image_count = s3_handler.get_num_of_files()

            last_time_captured = datetime.datetime.now()
            # image_path_cam0 = camera.capture_store_image(s3_image_count + 1, 0, True) # camera 0 with usb
            # image_path_cam1 = camera.capture_store_image(s3_image_count + 1, 0) # rpi camera port 0

            i = 0
            for image_path in [image_path_cam0, image_path_cam1]:
                if image_path:
                    # upload the image to s3
                    s3_handler.upload_file(
                        image_path, os.path.basename(image_path))

                    # get the s3 url
                    s3_url = s3_handler.get_s3_url(os.path.basename(image_path))

                    if s3_url:
                        _CUSTOM_PRINT_FUNC(f"S3 URL: {s3_url}")
                        # insert the image url to the database
                        mongo_db_handler.insert_image_data("plant image", s3_url, i)
                        i += 1
                        # remove the image from local storage
                        camera.remove_image(image_path)                    
                    else:
                        _CUSTOM_PRINT_FUNC("Error getting S3 URL")                        
                    time.sleep(1)
                else:
                    _CUSTOM_PRINT_FUNC("Error capturing image")
            toggle_flash_light(0)  # Turn off flash light after capturing images


        

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

# ==================== REST API ENDPOINTS ====================

@app.route('/api/sensors', methods=['GET'])
def get_sensors():
    """Get all sensor readings"""
    try:
        # Read sensors with thread safety
        temperature_semaphore.acquire()
        try:
            air_temp_c = env_sensors.get_air_temperature_C()
            air_humidity = env_sensors.get_air_humidity()
        finally:
            temperature_semaphore.release()

        light_semaphore.acquire()
        try:
            light_intensity = env_sensors.get_light_intensity()
        finally:
            light_semaphore.release()

        soil_semaphore.acquire()
        try:
            soil_ph, soil_ec, soil_humidity, soil_temp = env_sensors.get_soil_values()
        finally:
            soil_semaphore.release()

        electricity_semaphore.acquire()
        try:
            voltage, current, power, energy, frequency, power_factor, alarm = env_sensors.get_electricity_values()
        finally:
            electricity_semaphore.release()

        water_flow_semaphore.acquire()
        try:
            water_flow = env_sensors.get_water_flow_rate()
            water_amount = env_sensors.get_total_water_amount()
        finally:
            water_flow_semaphore.release()

        return jsonify({
            'success': True,
            'data': {
                'air_temperature': round(air_temp_c, 2),
                'air_humidity': round(air_humidity, 2),
                'light_intensity': round(light_intensity, 2),
                'soil_ph': round(soil_ph, 2),
                'soil_ec': round(soil_ec, 2),
                'soil_humidity': round(soil_humidity, 2),
                'soil_temperature': round(soil_temp, 2),
                'water_flow': round(water_flow, 2),
                'water_amount': round(water_amount, 2),
                'voltage': round(voltage, 2),
                'current': round(current, 2),
                'power': round(power, 2),
                'energy': round(energy, 2),
                'frequency': round(frequency, 2),
                'power_factor': round(power_factor, 2)
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/actuators', methods=['GET'])
def get_actuators():
    """Get all actuator states"""
    try:
        heater_dc = env_actuators.get_heater_duty_cycle()
        light_dc = env_actuators.get_light_strip_1_duty_cycle()
        fan_dc = env_actuators.get_fan_duty_cycle()
        pump_dc = env_actuators.get_water_pump_duty_cycle()

        return jsonify({
            'success': True,
            'data': {
                'heater': {
                    'duty_cycle': heater_dc,
                    'percentage': round((heater_dc / 4095) * 100, 2),
                    'state': 'on' if heater_dc > 0 else 'off'
                },
                'light': {
                    'duty_cycle': light_dc,
                    'percentage': round((light_dc / 4095) * 100, 2),
                    'state': 'on' if light_dc > 0 else 'off'
                },
                'fan': {
                    'duty_cycle': fan_dc,
                    'percentage': round((fan_dc / 4095) * 100, 2),
                    'state': 'on' if fan_dc > 0 else 'off'
                },
                'water_pump': {
                    'duty_cycle': pump_dc,
                    'percentage': round((pump_dc / 4095) * 100, 2),
                    'state': 'on' if pump_dc > 0 else 'off'
                }
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/actuators/heater', methods=['POST'])
def control_heater():
    """Control heater - expects {state: 'on'/'off'} or {duty_cycle: 0-4095}"""
    try:
        data = request.get_json()

        if 'state' in data:
            duty_cycle = 2048 if data['state'] == 'on' else 0
        elif 'duty_cycle' in data:
            duty_cycle = int(data['duty_cycle'])
        else:
            return jsonify({'success': False, 'error': 'Missing state or duty_cycle'}), 400

        duty_cycle = max(0, min(4095, duty_cycle))

        if not set_all_heater_dc(duty_cycle):
            return jsonify({'success': False, 'error': 'Failed to set heater'}), 500

        return jsonify({'success': True, 'duty_cycle': duty_cycle})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/actuators/light', methods=['POST'])
def control_light():
    """Control light strips - expects {state: 'on'/'off'} or {duty_cycle: 0-4095}"""
    try:
        data = request.get_json()

        if 'state' in data:
            duty_cycle = 2048 if data['state'] == 'on' else 0
        elif 'duty_cycle' in data:
            duty_cycle = int(data['duty_cycle'])
        else:
            return jsonify({'success': False, 'error': 'Missing state or duty_cycle'}), 400

        duty_cycle = max(0, min(4095, duty_cycle))

        if not set_all_light_strip_dc(duty_cycle):
            return jsonify({'success': False, 'error': 'Failed to set light'}), 500

        return jsonify({'success': True, 'duty_cycle': duty_cycle})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/actuators/fan', methods=['POST'])
def control_fan():
    """Control fan - expects {state: 'on'/'off'} or {duty_cycle: 0-4095}"""
    try:
        data = request.get_json()

        if 'state' in data:
            duty_cycle = 2048 if data['state'] == 'on' else 0
        elif 'duty_cycle' in data:
            duty_cycle = int(data['duty_cycle'])
        else:
            return jsonify({'success': False, 'error': 'Missing state or duty_cycle'}), 400

        duty_cycle = max(0, min(4095, duty_cycle))

        if not env_actuators.set_fan_duty_cycle(duty_cycle):
            return jsonify({'success': False, 'error': 'Failed to set fan'}), 500

        return jsonify({'success': True, 'duty_cycle': duty_cycle})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/actuators/water_pump', methods=['POST'])
def control_water_pump():
    """Control water pump - expects {state: 'on'/'off'} or {duty_cycle: 0-4095}"""
    try:
        data = request.get_json()

        if 'state' in data:
            duty_cycle = 2048 if data['state'] == 'on' else 0
        elif 'duty_cycle' in data:
            duty_cycle = int(data['duty_cycle'])
        else:
            return jsonify({'success': False, 'error': 'Missing state or duty_cycle'}), 400

        duty_cycle = max(0, min(4095, duty_cycle))

        if not env_actuators.set_water_pump_duty_cycle(duty_cycle):
            return jsonify({'success': False, 'error': 'Failed to set water pump'}), 500

        return jsonify({'success': True, 'duty_cycle': duty_cycle})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/operation_mode', methods=['GET', 'POST'])
def operation_mode():
    """Get or set operation mode (manual/autonomous)"""
    try:
        if request.method == 'GET':
            mode = setpoints.get_operation_mode()
            return jsonify({'success': True, 'mode': mode})
        else:
            data = request.get_json()
            mode = data.get('mode')
            if mode not in ['manual', 'autonomous']:
                return jsonify({'success': False, 'error': 'Invalid mode'}), 400

            setpoints.set_operation_mode(mode)
            return jsonify({'success': True, 'mode': mode})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== WEB ROUTES ====================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/cameras')
def cameras():
    """Camera viewer page"""
    return render_template('camera_view.html')

@app.route('/camera_4k')
def camera_4k_fullscreen():
    """4K Camera full-screen viewer"""
    return render_template('camera_4k_fullscreen.html')

@app.route('/video_c1')
def video_c1():
    return Response(camera.generate_video_stream_camera_USB(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/video_c2')
def video_c2():
    return Response(camera.generate_video_stream_camera_RPi(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/start_stream_c1')
def start_stream_c1():
    return Response(camera.generate_video_stream_camera_USB(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')
    
@app.route('/start_stream_c2')
def start_stream_c2():
    return Response(camera.generate_video_stream_camera_RPi(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/stop_stream_c1')
def stop_stream_c1():
    camera.stop_camera_USB()
    return "Camera stopped."

@app.route('/stop_stream_c2')
def stop_stream_c2():
    camera.stop_camera_RPi()
    return "Camera stopped."

# ==================== NEW 4K CAMERA ENDPOINTS ====================

@app.route('/video_c3')
def video_c3():
    """Stream video from 4K camera"""
    return Response(camera.generate_video_stream_camera_4K(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/start_stream_c3')
def start_stream_c3():
    """Start streaming from 4K camera"""
    return Response(camera.generate_video_stream_camera_4K(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/stop_stream_c3')
def stop_stream_c3():
    """Stop the 4K camera stream"""
    camera.stop_camera_4K()
    return "4K Camera stopped."

@app.route('/api/cameras', methods=['GET'])
def get_available_cameras():
    """Get list of all available cameras"""
    try:
        cameras = camera.get_available_cameras()
        return jsonify({'success': True, 'cameras': cameras})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/capture_4k', methods=['POST'])
def capture_4k_image():
    """
    Capture a high-resolution image from the 4K camera
    Optional JSON body: {"resolution": [width, height]}
    """
    try:
        data = request.get_json() if request.is_json else {}
        resolution = data.get('resolution', [2592, 1944])  # Default to max resolution

        # Generate filename with timestamp
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        filename = f"4k_capture_{timestamp}.jpg"

        # Capture image
        path = camera.capture_image_4K(path=filename, resolution=tuple(resolution))

        if path:
            return jsonify({
                'success': True,
                'path': path,
                'resolution': resolution,
                'message': 'Image captured successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to capture image'
            }), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# @app.route('/capture_c1')
# def capture_c1():    
#     """Capture an image from the USB camera and upload to S3"""
#     # stop the stream temporarily
#     camera.stop_camera_USB()
#     _CUSTOM_PRINT_FUNC("Capturing image from USB camera...")
#     image_num = s3_handler.get_num_of_files() + 1
#     path = camera.capture_store_image(image_num, 0, True)
#     if path:
#         _CUSTOM_PRINT_FUNC(f"Captured image: {path}")
#         s3_handler.upload_file(path, os.path.basename(path))
#         s3_url = s3_handler.get_s3_url(os.path.basename(path))
#         if s3_url:
#             _CUSTOM_PRINT_FUNC(f"S3 URL: {s3_url}")
#             mongo_db_handler.insert_image_data("plant image", s3_url, 0)
#             camera.remove_image(path)
#         else:
#             _CUSTOM_PRINT_FUNC("Error getting S3 URL")
#     else:
#         _CUSTOM_PRINT_FUNC("Error capturing image from USB camera")
#     # restart the stream    
#     return Response(camera.generate_video_stream_camera_USB(),
#                     mimetype='multipart/x-mixed-replace; boundary=frame')

# @app.route('/capture_c2')
# def capture_c2():
#     """Capture an image from the Raspberry Pi camera and upload to S3"""
#     # stop the stream temporarily
#     camera.stop_camera_RPi()
#     _CUSTOM_PRINT_FUNC("Capturing image from Raspberry Pi camera...")
#     image_num = s3_handler.get_num_of_files() + 1
#     path = camera.capture_store_image(image_num, 0)
#     if path:
#         _CUSTOM_PRINT_FUNC(f"Captured image: {path}")
#         s3_handler.upload_file(path, os.path.basename(path))
#         s3_url = s3_handler.get_s3_url(os.path.basename(path))
#         if s3_url:
#             _CUSTOM_PRINT_FUNC(f"S3 URL: {s3_url}")
#             mongo_db_handler.insert_image_data("plant image", s3_url, 1)
#             camera.remove_image(path)
#         else:
#             _CUSTOM_PRINT_FUNC("Error getting S3 URL")
#     else:
#         _CUSTOM_PRINT_FUNC("Error capturing image from Raspberry Pi camera")
#     # restart the stream
#     return Response(camera.generate_video_stream_camera_RPi(),
#                     mimetype='multipart/x-mixed-replace; boundary=frame')

# @app.route('/capture_c1_c2')
# def capture_c1_c2():
#     """Capture images from both cameras and upload to S3"""
#     # stop the streams temporarily
#     camera.stop_camera_USB()
#     camera.stop_camera_RPi()
#     _CUSTOM_PRINT_FUNC("Capturing images from both cameras...")
#     image_num = s3_handler.get_num_of_files() + 1
#     path_c1 = camera.capture_store_image(image_num, 0, True)
#     path_c2 = camera.capture_store_image(image_num, 0)
#     if path_c1 and path_c2:
#         _CUSTOM_PRINT_FUNC(f"Captured images: {path_c1}, {path_c2}")
#         s3_handler.upload_file(path_c1, os.path.basename(path_c1))
#         s3_handler.upload_file(path_c2, os.path.basename(path_c2))
        
#         s3_url_c1 = s3_handler.get_s3_url(os.path.basename(path_c1))
#         s3_url_c2 = s3_handler.get_s3_url(os.path.basename(path_c2))
        
#         if s3_url_c1 and s3_url_c2:
#             _CUSTOM_PRINT_FUNC(f"S3 URLs: {s3_url_c1}, {s3_url_c2}")
#             mongo_db_handler.insert_image_data("plant image", s3_url_c1, 0)
#             mongo_db_handler.insert_image_data("plant image", s3_url_c2, 1)
#             camera.remove_image(path_c1)
#             camera.remove_image(path_c2)
#         else:
#             _CUSTOM_PRINT_FUNC("Error getting S3 URLs")
#     else:
#         _CUSTOM_PRINT_FUNC("Error capturing images from cameras")
    
#     return "Images captured and uploaded successfully."


# Function to run Flask server in a thread
def run_flask():
    app.run(host='0.0.0.0', port=5000, threaded=True, debug=False)


if __name__ == "__main__":

    setpoints.set_control_thread_event("temperature", temperature_pause_event)
    setpoints.set_control_thread_event("light", light_pause_event)
    setpoints.set_control_thread_event("moisture", soil_pause_event)
    setpoints.set_soil_humidity_hysteresis(20.0)  # Set default hysteresis value
    setpoints.set_operation_mode("manual")  # Set initial operation mode to manual

    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # create the threads
    serial_logger_thread = threading.Thread(target=serial_logger_task, args=(env_sensors, get_last_sensor_update, env_actuators, setpoints, temperature_semaphore, light_semaphore, soil_semaphore, water_flow_semaphore, electricity_semaphore))
    temperature_thread = threading.Thread(target=temperature_sp_adjustment_task)
    light_thread = threading.Thread(target=light_sp_adjustment_task)
    soil_thread = threading.Thread(target=set_soil_moisture_setpoint_task)
    app_thread = threading.Thread(target=app_task)

    # start the threads
    temperature_thread.start()
    light_thread.start()
    soil_thread.start()
    app_thread.start()
    _CUSTOM_PRINT_FUNC("Starting serial logger thread...")    
    set_serial_log_enabled(True)  # Enable serial logging
    serial_logger_thread.start()

    # wait for the threads to finish
    serial_logger_thread.join()
    temperature_thread.join()
    light_thread.join()
    soil_thread.join()
    app_thread.join()
