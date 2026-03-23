"""
Temperature PID Test Script
----------------------------
Tests the PID logic with the real DHT22 sensor and real actuators (heater + fan).
No MongoDB or MQTT required.

Run from the Backend folder:
    cd "/home/mohamadaboria/Desktop/PlantMind AI/NewProject/Backend"
    python3 tests/test_temperature_pid.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import time
import signal
import datetime
import board
import busio
from simple_pid import PID
from Sensors.air import AirSensor
from Actuators.actuators import GH_Actuators


def _timeout_handler(signum, frame):
    raise TimeoutError("DHT22 read timed out")

def read_temperature_safe(air_sensor, fallback, timeout=4):
    """Read DHT22 with a hard OS-level timeout — works even on blocking GPIO."""
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(timeout)
    try:
        temp = air_sensor.get_air_temperature_C()
        signal.alarm(0)  # cancel alarm
        return temp if (temp is not None and temp != 0.0) else fallback
    except TimeoutError:
        print(f"  [WARN] DHT22 timed out — using last value: {fallback:.2f} °C")
        return fallback
    except Exception as e:
        print(f"  [WARN] DHT22 error ({e}) — using last value: {fallback:.2f} °C")
        signal.alarm(0)
        return fallback

# ─── SETTINGS ────────────────────────────────────────────────────────────────
TEMPERATURE_SETPOINT = 24.0   # <-- change this to test different targets

KP = 1034.05
KI = 1.52
KD = 0.0

SAMPLE_TIME   = 10    # seconds between each PID step
DEADBAND      = 0.2   # °C — no action if within this range of setpoint
MIN_POWER     = 500   # minimum duty cycle when actuator is ON
MAX_POWER     = 4095  # maximum duty cycle
OUTPUT_LIMITS = (-1, 1)
# ─────────────────────────────────────────────────────────────────────────────


def main():
    print("=" * 55)
    print("  Temperature PID Test")
    print(f"  Setpoint : {TEMPERATURE_SETPOINT} °C")
    print(f"  Kp={KP}  Ki={KI}  Kd={KD}")
    print(f"  Sample time: {SAMPLE_TIME}s   Deadband: ±{DEADBAND}°C")
    print("=" * 55)

    # --- Hardware init ---
    i2c = busio.I2C(board.SCL, board.SDA)

    air_sensor = AirSensor()
    air_sensor.set_dht22_pin(board.D26)

    actuators = GH_Actuators(0x30, i2c, 'big')

    print("Restarting ESP32...", end='', flush=True)
    while not actuators.restart_esp32():
        time.sleep(2)
    start = datetime.datetime.now()
    while datetime.datetime.now() - start < datetime.timedelta(seconds=10):
        print(".", end='', flush=True)
        time.sleep(1)
    print(" done.")

    print("Setting up heater (pin 17)...", end='', flush=True)
    while not actuators.setup_heater_esp32(pin=17, channel=1, timer_src=1, frequency=50, duty_cycle=0):
        time.sleep(2)
    time.sleep(1)
    print(" done.")

    print("Setting up heater fan (pin 18)...", end='', flush=True)
    while not actuators.setup_heater_fan_esp32(pin=18, channel=2, timer_src=0, frequency=5000, duty_cycle=0):
        time.sleep(2)
    time.sleep(1)
    print(" done.")

    print("Setting up cooling fan (pin 19)...", end='', flush=True)
    while not actuators.setup_fan_esp32(pin=19, channel=3, timer_src=0, frequency=5000, duty_cycle=0):
        time.sleep(2)
    time.sleep(1)
    print(" done.")

    # --- PID init ---
    pid = PID(KP, KI, KD,
              setpoint=TEMPERATURE_SETPOINT,
              sample_time=SAMPLE_TIME,
              output_limits=OUTPUT_LIMITS)
    pid.proportional_on_measurement = False

    print("\n{:<6} {:<12} {:<12} {:<10} {:<12} {:<10}".format(
        "Step", "Temp (°C)", "Error (°C)", "PID Out", "Action", "Duty Cycle"))
    print("-" * 65)

    def set_actuator(fn, value, name):
        """Try to set actuator once, print warning if it fails."""
        if not fn(value):
            print(f"  [WARN] Failed to set {name} to {value} — continuing anyway")

    last_temp = 20.0  # safe starting fallback
    step = 1
    try:
        while True:
            try:
                current_temp = read_temperature_safe(air_sensor, fallback=last_temp)
                last_temp = current_temp
                print(f"  [DEBUG] Temp: {current_temp:.2f} °C")

                error = TEMPERATURE_SETPOINT - current_temp
                raw_output = pid(current_temp)

                # Deadband check
                if abs(error) < DEADBAND:
                    control_output = 0
                else:
                    control_output = raw_output

                power_range = MAX_POWER - MIN_POWER

                if control_output > 0:
                    duty = int(MIN_POWER + power_range * control_output)
                    duty = max(MIN_POWER, min(MAX_POWER, duty))
                    set_actuator(actuators.set_heater_duty_cycle, duty, "heater")
                    set_actuator(actuators.set_heater_fan_duty_cycle, duty, "heater_fan")
                    set_actuator(actuators.set_fan_duty_cycle, 0, "fan")
                    action = "HEATING"

                elif control_output < 0:
                    duty = int(MIN_POWER + power_range * abs(control_output))
                    duty = max(MIN_POWER, min(MAX_POWER, duty))
                    set_actuator(actuators.set_heater_duty_cycle, 0, "heater")
                    set_actuator(actuators.set_heater_fan_duty_cycle, 0, "heater_fan")
                    set_actuator(actuators.set_fan_duty_cycle, duty, "fan")
                    action = "COOLING"

                else:
                    duty = 0
                    set_actuator(actuators.set_heater_duty_cycle, 0, "heater")
                    set_actuator(actuators.set_heater_fan_duty_cycle, 0, "heater_fan")
                    set_actuator(actuators.set_fan_duty_cycle, 0, "fan")
                    action = "IDLE"

                print("{:<6} {:<12.2f} {:<12.2f} {:<10.4f} {:<12} {:<10}".format(
                    step, current_temp, error, control_output, action, duty))

            except Exception as e:
                print(f"  [ERROR] Step {step} failed: {e}")

            step += 1
            time.sleep(SAMPLE_TIME)

    except KeyboardInterrupt:
        print("\n\nTest stopped by user. Turning off all actuators...")
        actuators.set_heater_duty_cycle(0)
        actuators.set_heater_fan_duty_cycle(0)
        actuators.set_fan_duty_cycle(0)
        print("All actuators OFF. Test complete.")


if __name__ == "__main__":
    main()
