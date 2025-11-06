import time
import board
import adafruit_dht
import numpy as np
import matplotlib.pyplot as plt
from gekko import GEKKO
from Actuators.actuators import GH_Actuators

# Initialize actuators
act = GH_Actuators(esp32_i2c_address=0x30)
act.setup_heater_esp32(pin=17, channel=1, timer_src=1, frequency=50, duty_cycle=0)  # Pin 18, channel 0, frequency 10 Hz, duty cycle 0

# Set up DHT22 sensor
dht_device = adafruit_dht.DHT22(board.D26)

# Setpoint (Target Temperature)
TEMP_SETPOINT = 30

# Create GEKKO Model
m = GEKKO(remote=False)

# **Fix 1: Define a Proper Time Grid**
m.time = np.linspace(0, 10, 11)  # 11 points over 10 seconds

# **Fix 2: Ensure Bounded Variables**
heater = m.MV(value=50, lb=0, ub=4095)  # Heater power (0-100%)
heater.STATUS = 1  # Allow GEKKO to optimize it
heater.DCOST = 0.1  # Penalize sudden changes
# heater.TR_INIT = 2  # Allow a small initial guess for heater output

# PID Gains
Kp = m.FV(value=1, lb=0, ub=5)  # Proportional Gain (Bounded)
Ki = m.FV(value=0.1, lb=0, ub=2)  # Integral Gain (Bounded)
Kd = m.Param(value=0.05)  # Fixed Derivative term

# Enable Auto-Tuning
Kp.STATUS, Ki.STATUS = 1, 1

# Process Variable (Temperature)
temp = m.CV(value=20, lb=10, ub=50)  # Temperature must be realistic
temp.FSTATUS = 1  # Enable feedback from sensor

# **Fix 3: Use a More Stable Equation**
m.Equation(temp.dt() == 0.05 * heater - 0.2 * (temp - TEMP_SETPOINT))  # Simple linear model

# **Fix 4: Start with a Simulation First**
m.options.IMODE = 5  # Simulation mode
m.solve(disp=False)

# **Switch to Dynamic Control**
m.options.IMODE = 6  # Dynamic optimization
m.options.CV_TYPE = 1  # Minimize squared error

# Function to Read Temperature
def read_temperature():
    try:
        return dht_device.temperature
    except RuntimeError:
        return None

# **Ensure All Data Lists Are Equal**
time_list = list(m.time)
temp_list = [20] * len(m.time)
output_list = [0] * len(m.time)

# Start Time
start_time = time.time()

# Real-Time Plot Setup
plt.ion()
fig, ax = plt.subplots()
temp_line, = plt.plot([], [], label="Temperature (°C)", color="blue")
output_line, = plt.plot([], [], label="Heater Output (%)", color="red")
plt.xlabel("Time (s)")
plt.ylabel("Value")
plt.legend()

# PID Control Loop
while True:
    temp_val = read_temperature()
    if temp_val is not None:
        # **Ensure Same Length for All Arrays**
        temp_list.append(temp_val)
        temp_list.pop(0)
        
        temp.VALUE = temp_list
        m.solve(disp=False)  # Solve PID Optimization

        heater_output = heater.VALUE[0]  # Get heater output from GEKKO

        # Set Heater Power
        act.set_heater_duty_cycle(int(heater_output))  # Scale to ESP32 range (0-4095)

        # Store Data
        time_list.append(time.time() - start_time)
        time_list.pop(0)
        output_list.append(heater_output)
        output_list.pop(0)

        # Update Graph
        temp_line.set_data(time_list, temp_list)
        output_line.set_data(time_list, output_list)
        ax.relim()
        ax.autoscale_view()
        plt.pause(0.5)

    time.sleep(2)  # Adjust every 2 seconds
