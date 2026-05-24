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

        # Anti-windup: undo integral accumulation when output is saturated
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
            fan_duty_cycle    = int(MIN_POWER + (POWER_RANGE * cool_power_scaled))
            fan_duty_cycle    = max(MIN_POWER, min(MAX_POWER, fan_duty_cycle))
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
    soil_semaphore, soil_pause_event, db_handler, light_pause_event=None,
):
    """
    Pulse irrigation: when soil moisture is below threshold, fire a short
    pump burst, then wait for the water to absorb before re-checking.

    Tunable constants:
      PUMP_DC         — duty cycle during pulse (0-4095)
      PULSE_ON_SEC    — how long the pump runs per pulse (seconds)
      ABSORB_WAIT_SEC — how long to wait after a pulse before re-checking
      CHECK_INTERVAL  — how often to check when soil is already OK (seconds)
      PUMP_TIMEOUT_SEC — max seconds to wait for pump I2C command to succeed
    """
    PUMP_DC          = 1800
    PULSE_ON_SEC     = 1
    ABSORB_WAIT_SEC  = 600
    CHECK_INTERVAL   = 30

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
            time.sleep(CHECK_INTERVAL)
            continue
        finally:
            soil_semaphore.release()

        # 0.0 means the sensor failed to respond — skip this cycle
        if soil_humidity == 0.0:
            _CUSTOM_PRINT_FUNC("[Soil] Sensor returned 0.0 — read failed, skipping cycle.")
            time.sleep(CHECK_INTERVAL)
            continue

        _CUSTOM_PRINT_FUNC(
            f"[Soil] Moisture={soil_humidity:.1f}%  "
            f"Threshold={start_threshold:.1f}%  Setpoint={mo_set_point:.1f}%"
        )

        if soil_humidity <= start_threshold:
            _CUSTOM_PRINT_FUNC(
                f"[Soil] Moisture {soil_humidity:.1f}% <= {start_threshold:.1f}% — firing pump"
            )

            # Pause light loop so I2C is free — same as curl command having exclusive bus access
            if light_pause_event is not None:
                light_pause_event.clear()
                time.sleep(0.2)

            # Exactly: duty_cycle=1700, sleep 1, duty_cycle=0
            env_actuators.set_water_pump_duty_cycle(PUMP_DC)
            env_actuators.set_mqtt_dc_value_water_pump(PUMP_DC)
            time.sleep(PULSE_ON_SEC)
            env_actuators.set_water_pump_duty_cycle(0)
            env_actuators.set_mqtt_dc_value_water_pump(0)

            # Resume light loop
            if light_pause_event is not None:
                light_pause_event.set()

            flow_rate = 0.0
            try:
                flow_rate = env_sensors.get_water_flow_rate()
            except Exception:
                pass

            db_handler.insert_pump_log('water', PULSE_ON_SEC, PUMP_DC, flow_rate)
            _CUSTOM_PRINT_FUNC(
                f"[Soil] Pump OFF — waiting {ABSORB_WAIT_SEC}s for water to absorb..."
            )

            # Wait for absorption, then loop back to re-check moisture
            time.sleep(ABSORB_WAIT_SEC)

        else:
            _CUSTOM_PRINT_FUNC("[Soil] ✅ Moisture OK — no irrigation needed.")
            time.sleep(CHECK_INTERVAL)


