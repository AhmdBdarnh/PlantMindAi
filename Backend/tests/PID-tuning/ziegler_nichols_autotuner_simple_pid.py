#!/usr/bin/env python3
"""
PID Auto-Tuning Script using Ziegler-Nichols Closed-Loop Method
For Raspberry Pi 5 with temperature and light control systems

This script implements the Ziegler-Nichols closed-loop method for PID tuning:
1. Increase Kp until system oscillates with constant amplitude (finding ultimate gain Ku)
2. Measure the oscillation period (Pu)
3. Calculate PID parameters based on Ziegler-Nichols rules
"""

import os
import time
import datetime
import argparse
import busio
import numpy as np
import matplotlib.pyplot as plt
from collections import deque
from simple_pid import PID  # Import simple-pid
from Actuators.actuators import GH_Actuators
import adafruit_ads1x15.ads1115 as ads
from Sensors.light import LightSensor
import board
from Sensors.air import AirSensor

# ===== HARDWARE INTERFACE TEMPLATES =====
# Replace these template functions with your actual hardware interface code
airTemp = AirSensor()
airTemp.set_dht22_pin(board.D26)  # Set the pin for DHT22 sensor

i2cBus = busio.I2C(board.SCL, board.SDA)
act = GH_Actuators(esp32_i2c_address=0x30, i2c_bus=i2cBus, frame_endianes='big')
print("Initializing actuators...", end='')
act.restart_esp32()
last_date_time = datetime.datetime.now()
while datetime.datetime.now() - last_date_time < datetime.timedelta(seconds=10):
    print(".", end='')
    time.sleep(1)

print(" done.")

# pin 16, channel 0, frequency 5000 Hz, duty cycle 0
while not act.setup_light_strip_1_esp32(pin=16, channel=0, timer_src=0, frequency=5000, duty_cycle=0):
    print("sending light strip 1 setup command again...")
    time.sleep(5)

time.sleep(1)

while not act.setup_light_strip_1_esp32(pin=15, channel=5, timer_src=0, frequency=5000, duty_cycle=0):
    print("sending light strip 2 setup command again...")
    time.sleep(5)

time.sleep(1)

# pin 17, channel 1, frequency 10 Hz, duty cycle 0
while not act.setup_heater_esp32(pin=17, channel=1, timer_src=1, frequency=50, duty_cycle=0):
    print("sending heater setup command again...")
    time.sleep(5)

time.sleep(1)
# pin 18, channel 2, frequency 25000 Hz, duty cycle 0
while not act.setup_heater_fan_esp32(pin=18, channel=2, timer_src=0, frequency=5000, duty_cycle=0):
    print("sending heater fan setup command again...")
    time.sleep(5)

time.sleep(1)
# pin 19, channel 3, frequency 25000 Hz, duty cycle 0
while not act.setup_fan_esp32(pin=19, channel=3, timer_src=0, frequency=5000, duty_cycle=0):
    print("sending fan setup command again...")
    time.sleep(5)


def read_temperature():
    """
    Template function to read temperature from DHT22 sensor
    Returns: float - current temperature in degrees Celsius
    """
    # TODO: Replace with actual DHT22 reading code
    # Example:
    # import Adafruit_DHT
    # humidity, temperature = Adafruit_DHT.read_retry(Adafruit_DHT.DHT22, DHT22_PIN)
    # return temperature
    return airTemp.get_air_temperature_C()  # Returns temperature in Celsius
    # For testing, this returns a simulated value
    # Simulate some noise and slight drift for testing
   

def read_light_level():
    """
    Template function to read light level from light sensor
    Returns: float - current light level (units depend on your sensor)
    """
    # TODO: Replace with actual light sensor reading code
    # Example:
    # import board
    # import busio
    # import adafruit_tsl2591
    # i2c = busio.I2C(board.SCL, board.SDA)
    # sensor = adafruit_tsl2591.TSL2591(i2c)
    # return sensor.lux

    global i2cBus
    ads_channels = [ads.P0, ads.P1, ads.P2, ads.P3]
    lightSensor = LightSensor(ads_sensor=ads.ADS1115(i2cBus), ads_channels=ads_channels, I2C=i2cBus)
    lightSensor.set_light_intensity_ads1115_channel(1)  # Set the channel for light sensor    
    lightLux = lightSensor.get_light_intensity()
    return lightLux  # Returns light intensity in lux

    # For testing, this returns a simulated value
    # Simulate some noise and slight drift for testing


