"""
control_loops.py — PID and hysteresis control loop thread functions.

Each function is designed to run as a daemon thread target.
All dependencies are passed as arguments so the functions are self-contained.
"""
import time
from simple_pid import PID
from utils.utils import _CUSTOM_PRINT_FUNC


def temperature_sp_adjustment_task(
    env_sensors, env_actuators, setpoints,
    temperature_semaphore, temperature_pause_event,
):
    # PID controller parameters - easily tunable
    KP_TEMP = 1034.05  # Proportional gain
    KI_TEMP = 1.52     # Integral gain
    KD_TEMP = 0.0      # Derivative gain

    # Output limits for bidirectional control (-1 to 1)
    # Negative values for cooling, positive for heating
    OUTPUT_LIMITS = (-1, 1)

    # Sample time in seconds
    SAMPLE_TIME = 10

    # Deadband to prevent rapid switching between heating and cooling
    DEADBAND = 1.0  # °C — heater ON below 22°C, IDLE 22-24°C, fan ON above 24°C

    # Actuator power limits
    MIN_POWER = 500
    MAX_POWER = 4095
    POWER_RANGE = MAX_POWER - MIN_POWER

    # Create a single PID controller for both heating and cooling
    temperature_pid = PID(
        KP_TEMP, KI_TEMP, KD_TEMP,
        setpoint=0,
        sample_time=SAMPLE_TIME,
        output_limits=OUTPUT_LIMITS,
    )
    temperature_pid.proportional_on_measurement = False

    while True:
        temperature_pause_event.wait()
        _CUSTOM_PRINT_FUNC(f"[TEMP] Mode={setpoints.get_operation_mode()} | PID loop running")

        temperature_set_point = setpoints.get_temperature_setpoint()
        temperature_pid.setpoint = temperature_set_point

        try:
            temperature_semaphore.acquire()
            current_temp = env_sensors.get_air_temperature_C()
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[TEMP] Error reading temperature: {e}")
            continue
        finally:
            temperature_semaphore.release()

        _CUSTOM_PRINT_FUNC(
            f"[TEMP] Temp={current_temp:.2f}°C  Setpoint={temperature_set_point:.2f}°C"
            f"  Error={temperature_set_point - current_temp:.2f}"
        )

        raw_output = temperature_pid(current_temp)

        # Anti-windup logic
        if (raw_output >= OUTPUT_LIMITS[1] and (temperature_set_point - current_temp) > 0) or \
           (raw_output <= OUTPUT_LIMITS[0] and (temperature_set_point - current_temp) < 0):
            temperature_pid._integral -= (temperature_set_point - current_temp) * KI_TEMP * SAMPLE_TIME

        control_output = raw_output

        if abs(temperature_set_point - current_temp) < DEADBAND:
            control_output = 0

        _CUSTOM_PRINT_FUNC(
            f"[TEMP] PID output={control_output:.4f}"
            f"  Action={'HEATING' if control_output > 0 else 'COOLING' if control_output < 0 else 'IDLE'}"
        )

        if control_output > 0:  # HEATING
            heat_power_scaled = control_output
            heater_duty_cycle = int(MIN_POWER + (POWER_RANGE * heat_power_scaled))
            heater_duty_cycle = max(MIN_POWER, min(MAX_POWER, heater_duty_cycle))
            _CUSTOM_PRINT_FUNC(f"[TEMP] Setting heater ON → duty={heater_duty_cycle}")
            if not env_actuators.set_heater_duty_cycle(heater_duty_cycle):
                _CUSTOM_PRINT_FUNC("[TEMP] WARNING: heater set failed")
            if not env_actuators.set_heater_fan_duty_cycle(heater_duty_cycle):
                _CUSTOM_PRINT_FUNC("[TEMP] WARNING: heater fan set failed")
            env_actuators.set_fan_duty_cycle(0)

        elif control_output < 0:  # COOLING
            cool_power_scaled = abs(control_output)
            fan_duty_cycle = int(MIN_POWER + (POWER_RANGE * cool_power_scaled))
            fan_duty_cycle = max(MIN_POWER, min(MAX_POWER, fan_duty_cycle))
            _CUSTOM_PRINT_FUNC(f"[TEMP] Setting fan ON → duty={fan_duty_cycle}")
            env_actuators.set_heater_duty_cycle(0)
            env_actuators.set_heater_fan_duty_cycle(0)
            if not env_actuators.set_fan_duty_cycle(fan_duty_cycle):
                _CUSTOM_PRINT_FUNC("[TEMP] WARNING: fan set failed")

        else:  # IDLE
            _CUSTOM_PRINT_FUNC("[TEMP] IDLE — all actuators OFF")
            env_actuators.set_heater_duty_cycle(0)
            env_actuators.set_heater_fan_duty_cycle(0)
            env_actuators.set_fan_duty_cycle(0)

        time.sleep(SAMPLE_TIME)