def fertilizer_pump_control_task(
    env_sensors, env_actuators, setpoints,
    soil_semaphore, fertilizer_pause_event, db_handler,
    light_pause_event=None,
):
    """
    EC-based fertilization for lettuce.

    Every 60 s:
      EC >= 2000  → DANGER: fertilizer OFF, brief water dilution pulse, alert
      EC > 1800   → too high: fertilizer OFF, brief water dilution pulse, recheck
      EC 1200–1800→ OK: fertilizer OFF; if pH > 6.8 send pH alert
      EC < 1200   → too low: fire 1 s fertilizer pulse, wait 6 min to mix;
                    if pH > 6.8 send warning but still fertilize
    """
    FERT_DC         = 2662   # fertilizer pump duty cycle (~65%)
    WATER_DC        = 1800   # water pump duty cycle for dilution
    PULSE_ON_SEC    = 1      # fertilizer pulse duration (seconds)
    WATER_PULSE_SEC = 1      # water dilution pulse duration (seconds)
    SETTLE_WAIT_SEC = 360    # 6 min after fertilizer pulse
    CHECK_INTERVAL  = 60     # 60 s between normal checks

    EC_LOW       = 1200.0
    EC_HIGH      = 1800.0
    EC_DANGER    = 2000.0
    PH_HIGH_WARN = 6.8

    def _alert(msg):
        _CUSTOM_PRINT_FUNC(f"[Fertilizer] ALERT: {msg}")

    def _dilute_with_water():
        """Fire a short water pump pulse to dilute high EC."""
        if light_pause_event is not None:
            light_pause_event.clear()
            time.sleep(0.2)
        env_actuators.set_water_pump_duty_cycle(WATER_DC)
        time.sleep(WATER_PULSE_SEC)
        env_actuators.set_water_pump_duty_cycle(0)
        if light_pause_event is not None:
            light_pause_event.set()
        _CUSTOM_PRINT_FUNC(f"[Fertilizer] Water dilution pulse done ({WATER_PULSE_SEC}s).")

    while True:
        fertilizer_pause_event.wait()

        # ── Read sensors ───────────────────────────────────────────────────────
        soil_semaphore.acquire()
        try:
            soil_ph, soil_ec, _, _ = env_sensors.get_soil_values()
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[Fertilizer] Sensor read error: {e}")
            time.sleep(CHECK_INTERVAL)
            continue
        finally:
            soil_semaphore.release()

        _CUSTOM_PRINT_FUNC(
            f"[Fertilizer] EC={soil_ec:.1f} µS/cm  pH={soil_ph:.2f}"
        )

        # ── 1. EC DANGER ───────────────────────────────────────────────────────
        if soil_ec >= EC_DANGER:
            env_actuators.set_fertilizer_pump_duty_cycle(0)
            _alert(
                f"DANGER: EC={soil_ec:.1f} µS/cm is critically high (>= {EC_DANGER:.0f}). "
                f"Root burn risk! Fertilizer pump LOCKED OFF. Activating water to dilute."
            )
            _dilute_with_water()
            time.sleep(CHECK_INTERVAL)
            continue

        # ── 2. EC too high ─────────────────────────────────────────────────────
        if soil_ec >= EC_HIGH:
            env_actuators.set_fertilizer_pump_duty_cycle(0)
            _CUSTOM_PRINT_FUNC(
                f"[Fertilizer] EC={soil_ec:.1f} too high (>= {EC_HIGH:.0f}). "
                f"Pump OFF. Activating water to dilute."
            )
            _dilute_with_water()
            time.sleep(CHECK_INTERVAL)
            continue

        # ── 3. EC OK ───────────────────────────────────────────────────────────
        if soil_ec >= EC_LOW:
            env_actuators.set_fertilizer_pump_duty_cycle(0)
            _CUSTOM_PRINT_FUNC(
                f"[Fertilizer] EC OK — {soil_ec:.1f} µS/cm in target range 1200–1800."
            )
            if soil_ph > PH_HIGH_WARN:
                _alert(
                    f"pH={soil_ph:.2f} is high (> {PH_HIGH_WARN}). "
                    f"Add pH Down manually to bring pH to 5.8–6.5."
                )
            time.sleep(CHECK_INTERVAL)
            continue

        # ── 4. EC too low — fire fertilizer pulse ─────────────────────────────
        _CUSTOM_PRINT_FUNC(
            f"[Fertilizer] EC={soil_ec:.1f} < {EC_LOW:.0f} — firing pulse: {PULSE_ON_SEC}s ON."
        )

        if soil_ph > PH_HIGH_WARN:
            _alert(
                f"pH={soil_ph:.2f} is high (> {PH_HIGH_WARN}), but EC={soil_ec:.1f} is too low. "
                f"Continuing fertilization. Add pH Down manually after EC improves."
            )

        while not env_actuators.set_fertilizer_pump_duty_cycle(FERT_DC):
            time.sleep(0.1)

        time.sleep(PULSE_ON_SEC)

        fert_flow_rate = 0.0
        try:
            fert_flow_rate = env_sensors.get_fertilizer_flow_rate()
        except Exception:
            pass

        while not env_actuators.set_fertilizer_pump_duty_cycle(0):
            time.sleep(0.1)

        db_handler.insert_pump_log('fertilizer', PULSE_ON_SEC, FERT_DC, fert_flow_rate)
        _CUSTOM_PRINT_FUNC(
            f"[Fertilizer] Pump OFF. Waiting {SETTLE_WAIT_SEC}s for fertilizer to mix..."
        )
        time.sleep(SETTLE_WAIT_SEC)