def set_heater_power(power_level):
    """
    Template function to control heater
    Args:
        power_level: int - PWM value (0-4095)
    """

    # Example:
    # from adafruit_pca9685 import PCA9685
    # pca = PCA9685(i2c_bus)
    # pca.channels[HEATER_CHANNEL].duty_cycle = power_level
    while not act.set_heater_duty_cycle(power_level):  # Set heater power level (0-4095)
        print("sending heater power command again...")
        time.sleep(0.1)

    while not act.set_heater_fan_duty_cycle(power_level):  # Set fan power level (0-4095)
        print("sending heater fan power command again...")
        time.sleep(0.1)


def set_fan_power(power_level):
    """
    Template function to control fan
    Args:
        power_level: int - PWM value (0-4095)
    """
    # TODO: Replace with actual fan control code
    # Example:
    # from adafruit_pca9685 import PCA9685
    # pca = PCA9685(i2c_bus)
    # pca.channels[FAN_CHANNEL].duty_cycle = power_level
    while not act.set_fan_duty_cycle(power_level):  # Set fan power level (0-4095)
        print("sending fan power command again...")
        time.sleep(0.1)
    # For testing, just print the value and simulate effect


def set_led_power(power_level):
    """
    Template function to control LED strip
    Args:
        power_level: int - PWM value (0-4095)
    """
    # TODO: Replace with actual LED control code
    # Example:
    # from adafruit_pca9685 import PCA9685
    # pca = PCA9685(i2c_bus)
    # pca.channels[LED_CHANNEL].duty_cycle = power_level
    while not act.set_light_strip_1_duty_cycle(power_level):  # Set LED power level (0-4095)
        print("sending light strip 1 power command again...")
        time.sleep(0.1)

    while not act.set_light_strip_2_duty_cycle(power_level):  # Set LED power level (0-4095)
        print("sending light strip 2 power command again...")
        time.sleep(0.1)
    # For testing, just print the value and simulate effect

def set_temperature_dual_actuator(control_value):
    """
    Combined function to control temperature using both heater and fan
    Args:
        control_value: float - Control value (-4095 to 4095)
                      Positive values control heater, negative values control fan
    """
    # Ensure control_value is within range
    control_value = max(min(control_value, 4095), -4095)
    
    if control_value >= 0:
        # Positive control value: use heater, turn off fan
        heater_power = int(control_value)
        fan_power = 0
        set_heater_power(heater_power)
        set_fan_power(fan_power)
        return f"Heater: {heater_power}/4095, Fan: 0/4095"
    else:
        # Negative control value: use fan, turn off heater
        fan_power = int(abs(control_value))
        heater_power = 0
        set_heater_power(heater_power)
        set_fan_power(fan_power)
        return f"Heater: 0/4095, Fan: {fan_power}/4095"

# ===== ZIEGLER-NICHOLS AUTOTUNER =====