def light_sp_adjustment_task(
    env_sensors, env_actuators, setpoints,
    light_semaphore, light_pause_event,
):
    # PID controller parameters - easily tunable
    KP_LIGHT = 20   # Proportional gain
    KI_LIGHT = 7.5  # Integral gain
    KD_LIGHT = 0.1  # Derivative gain

    OUTPUT_LIMITS = (0, 4095)
    SAMPLE_TIME = 0.1

    light_pid = PID(
        KP_LIGHT, KI_LIGHT, KD_LIGHT,
        setpoint=0,
        sample_time=SAMPLE_TIME,
        output_limits=OUTPUT_LIMITS,
    )
    light_pid.proportional_on_measurement = False

    prev_set_point = 0

    while True:
        light_pause_event.wait()

        light_set_point = setpoints.get_light_setpoint()
        light_pid.setpoint = light_set_point

        try:
            light_semaphore.acquire()
            light_intensity = env_sensors.get_light_intensity()
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error reading light sensor: {e}")
            continue
        finally:
            light_semaphore.release()

        if prev_set_point != light_set_point:
            light_pid.reset()
            prev_set_point = light_set_point

        if light_set_point > 0:
            duty_cycle = light_pid(light_intensity)

            while not env_actuators.set_light_strip_1_duty_cycle(int(duty_cycle)):
                time.sleep(0.1)

            while not env_actuators.set_light_strip_2_duty_cycle(int(duty_cycle)):
                time.sleep(0.1)
        else:
            while not env_actuators.set_light_strip_1_duty_cycle(0):
                time.sleep(0.1)

            while not env_actuators.set_light_strip_2_duty_cycle(0):
                time.sleep(0.1)

            light_pid.reset()

        time.sleep(SAMPLE_TIME)


def set_soil_moisture_setpoint_task(
    env_sensors, env_actuators, setpoints,
    soil_semaphore, soil_pause_event,
):
    """
    Pulse irrigation: when soil moisture is below threshold, fire a short
    pump burst, then wait for the water to absorb before re-checking.

    Tunable constants:
      PUMP_DC         — duty cycle during pulse (0-4095)
      PULSE_ON_SEC    — how long the pump runs per pulse (seconds)
      ABSORB_WAIT_SEC — how long to wait after a pulse before re-checking
      CHECK_INTERVAL  — how often to check when soil is already OK (seconds)
    """
    PUMP_DC         = 3000   # ~73% — enough to push water, not flood
    PULSE_ON_SEC    = 2      # pump runs for 2 seconds per pulse
    ABSORB_WAIT_SEC = 120    # wait 2 minutes for water to absorb
    CHECK_INTERVAL  = 30     # check every 30 s when no irrigation needed

    while True:
        soil_pause_event.wait()

        mo_set_point    = setpoints.get_soil_humidity_setpoint()
        hysteresis      = setpoints.get_soil_humidity_hysteresis()
        start_threshold = mo_set_point - hysteresis

        soil_semaphore.acquire()
        try:
            _, _, soil_humidity, _ = env_sensors.get_soil_values()
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[Soil] Error reading moisture: {e}")
            soil_semaphore.release()
            time.sleep(CHECK_INTERVAL)
            continue
        finally:
            soil_semaphore.release()

        _CUSTOM_PRINT_FUNC(
            f"[Soil] Moisture={soil_humidity:.1f}%  "
            f"Threshold={start_threshold:.1f}%  Setpoint={mo_set_point:.1f}%"
        )

        if soil_humidity <= start_threshold:
            # Fire one pulse
            _CUSTOM_PRINT_FUNC(
                f"[Soil] 💧 Moisture {soil_humidity:.1f}% ≤ {start_threshold:.1f}% "
                f"— pulse ON for {PULSE_ON_SEC}s"
            )
            while not env_actuators.set_water_pump_duty_cycle(PUMP_DC):
                time.sleep(0.1)

            time.sleep(PULSE_ON_SEC)

            while not env_actuators.set_water_pump_duty_cycle(0):
                time.sleep(0.1)
            _CUSTOM_PRINT_FUNC(
                f"[Soil] Pump OFF — waiting {ABSORB_WAIT_SEC}s for water to absorb..."
            )

            # Wait for absorption, then loop back to re-check moisture
            time.sleep(ABSORB_WAIT_SEC)

        else:
            _CUSTOM_PRINT_FUNC("[Soil] ✅ Moisture OK — no irrigation needed.")
            time.sleep(CHECK_INTERVAL)
