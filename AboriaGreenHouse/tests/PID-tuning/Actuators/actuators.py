import gpiod
import time
import os
import board
import busio
import numpy as np

# Job IDs (Upper 3 bits of the first byte)
JOB_INIT_PWM = 0b000  # Initialize PWM (8 bytes)
JOB_SET_DUTY = 0b001  # Set PWM Duty Cycle (2 bytes)
JOB_RESTART = 0b010  # Restart ESP (0 bytes)
JOB_LED_TOG = 0b011  # Turn Onboard LED ON (0 bytes)
JOB_GET_STATE = 0b100  # Get PWM state (2 bytes)
JOB_GET_FREQ = 0b101  # Get PWM frequency (2 bytes)
JOB_GET_DUTY = 0b110  # Get PWM duty cycle (2 bytes)

# I2C Commands
ESP_READY = 0x01
ESP_NOT_READY = 0x02
ESP_OK = 0x03
ESP_NOT_OK = 0x04

class GH_Actuators:     
    def __init__(self, esp32_i2c_address: int, i2c_bus: busio.I2C = busio.I2C(board.SCL, board.SDA), frame_endianes: str = 'big'):
        self.__esp32_i2c_address = esp32_i2c_address
        self.__i2c_bus = i2c_bus
        self.__frame_endianes = frame_endianes
    
    def capture_image(self, path: str):
        # Initialize the camera
        with picamera2.Picamera2() as camera:
            camera.start()
            # Capture an image and save it
            camera.capture_file('image.jpg')
            print("Image captured and saved as 'image.jpg'.")
            # Stop the camera preview
            camera.stop()

    def restart_esp32(self) -> bool:
        try:
            while not self.__i2c_bus.try_lock():
                time.sleep(0.1)
            # create the frame to send to esp32
            frame = b''
            # create the first byte to send to esp32
            first_byte = JOB_RESTART << 5 | len(frame) & 0x1F
            frame = first_byte.to_bytes(1, self.__frame_endianes) + frame + b'\x00' * (32 - len(frame) - 1)
            print(f"Frame to send: {frame.hex()}")
            # send first byte
            self.__i2c_bus.writeto(self.__esp32_i2c_address, frame)
            # get the ready byte from esp32            
            time.sleep(0.1)
            self.__i2c_bus.unlock()
            return True            
        except Exception as e:
            print(f"Error restarting ESP32: {e}")
            self.__i2c_bus.unlock()
            return False        
    
    def toggle_esp32_onboard_led(self) -> bool:
        try:
            while not self.__i2c_bus.try_lock():
                time.sleep(0.1)
            # create the frame to send to esp32
            frame = b''
            # create the first byte to send to esp32
            first_byte = JOB_LED_TOG << 5 | len(frame) & 0x1F
            frame = first_byte.to_bytes(1, self.__frame_endianes) + frame + b'\x00' * (32 - len(frame) - 1)
            print(f"Frame to send: {frame.hex()}")
            # send first byte
            self.__i2c_bus.writeto(self.__esp32_i2c_address, frame)
            time.sleep(0.1)
            self.__i2c_bus.unlock()
            return True    
        except Exception as e:
            print(f"Error toggling ESP32 onboard LED: {e}")
            self.__i2c_bus.unlock()
            return False

    def __send_init_request(self, pin: int, channel: int, timer_src: int, frequency: int, duty_cycle: int, device_name: str) -> bool:
        try:
            while not self.__i2c_bus.try_lock():
                time.sleep(0.1)
            # create the frame to send to esp32
            frame = (frequency.to_bytes(4, self.__frame_endianes) + duty_cycle.to_bytes(2, self.__frame_endianes) + pin.to_bytes(1, self.__frame_endianes) + channel.to_bytes(1, self.__frame_endianes) + timer_src.to_bytes(1, self.__frame_endianes))
            # send command and frame size
            first_byte = JOB_INIT_PWM << 5 | len(frame) & 0x1F
            # complete the 32 bytes
            frame = first_byte.to_bytes(1, self.__frame_endianes) + frame + b'\x00' * (32 - len(frame) - 1)
            print(f"initializing {device_name} with frequency {frequency} and duty cycle {duty_cycle} at pin {pin} and channel {channel} for timer {timer_src}: {frame.hex()}")
            self.__i2c_bus.writeto(self.__esp32_i2c_address, frame)
            time.sleep(0.5)
            self.__i2c_bus.unlock()
            return True
        except Exception as e:
            print(f"Error sending init request: {e}")
            self.__i2c_bus.unlock()
            return False

    def __send_duty_cycle_update_request(self, duty_cycle: int, pin: int, channel: int, device_name: str) -> bool:
        try:
            while not self.__i2c_bus.try_lock():
                time.sleep(0.1)
            if duty_cycle < 0 or duty_cycle > 4096:
                print("Duty cycle must be between 0 and 4096")
                self.__i2c_bus.unlock()
                return False
            # create the frame to send to esp32
            frame = (duty_cycle.to_bytes(2, self.__frame_endianes) + pin.to_bytes(1, self.__frame_endianes) + channel.to_bytes(1, self.__frame_endianes))
            # create the first byte to send to esp32
            first_byte = JOB_SET_DUTY << 5 | len(frame) & 0x1F
            # complete the 32 bytes
            frame = first_byte.to_bytes(1, self.__frame_endianes) + frame + b'\x00' * (32 - len(frame) - 1)
            print(f"setting {device_name} to duty cycle {duty_cycle}: {frame.hex()}")
            # get the ready byte from esp32
            self.__i2c_bus.writeto(self.__esp32_i2c_address, frame) 
            time.sleep(0.1)
            self.__i2c_bus.unlock()
            return True
        except Exception as e:
            # print(f"Error sending duty cycle update request: {e}")
            self.__i2c_bus.unlock()
            return False          
        
    def setup_heater_esp32(self, pin: int, timer_src: int, channel: int, frequency: int, duty_cycle: int) -> bool:
        self.__heater_pin = pin
        self.__heater_channel = channel
        self.__heater_frequency = frequency
        self.__heater_duty_cycle = duty_cycle
        self.__heater_timer_src = timer_src
        try:
            return self.__send_init_request(pin, channel, timer_src, frequency, duty_cycle, "heater")
        except Exception as e:
            # print(f"Error setting up heater: {e}")
            return False

    def set_heater_duty_cycle(self, duty_cycle: int) -> bool:
        try:
            return self.__send_duty_cycle_update_request(duty_cycle, self.__heater_pin, self.__heater_channel, "heater")        
        except Exception as e:
            # print(f"Error setting heater duty cycle: {e}")
            return False           
    
    def setup_heater_fan_esp32(self, pin: int, channel: int, timer_src: int, frequency: int, duty_cycle: int) -> bool:
        self.__heater_fan_pin = pin
        self.__heater_fan_channel = channel
        self.__heater_fan_frequency = frequency
        self.__heater_fan_duty_cycle = duty_cycle
        self.__heater_fan_timer_src = timer_src
        try:
            return self.__send_init_request(pin, channel, timer_src, frequency, duty_cycle, "heater_fan")
        except Exception as e:
            # print(f"Error setting up heater fan: {e}")
            return False
    
    def set_heater_fan_duty_cycle(self, duty_cycle: int) -> bool:
        try:
            return self.__send_duty_cycle_update_request(duty_cycle, self.__heater_fan_pin, self.__heater_fan_channel, "heater_fan")
        except Exception as e:
            # print(f"Error setting heater fan duty cycle: {e}")
            return False

    def setup_fan_esp32(self, pin: int, channel: int, timer_src: int, frequency: int, duty_cycle: int) -> bool:
        self.__fan_pin = pin
        self.__fan_channel = channel
        self.__fan_frequency = frequency
        self.__fan_duty_cycle = duty_cycle
        self.__fan_timer_src = timer_src
        try:
            return self.__send_init_request(pin, channel, timer_src, frequency, duty_cycle, "fan")
        except Exception as e:
            # print(f"Error setting up fan: {e}")
            return False
    
    def set_fan_duty_cycle(self, duty_cycle: int) -> bool:
        try:
            return self.__send_duty_cycle_update_request(duty_cycle, self.__fan_pin, self.__fan_channel, "fan")
        except Exception as e:
            # print(f"Error setting fan duty cycle: {e}")
            return False
    
    def setup_light_strip_1_esp32(self, pin: int, channel: int, timer_src: int, frequency: int, duty_cycle: int) -> bool:
        self.__light_pin = pin
        self.__light_channel = channel
        self.__light_frequency = frequency
        self.__light_duty_cycle = duty_cycle
        self.__light_timer_src = timer_src
        try:
            return self.__send_init_request(pin, channel, timer_src, frequency, duty_cycle, "light_strip_1")
        except Exception as e:
            # print(f"Error setting up light: {e}")
            return False
    
    def set_light_strip_1_duty_cycle(self, duty_cycle: int) -> bool:
        try:
            return self.__send_duty_cycle_update_request(duty_cycle, self.__light_pin, self.__light_channel, "light_strip_1")
        except Exception as e:
            # print(f"Error setting light duty cycle: {e}")
            return False
    
    def setup_light_strip_2_esp32(self, pin: int, channel: int, timer_src: int, frequency: int, duty_cycle: int) -> bool:
        self.__light_strip_2_pin = pin
        self.__light_strip_2_channel = channel
        self.__light_strip_2_frequency = frequency
        self.__light_strip_2_duty_cycle = duty_cycle
        self.__light_strip_2_timer_src = timer_src
        try:
            return self.__send_init_request(pin, channel, timer_src, frequency, duty_cycle, "light_strip_2")
        except Exception as e:
            # print(f"Error setting up light strip 2: {e}")
            return False
        
    def set_light_strip_2_duty_cycle(self, duty_cycle: int) -> bool:
        try:
            return self.__send_duty_cycle_update_request(duty_cycle, self.__light_strip_2_pin, self.__light_strip_2_channel, "light_strip_2")
        except Exception as e:
            # print(f"Error setting light strip 2 duty cycle: {e}")
            return False

    def setup_water_pump_esp32(self, pin: int, channel: int, timer_src: int, frequency: int, duty_cycle: int) -> bool:
        self.__water_pump_pin = pin
        self.__water_pump_channel = channel
        self.__water_pump_frequency = frequency
        self.__water_pump_duty_cycle = duty_cycle
        self.__water_pump_timer_src = timer_src
        try:
            return self.__send_init_request(pin, channel, timer_src, frequency, duty_cycle, "water_pump")
        except Exception as e:
            # print(f"Error setting up water pump: {e}")
            return False
    
    def set_water_pump_duty_cycle(self, duty_cycle: int) -> bool:
        try:
            return self.__send_duty_cycle_update_request(duty_cycle, self.__water_pump_pin, self.__water_pump_channel, "water_pump")
        except Exception as e:
            # print(f"Error setting water pump duty cycle: {e}")
            return False

    # get current actuator duty cycles
    def get_water_pump_duty_cycle(self) -> int:
        try:
            return self.__water_pump_duty_cycle
        except AttributeError:
            print("Water pump not initialized.")
            return 0
    
    def get_heater_duty_cycle(self) -> int:
        try:
            return self.__heater_duty_cycle
        except AttributeError:
            print("Heater not initialized.")
            return 0
    
    def get_heater_fan_duty_cycle(self) -> int:
        try:
            return self.__heater_fan_duty_cycle
        except AttributeError:
            print("Heater fan not initialized.")
            return 0
    
    def get_fan_duty_cycle(self) -> int:
        try:
            return self.__fan_duty_cycle
        except AttributeError:
            print("Fan not initialized.")
            return 0
        
    def get_light_strip_1_duty_cycle(self) -> int:
        try:
            return self.__light_duty_cycle
        except AttributeError:
            print("Light not initialized.")
            return 0
        
    def get_light_strip_2_duty_cycle(self) -> int:
        try:
            return self.__light_strip_2_duty_cycle
        except AttributeError:
            print("Light strip 2 not initialized.")
            return 0