class ZieglerNicholsAutotuner:
    """
    Implements the Ziegler-Nichols closed-loop method for PID tuning using simple-pid
    """
    def __init__(self, sensor_func, actuator_func, setpoint, 
                 min_output=-4095, max_output=4095,  # Default to bidirectional control
                 start_kp=0.1, kp_step=0.1,
                 sample_time=0.5, window_size=100,
                 oscillation_threshold=0.05, min_oscillations=4,
                 max_test_time=300, safety_limits=None,
                 dual_actuator=False):
        """
        Initialize the autotuner
        
        Args:
            sensor_func: function - reads the process variable
            actuator_func: function - controls the actuator
            setpoint: float - desired process variable value
            min_output: int - minimum actuator value
            max_output: int - maximum actuator value
            start_kp: float - initial proportional gain
            kp_step: float - step size for increasing Kp
            sample_time: float - time between samples (seconds)
            window_size: int - number of samples to keep for analysis
            oscillation_threshold: float - threshold for detecting oscillations
            min_oscillations: int - minimum number of oscillations required
            max_test_time: float - maximum test duration (seconds)
            safety_limits: tuple - (min, max) safety limits for process variable
            dual_actuator: bool - whether using dual actuator mode (bidirectional control)
        """
        self.sensor_func = sensor_func
        self.actuator_func = actuator_func
        self.setpoint = setpoint
        self.min_output = min_output
        self.max_output = max_output
        self.start_kp = start_kp
        self.kp_step = kp_step
        self.sample_time = sample_time
        self.window_size = window_size
        self.oscillation_threshold = oscillation_threshold
        self.min_oscillations = min_oscillations
        self.max_test_time = max_test_time
        self.safety_limits = safety_limits
        self.dual_actuator = dual_actuator
        
        # Data storage
        self.times = []
        self.pv_values = []
        self.output_values = []
        self.kp_values = []
        
        # Results
        self.ku = None
        self.pu = None
        self.pid_params = None
    
    def _check_safety(self, pv):
        """Check if process variable is within safety limits"""
        if self.safety_limits is None:
            return True
        
        min_limit, max_limit = self.safety_limits
        return min_limit <= pv <= max_limit
    
    def _detect_oscillations(self, values):
        """
        Detect sustained oscillations in the process variable
        Returns: (is_oscillating, period)
        """
        if len(values) < self.window_size:
            return False, 0
        
        # Get the last window_size values
        recent_values = values[-self.window_size:]
        
        # Calculate mean and standard deviation
        mean_value = np.mean(recent_values)
        std_value = np.std(recent_values)
        
        # Check if standard deviation is significant relative to mean or setpoint
        if std_value < self.oscillation_threshold * max(abs(mean_value), abs(self.setpoint), 1e-6):
             return False, 0
        
        # Find peaks and troughs
        peaks = []
        troughs = []
        
        for i in range(1, len(recent_values) - 1):
            if (recent_values[i] > recent_values[i-1] and 
                recent_values[i] > recent_values[i+1]):
                peaks.append(i)
            elif (recent_values[i] < recent_values[i-1] and 
                  recent_values[i] < recent_values[i+1]):
                troughs.append(i)
        
        # Check if we have enough oscillations
        if len(peaks) < self.min_oscillations or len(troughs) < self.min_oscillations:
            return False, 0
        
        # Calculate average period
        peak_periods = []
        for i in range(1, len(peaks)):
            peak_periods.append(peaks[i] - peaks[i-1])
        
        trough_periods = []
        for i in range(1, len(troughs)):
            trough_periods.append(troughs[i] - troughs[i-1])
        
        # Average the periods
        if peak_periods and trough_periods:
            avg_period_samples = (np.mean(peak_periods) + np.mean(trough_periods)) / 2
            period_seconds = avg_period_samples * self.sample_time
            
            # Check if period is reasonably stable
            all_periods = peak_periods + trough_periods
            if np.std(all_periods) / avg_period_samples > 0.3: # Check for high variation
                return False, 0
                
            return True, period_seconds
        
        return False, 0
    
    def run(self, verbose=True, plot_results=True):
        """
        Run the autotuning process
        
        Args:
            verbose: bool - print progress messages
            plot_results: bool - generate plots after tuning
            
        Returns:
            dict - PID parameters for different controller types
        """
        if verbose:
            print(f"Starting Ziegler-Nichols autotuning with setpoint: {self.setpoint}")
            print(f"Initial Kp: {self.start_kp}, Step size: {self.kp_step}")
            if self.dual_actuator:
                print(f"Using dual actuator mode (bidirectional control)")
            print("Press Ctrl+C to stop early.")
        
        # Initialize P-only controller using simple-pid
        controller = PID(
            Kp=self.start_kp,
            Ki=0.0,
            Kd=0.0,
            setpoint=self.setpoint,
            output_limits=(self.min_output, self.max_output),
            sample_time=self.sample_time, # Use the autotuner's sample time
            auto_mode=True # Start enabled
        )
        
        # Initialize data collection
        self.times = []
        self.pv_values = []
        self.output_values = []
        self.kp_values = []
        
        # Start time
        start_time = time.time()
        last_sample_time = start_time
        last_print_time = start_time
        kp_increased_msg = ""
        actuator_status = ""
        
        try:
            # Main tuning loop
            while time.time() - start_time < self.max_test_time:
                current_time = time.time()
                
                # Check if it's time for a new sample
                if current_time - last_sample_time >= self.sample_time:
                    # Read process variable
                    pv = self.sensor_func()
                    
                    # Safety check
                    if not self._check_safety(pv):
                        if verbose:
                            print(f"\nSafety limit reached! PV: {pv:.2f}")
                        break
                    
                    # Update controller using simple-pid
                    output = controller(pv)
                    
                    # Apply control output
                    if self.dual_actuator:
                        actuator_status = self.actuator_func(output)
                    else:
                        self.actuator_func(int(output))
                        actuator_status = f"Output: {int(output)}/{self.max_output}"
                    
                    # Record data
                    elapsed_time = current_time - start_time
                    self.times.append(elapsed_time)
                    self.pv_values.append(pv)
                    self.output_values.append(output)
                    self.kp_values.append(controller.Kp) # Get Kp from simple-pid controller
                    
                    # Check for oscillations
                    is_oscillating, period = self._detect_oscillations(self.pv_values)
                    
                    if is_oscillating:
                        if verbose:
                            # Clear terminal before final message
                            os.system('cls' if os.name == 'nt' else 'clear')
                            print(f"Sustained oscillations detected at Kp={controller.Kp:.4f}")
                            print(f"Oscillation period (Pu): {period:.2f} seconds")
                        
                        # We found the ultimate gain (Ku) and period (Pu)
                        self.ku = controller.Kp # Use controller.Kp
                        self.pu = period
                        break
                    
                    # If not oscillating and we have enough data, increase Kp
                    if len(self.pv_values) >= self.window_size and not is_oscillating:
                        controller.Kp += self.kp_step # Update Kp in simple-pid controller
                        kp_increased_msg = f"Increased Kp to {controller.Kp:.4f}"
                    else:
                        kp_increased_msg = "" # Clear message if Kp wasn't increased
                    
                    # Update last sample time
                    last_sample_time = current_time

                    # Print status periodically (e.g., every second)
                    if verbose and (current_time - last_print_time >= 1.0):
                        os.system('cls' if os.name == 'nt' else 'clear')
                        print(f"--- Ziegler-Nichols Autotuning --- Setpoint: {self.setpoint:.2f} ---")
                        print(f"Elapsed Time: {elapsed_time:.1f}s / {self.max_test_time:.0f}s")
                        print(f"Current Kp:   {controller.Kp:.4f}")
                        print(f"Sensor Value: {pv:.2f}")
                        if self.dual_actuator:
                            print(f"Control: {actuator_status}")
                        else:
                            print(f"PID Output:   {output:.2f} ({int(output)}/{self.max_output})")
                        if kp_increased_msg:
                            print(kp_increased_msg)
                        print("\n(Waiting for sustained oscillations... Press Ctrl+C to stop)")
                        last_print_time = current_time
                
                # Small delay to prevent CPU overload
                time.sleep(0.01)
        
        except KeyboardInterrupt:
            if verbose:
                print("\nAutotuning stopped by user.")
        
        finally:
            # Turn off the actuator
            if self.dual_actuator:
                self.actuator_func(0)  # Zero is neutral for dual actuator
            else:
                self.actuator_func(0)  # Zero for single actuator
            print("Actuator turned off.")
        
        # Calculate PID parameters if oscillations were found
        if self.ku is not None and self.pu is not None and self.pu > 0:
            self.pid_params = self._calculate_pid_parameters()
            
            if verbose:
                print("\nZiegler-Nichols tuning results:")
                print(f"Ultimate gain (Ku): {self.ku:.4f}")
                print(f"Oscillation period (Pu): {self.pu:.4f} seconds")
                print("\nRecommended PID parameters:")
                for controller_type, params in self.pid_params.items():
                    print(f"{controller_type}: Kp={params['Kp']:.4f}, Ki={params['Ki']:.4f}, Kd={params['Kd']:.4f}")
        else:
            if verbose:
                print("\nAutotuning failed or stopped before completion.")
                print("Reason: No sustained oscillations detected or Pu is zero, or stopped early.")
                print("Try adjusting parameters: --start-kp, --kp-step, --max-time, oscillation_threshold, or check sensor/actuator functions.")
        
        # Generate plots if requested and data exists
        if plot_results and self.times:
            self._plot_results()
        
        return self.pid_params
    
    def _calculate_pid_parameters(self):
        """
        Calculate PID parameters using Ziegler-Nichols rules
        Returns: dict of PID parameters for different controller types
        """
        if self.ku is None or self.pu is None or self.pu <= 0:
            return None
        
        # Ziegler-Nichols rules for different controller types
        params = {
            "P": {
                "Kp": 0.5 * self.ku,
                "Ki": 0.0,
                "Kd": 0.0
            },
            "PI": {
                "Kp": 0.45 * self.ku,
                "Ki": 0.54 * self.ku / self.pu,
                "Kd": 0.0
            },
            "PID": {
                "Kp": 0.6 * self.ku,
                "Ki": 1.2 * self.ku / self.pu,
                "Kd": 0.075 * self.ku * self.pu
            },
            "Pessen Integral Rule": {
                "Kp": 0.7 * self.ku,
                "Ki": 1.75 * self.ku / self.pu,
                "Kd": 0.105 * self.ku * self.pu
            },
            "Some Overshoot": {
                "Kp": 0.33 * self.ku,
                "Ki": 0.66 * self.ku / self.pu,
                "Kd": 0.11 * self.ku * self.pu
            },
            "No Overshoot": {
                "Kp": 0.2 * self.ku,
                "Ki": 0.4 * self.ku / self.pu,
                "Kd": 0.066 * self.ku * self.pu
            }
        }
        
        return params
    
    def _plot_results(self):
        """Generate plots of the autotuning process"""
        try:
            plt.figure(figsize=(12, 10))
            
            # Plot process variable
            plt.subplot(3, 1, 1)
            plt.plot(self.times, self.pv_values)
            plt.axhline(y=self.setpoint, color='r', linestyle='--', label='Setpoint')
            plt.title('Process Variable')
            plt.xlabel('Time (s)')
            plt.ylabel('Value')
            plt.grid(True)
            plt.legend()
            
            # Plot control output
            plt.subplot(3, 1, 2)
            plt.plot(self.times, self.output_values)
            plt.title('Control Output')
            if self.dual_actuator:
                plt.ylabel(f'Output ({self.min_output}-{self.max_output})')
                plt.axhline(y=0, color='k', linestyle='--', label='Neutral')
            else:
                plt.ylabel(f'Output ({self.min_output}-{self.max_output})')
            plt.grid(True)
            plt.legend()
            
            # Plot Kp value
            plt.subplot(3, 1, 3)
            plt.plot(self.times, self.kp_values)
            if self.ku is not None:
                plt.axhline(y=self.ku, color='r', linestyle='--', label='Ultimate Gain (Ku)')
            plt.title('Proportional Gain (Kp)')
            plt.xlabel('Time (s)')
            plt.ylabel('Kp')
            plt.grid(True)
            plt.legend()
            
            plt.tight_layout()
            plot_filename = 'ziegler_nichols_tuning_results.png'
            plt.savefig(plot_filename)
            print(f"Plot saved to {plot_filename}")
            plt.close()
        except Exception as e:
            print(f"Error generating plot: {e}")

