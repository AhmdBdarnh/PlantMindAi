import time
import threading
import gpiod
from datetime import timedelta
from utils.utils import _CUSTOM_PRINT_FUNC

class WaterFlowSensor:
    """
    Class to handle water flow sensor operations including:
    - Pulse counting
    - Flow rate calculation
    - Total water amount tracking
    """
    def __init__(self):
        self.__water_flow_running = False
        self.__flow_rate = 0.0
        self.__water_amount = 0.0
        self.__counter = 0
        self.__chip = gpiod.chip('gpiochip4')
        self.__water_flow_sensor_pin = None
        self.__PULSES_PER_LITRE = 450.0  # pulses per litre for the flow sensor

        # read the last water amount from file if it exists
        try:
            with open('consumption/water_amount.txt', 'r') as file:
                self.__water_amount = float(file.read().strip())
        except FileNotFoundError:
            self.__water_amount = 0.0
        except ValueError:
            _CUSTOM_PRINT_FUNC("Error reading water amount from file. Initializing to 0.0.")
            self.__water_amount = 0.0


    def set_water_flow_sensor_pin(self, pin):
        """Set up the water flow sensor with the specified pin"""
        self.__water_flow_sensor_pin = self.__chip.get_line(pin)        
        config = gpiod.line_request()
        config.consumer = "Water_Flow"
        config.request_type = gpiod.line_request.EVENT_BOTH_EDGES        
        self.__water_flow_sensor_pin.request(config=config, default_val=0)
        
        self.__counter = 0
        self.__water_flow_running = True
        
        # Start threads for pulse counting and flow rate calculation
        self.__water_flow_thread = threading.Thread(
            target=self.__water_flow_pulse_counter, 
            daemon=True
        )
        self.__water_flow_thread.start()

        self.__flow_rate_thread = threading.Thread(
            target=self.__calculate_flow_rate, 
            daemon=True
        )
        self.__flow_rate_thread.start()

    def __water_flow_pulse_counter(self):
        """Thread function to count pulses from the water flow sensor"""
        while self.__water_flow_running:
            if self.__water_flow_sensor_pin.event_wait(timedelta(seconds=1)):
                event = self.__water_flow_sensor_pin.event_read()
                if event.event_type == gpiod.line_event.RISING_EDGE:
                    self.__counter += 1

    def __calculate_flow_rate(self):
        """Thread function to calculate flow rate based on pulse count"""
        start_time = time.time()
        while self.__water_flow_running:
            time.sleep(1)
            elapsed_time = time.time() - start_time
            self.__flow_rate = (self.__counter / self.__PULSES_PER_LITRE) / (elapsed_time / 60.0)  # litres per minute
            self.__counter = 0  # reset the counter for the next interval
            start_time = time.time()  # reset the start time for the next interval

    def get_water_flow_rate(self):
        """Get water flow rate in liters per minute"""
        try:
            # calculate amount of water in liters
            self.__water_amount += self.__flow_rate / 60.0  # convert L/min to L/s

            # save water amount in local file
            with open('consumption/water_amount.txt', 'w') as file:
                file.write(f'{self.__water_amount:.2f}')

            return self.__flow_rate
        except RuntimeError as err:
            _CUSTOM_PRINT_FUNC(f'Sensor Error: {err.args[0]}')
            return 0    
        except KeyboardInterrupt:
            self.stop()

    def get_total_water_amount(self):
        """Get total water amount in liters"""
        return self.__water_amount

    def stop(self):
        """Stop the water flow sensor threads"""
        self.__water_flow_running = False
        if self.__water_flow_thread.is_alive():
            self.__water_flow_thread.join()
        if self.__flow_rate_thread.is_alive():
            self.__flow_rate_thread.join()
        if self.__water_flow_sensor_pin:
            self.__water_flow_sensor_pin.release()

    def reset_water_amount(self):
        """Reset the total water amount to zero"""
        self.__water_amount = 0.0
        with open('consumption/water_amount.txt', 'w') as file:
            file.write('0.00')
        _CUSTOM_PRINT_FUNC("Water amount reset to 0.0 liters.")

    