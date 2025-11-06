#!/usr/bin/env python3
"""
Manual PID Tuner GUI for Light Control

Allows real-time adjustment of Kp, Ki, Kd and Setpoint for a light PID controller,
and displays sensor readings and actuator output.

Integrates hardware functions STRICTLY as provided by the user.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import datetime
import os
import board
import busio
import adafruit_ads1x15.ads1115 as ads
from simple_pid import PID

# Attempt to import user's hardware modules
try:
    from Actuators.actuators import GH_Actuators
    from Sensors.light import LightSensor
    # from Sensors.air import AirSensor # Not needed for light control
    HARDWARE_MODULES_FOUND = True
except ImportError as e:
    print(f"Error importing hardware modules: {e}")
    print("Please ensure Actuators/actuators.py and Sensors/light.py are accessible.")
    HARDWARE_MODULES_FOUND = False
    # Define dummy classes if import fails, so GUI can still load (but won't work)
    class GH_Actuators:
        def __init__(self, *args, **kwargs): pass
        def restart_esp32(self): pass
        def setup_light_strip_1_esp32(self, *args, **kwargs): return True
        def setup_light_strip_2_esp32(self, *args, **kwargs): return True
        def set_light_strip_1_duty_cycle(self, *args, **kwargs): return True
        def set_light_strip_2_duty_cycle(self, *args, **kwargs): return True # Assuming this exists based on user code
        def setup_heater_esp32(self, *args, **kwargs): return True
        def setup_heater_fan_esp32(self, *args, **kwargs): return True
        def setup_fan_esp32(self, *args, **kwargs): return True

    class LightSensor:
        def __init__(self, *args, **kwargs): pass
        def set_light_intensity_ads1115_channel(self, *args, **kwargs): pass
        def get_light_intensity(self): return 1000.0 # Dummy value

# --- Global Hardware Objects ---
i2cBus = None
act = None
lightSensor = None

# --- Hardware Functions & Initialization (Strictly from user script) ---
def initialize_hardware():
    """Initializes I2C, Actuators, and Light Sensor STRICTLY based on user script."""
    global i2cBus, act, lightSensor
    if not HARDWARE_MODULES_FOUND:
        print("Hardware modules not found, cannot initialize.")
        return False

    try:
        print("Initializing hardware...")
        i2cBus = busio.I2C(board.SCL, board.SDA)
        act = GH_Actuators(esp32_i2c_address=0x30, i2c_bus=i2cBus, frame_endianes='big')
        print("Initializing actuators (restarting ESP32)...", end='')
        act.restart_esp32()
        last_date_time = datetime.datetime.now()
        while datetime.datetime.now() - last_date_time < datetime.timedelta(seconds=10):
            print(".", end='')
            time.sleep(1)
        print(" done.")

        print("Configuring actuators...")
        # Light Strip 1 setup (Pin 16, Channel 0)
        while not act.setup_light_strip_1_esp32(pin=16, channel=0, timer_src=0, frequency=5000, duty_cycle=0):
            print("sending light strip 1 setup command again...")
            time.sleep(5)
        time.sleep(1)

        # Light Strip 2 setup (Pin 15, Channel 5)
        # Using the exact (potentially mistaken) second call from user script
        while not act.setup_light_strip_2_esp32(pin=15, channel=5, timer_src=0, frequency=5000, duty_cycle=0):
            print("sending light strip 2 setup command again...") # User script had this print msg
            time.sleep(5)
        time.sleep(1)

        # # Setup other actuators exactly as in user script
        # while not act.setup_heater_esp32(pin=17, channel=1, timer_src=1, frequency=50, duty_cycle=0):
        #     print("sending heater setup command again...")
        #     time.sleep(5)
        # time.sleep(1)
        # while not act.setup_heater_fan_esp32(pin=18, channel=2, timer_src=0, frequency=5000, duty_cycle=0):
        #     print("sending heater fan setup command again...")
        #     time.sleep(5)
        # time.sleep(1)
        # while not act.setup_fan_esp32(pin=19, channel=3, timer_src=0, frequency=5000, duty_cycle=0):
        #     print("sending fan setup command again...")
        #     time.sleep(5)
        # time.sleep(1)

        # Initialize Light Sensor exactly as in user script
        ads_channels = [ads.P0, ads.P1, ads.P2, ads.P3]
        lightSensor = LightSensor(ads_sensor=ads.ADS1115(i2cBus), ads_channels=ads_channels, I2C=i2cBus)
        lightSensor.set_light_intensity_ads1115_channel(1) # Set the channel for light sensor
        print("Light sensor initialized.")

        print("Hardware initialization complete.")
        return True

    except Exception as e:
        print(f"Error during hardware initialization: {e}")
        return False

def get_light_intensity():
    """Reads light intensity from the actual sensor - STRICTLY user code."""
    global lightSensor
    # No additional error checking added here as per user request
    lightLux = lightSensor.get_light_intensity()
    return lightLux

def set_light_strip_duty_cycle(power_level):
    """Sets duty cycle for both light strips - STRICTLY user code structure."""
    global act
    # No additional error checking or range clamping added here
    # Using the exact structure from user's set_led_power function
    while not act.set_light_strip_1_duty_cycle(power_level):  # Set LED power level (0-4095)
        print("sending light strip 1 power command again...")
        time.sleep(0.1)

    while not act.set_light_strip_2_duty_cycle(power_level):  # Set LED power level (0-4095)
        print("sending light strip 2 power command again...")
        time.sleep(0.1)
    # The function implicitly returns None, mirroring user's original structure
    # We don't return success/failure as the original didn't

# --- Global Variables --- 
pid_controller = None
control_thread = None
stop_event = threading.Event()
app_running = True

# Default values (Keep these for the GUI)
DEFAULT_KP = 10.0
DEFAULT_KI = 0.1
DEFAULT_KD = 0.0
DEFAULT_SETPOINT = 1500
SAMPLE_TIME = 0.1 # Seconds
OUTPUT_LIMITS = (0, 4095)

# --- PID Control Loop (Minimal changes, uses strict hardware functions) --- 
def pid_control_loop(app_instance):
    """Runs the PID control logic in a separate thread."""
    global pid_controller
    last_update_time = time.time()

    while not stop_event.is_set():
        current_time = time.time()
        if current_time - last_update_time < SAMPLE_TIME:
            time.sleep(0.01) # Prevent busy-waiting
            continue

        last_update_time = current_time
        light_intensity = 0 # Default value
        duty_cycle = 0 # Default value

        try:
            # Read sensor
            light_intensity = get_light_intensity()
            if light_intensity is None: # Basic check from user's original code implicit behavior
                print("Warning: Light sensor read None, skipping PID step.")
                continue

            # Calculate PID output
            if pid_controller is not None:
                duty_cycle = pid_controller(light_intensity)
            else:
                duty_cycle = 0 # Default to off if PID not initialized

            # Apply to actuator
            if pid_controller is not None and pid_controller.setpoint > 0:
                set_light_strip_duty_cycle(int(duty_cycle)) # Cast to int
            else:
                set_light_strip_duty_cycle(0) # Turn off if setpoint is 0 or PID not ready

            # Update GUI (using thread-safe method)
            app_instance.update_display(light_intensity, duty_cycle)

        except Exception as e:
            print(f"Error in PID loop: {e}")
            # Consider adding more robust error handling or just logging
            time.sleep(SAMPLE_TIME) # Wait before retrying on error

    # Ensure lights are off when loop stops
    print("Control loop stopping. Turning off lights.")
    try:
        set_light_strip_duty_cycle(0)
    except Exception as e:
        print(f"Error turning off lights on exit: {e}")
    print("Control loop stopped.")

# --- Tkinter GUI Application (Structure remains the same) --- 
class ManualTunerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Manual Light PID Tuner (Strict User HW Code)")
        self.geometry("400x350")
        self.protocol("WM_DELETE_WINDOW", self.on_closing) # Handle window close

        # Initialize Hardware FIRST
        self.hardware_ok = initialize_hardware()

        # Initialize PID controller AFTER hardware
        self.initialize_pid()

        # Create GUI elements
        self.create_widgets()

        if not self.hardware_ok:
            messagebox.showerror("Hardware Error", "Failed to initialize hardware. Check console. Loop disabled.")
            if hasattr(self, 'start_stop_button'): # Check if button exists before disabling
                 self.start_stop_button.config(state=tk.DISABLED)

    def initialize_pid(self):
        global pid_controller
        pid_controller = PID(
            Kp=DEFAULT_KP,
            Ki=DEFAULT_KI,
            Kd=DEFAULT_KD,
            setpoint=DEFAULT_SETPOINT,
            sample_time=SAMPLE_TIME,
            output_limits=OUTPUT_LIMITS
        )
        pid_controller.proportional_on_measurement = False
        print(f"PID Initialized: Kp={DEFAULT_KP}, Ki={DEFAULT_KI}, Kd={DEFAULT_KD}, SP={DEFAULT_SETPOINT}")

    def create_widgets(self):
        frame = ttk.Frame(self, padding="10")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # --- Input Fields ---
        ttk.Label(frame, text="Kp:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.kp_var = tk.StringVar(value=str(DEFAULT_KP))
        self.kp_entry = ttk.Entry(frame, textvariable=self.kp_var, width=10)
        self.kp_entry.grid(row=0, column=1, sticky=tk.W, pady=2)

        ttk.Label(frame, text="Ki:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.ki_var = tk.StringVar(value=str(DEFAULT_KI))
        self.ki_entry = ttk.Entry(frame, textvariable=self.ki_var, width=10)
        self.ki_entry.grid(row=1, column=1, sticky=tk.W, pady=2)

        ttk.Label(frame, text="Kd:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.kd_var = tk.StringVar(value=str(DEFAULT_KD))
        self.kd_entry = ttk.Entry(frame, textvariable=self.kd_var, width=10)
        self.kd_entry.grid(row=2, column=1, sticky=tk.W, pady=2)

        ttk.Label(frame, text="Setpoint:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.sp_var = tk.StringVar(value=str(DEFAULT_SETPOINT))
        self.sp_entry = ttk.Entry(frame, textvariable=self.sp_var, width=10)
        self.sp_entry.grid(row=3, column=1, sticky=tk.W, pady=2)

        # --- Apply Button ---
        self.apply_button = ttk.Button(frame, text="Apply Settings", command=self.apply_settings)
        self.apply_button.grid(row=4, column=0, columnspan=2, pady=10)

        # --- Display Labels ---
        ttk.Label(frame, text="Current Light:").grid(row=5, column=0, sticky=tk.W, pady=2)
        self.light_val_var = tk.StringVar(value="--")
        ttk.Label(frame, textvariable=self.light_val_var, font=("TkDefaultFont", 10, "bold")).grid(row=5, column=1, sticky=tk.W, pady=2)

        ttk.Label(frame, text="Duty Cycle:").grid(row=6, column=0, sticky=tk.W, pady=2)
        self.duty_cycle_var = tk.StringVar(value="--")
        ttk.Label(frame, textvariable=self.duty_cycle_var, font=("TkDefaultFont", 10, "bold")).grid(row=6, column=1, sticky=tk.W, pady=2)

        # --- Start/Stop Button ---
        self.start_stop_button = ttk.Button(frame, text="Start Loop", command=self.toggle_loop)
        self.start_stop_button.grid(row=7, column=0, columnspan=2, pady=10)
        self.loop_running = False
        # Disable button initially if hardware failed
        if not self.hardware_ok:
            self.start_stop_button.config(state=tk.DISABLED)

    def apply_settings(self):
        global pid_controller
        try:
            kp = float(self.kp_var.get())
            ki = float(self.ki_var.get())
            kd = float(self.kd_var.get())
            sp = float(self.sp_var.get())

            if pid_controller is not None:
                pid_controller.tunings = (kp, ki, kd)
                pid_controller.setpoint = sp
                # Reset if setpoint is 0 to clear integral
                if sp <= 0:
                     pid_controller.reset()
                print(f"PID Settings Updated: Kp={kp}, Ki={ki}, Kd={kd}, SP={sp}")
            else:
                messagebox.showerror("Error", "PID Controller not initialized.")

        except ValueError:
            messagebox.showerror("Input Error", "Please enter valid numbers for Kp, Ki, Kd, and Setpoint.")
        except Exception as e:
             messagebox.showerror("Error", f"Failed to apply settings: {e}")

    def toggle_loop(self):
        global control_thread, stop_event
        if not self.hardware_ok:
             messagebox.showerror("Hardware Error", "Cannot start loop, hardware not initialized.")
             return

        if self.loop_running:
            # Stop the loop
            print("Stopping control loop...")
            stop_event.set()
            if control_thread and control_thread.is_alive():
                control_thread.join(timeout=2) # Wait for thread to finish
            if control_thread and control_thread.is_alive():
                 print("Warning: Control thread did not stop gracefully.")
            control_thread = None
            self.start_stop_button.config(text="Start Loop")
            self.loop_running = False
            self.update_display("--", "--") # Clear display
            print("Loop stopped by GUI.")
        else:
            # Start the loop
            print("Starting control loop...")
            stop_event.clear()
            # Apply current settings before starting
            self.apply_settings()
            if pid_controller is None:
                 messagebox.showerror("Error", "Cannot start, PID controller not ready.")
                 return

            control_thread = threading.Thread(target=pid_control_loop, args=(self,), daemon=True)
            control_thread.start()
            self.start_stop_button.config(text="Stop Loop")
            self.loop_running = True
            print("Loop started by GUI.")

    def update_display(self, light_value, duty_cycle_value):
        """Thread-safe method to update GUI labels."""
        try:
            # Check if the root window still exists
            if self.winfo_exists():
                self.light_val_var.set(f"{light_value:.2f}" if light_value is not None else "N/A")
                self.duty_cycle_var.set(f"{duty_cycle_value:.0f}")
        except tk.TclError:
            # Handle cases where the widget might be destroyed during update
            pass
        except Exception as e:
            print(f"Error updating GUI: {e}")

    def on_closing(self):
        global app_running
        print("Closing application...")
        if self.loop_running:
            self.toggle_loop() # Attempt to stop the loop gracefully
        app_running = False
        self.destroy()

# --- Main Execution --- 
if __name__ == "__main__":
    # Check for display environment variable for GUI
    if not os.environ.get('DISPLAY'):
        print("Error: DISPLAY environment variable not set. Cannot run GUI.")
        print("If running via SSH, use 'ssh -X' or configure X11 forwarding.")
    else:
        app = ManualTunerApp()
        if HARDWARE_MODULES_FOUND and app.hardware_ok:
             app.mainloop()
        else:
             print("Exiting due to missing hardware modules or initialization failure.")
    print("Application closed.")