# ===== MAIN FUNCTION =====

def main():
    """Main function to run the autotuner"""
    parser = argparse.ArgumentParser(description='PID Autotuning using Ziegler-Nichols method (simple-pid)')
    parser.add_argument('--system', choices=['temperature', 'light'], required=True,
                        help='System to tune (temperature or light)')
    parser.add_argument('--setpoint', type=float, required=True,
                        help='Setpoint value for the system')
    parser.add_argument('--start-kp', type=float, default=0.1,
                        help='Initial proportional gain')
    parser.add_argument('--kp-step', type=float, default=0.1,
                        help='Step size for increasing Kp')
    parser.add_argument('--sample-time', type=float, default=0.5,
                        help='PID sample time in seconds')
    parser.add_argument('--max-time', type=float, default=300,
                        help='Maximum test duration in seconds')
    parser.add_argument('--min-safety', type=float, default=None,
                        help='Minimum safety limit for process variable')
    parser.add_argument('--max-safety', type=float, default=None,
                        help='Maximum safety limit for process variable')
    parser.add_argument('--no-plot', action='store_true',
                        help='Disable plotting of results')
    parser.add_argument('--verbose', action=argparse.BooleanOptionalAction, default=True,
                        help='Enable/disable verbose output (terminal clearing)')
    parser.add_argument('--dual-actuator', action='store_true',
                        help='Use dual actuator mode for temperature (heater and fan)')

    args = parser.parse_args()
    
    # Set up safety limits if provided
    safety_limits = None
    if args.min_safety is not None and args.max_safety is not None:
        safety_limits = (args.min_safety, args.max_safety)
    
    # Configure system-specific functions
    if args.system == 'temperature':
        sensor_func = read_temperature
        
        if args.dual_actuator:
            # Use the dual actuator function for temperature control
            actuator_func = set_temperature_dual_actuator
            output_range = (-4095, 4095)  # Bidirectional control
            print(f"Tuning temperature control system with DUAL ACTUATORS (heater and fan)")
            print(f"Setpoint: {args.setpoint}°C")
            print(f"Output range: {output_range[0]} to {output_range[1]} (negative=fan, positive=heater)")
        else:
            # Use only the heater for temperature control
            actuator_func = set_heater_power
            output_range = (0, 4095)  # Unidirectional control
            print(f"Tuning temperature control system (using heater only) with setpoint: {args.setpoint}°C")
    else:  # light
        sensor_func = read_light_level
        actuator_func = set_led_power
        output_range = (0, 4095)  # Unidirectional control
        print(f"Tuning light control system with setpoint: {args.setpoint}")
    
    # Create and run autotuner
    autotuner = ZieglerNicholsAutotuner(
        sensor_func=sensor_func,
        actuator_func=actuator_func,
        setpoint=args.setpoint,
        min_output=output_range[0],
        max_output=output_range[1],
        start_kp=args.start_kp,
        kp_step=args.kp_step,
        sample_time=args.sample_time,
        max_test_time=args.max_time,
        safety_limits=safety_limits,
        dual_actuator=args.dual_actuator
    )
    
    # Run the autotuning process
    pid_params = autotuner.run(verbose=args.verbose, plot_results=not args.no_plot)
    
    # Save results to file if tuning was successful
    if pid_params:
        output_filename = f"{args.system}_pid_parameters_simple_pid.txt"
        with open(output_filename, "w") as f:
            f.write(f"# PID parameters for {args.system} control (using simple-pid)\n")
            f.write(f"# Setpoint: {args.setpoint}\n")
            f.write(f"# Ultimate gain (Ku): {autotuner.ku:.6f}\n")
            f.write(f"# Oscillation period (Pu): {autotuner.pu:.6f} seconds\n\n")
            
            for controller_type, params in pid_params.items():
                f.write(f"## {controller_type}\n")
                f.write(f"Kp = {params['Kp']:.6f}\n")
                f.write(f"Ki = {params['Ki']:.6f}\n")
                f.write(f"Kd = {params['Kd']:.6f}\n\n")
        
        print(f"PID parameters saved to {output_filename}")

if __name__ == "__main__":
    main()
