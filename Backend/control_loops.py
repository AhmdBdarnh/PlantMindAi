"""
control_loops.py — PID and hysteresis control loop thread functions.

Each function is designed to run as a daemon thread target.
All dependencies are passed as arguments so the functions are self-contained.
"""
import time
import datetime
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

    OUTPUT_LIMITS = (-1, 1)
    SAMPLE_TIME   = 10
    DEADBAND      = 1.0  # °C

    # Actuator power limits
    MIN_POWER  = 500
    MAX_POWER  = 4095
    POWER_RANGE = MAX_POWER - MIN_POWER

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

        # Anti-windup
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
            _CUSTOM_PRINT_FUNC(f"[TEMP] HEATING → heater duty={heater_duty_cycle}")
            if not env_actuators.set_heater_duty_cycle(heater_duty_cycle):
                _CUSTOM_PRINT_FUNC("[TEMP] WARNING: heater set failed")
            if not env_actuators.set_heater_fan_duty_cycle(heater_duty_cycle):
                _CUSTOM_PRINT_FUNC("[TEMP] WARNING: heater fan set failed")
            env_actuators.set_fan_duty_cycle(0)

        elif control_output < 0:  # COOLING
            cool_power_scaled = abs(control_output)
            fan_duty_cycle = int(MIN_POWER + (POWER_RANGE * cool_power_scaled))
            fan_duty_cycle = max(MIN_POWER, min(MAX_POWER, fan_duty_cycle))
            _CUSTOM_PRINT_FUNC(f"[TEMP] COOLING → fan duty={fan_duty_cycle}")
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
            _CUSTOM_PRINT_FUNC(f"[Light] ERROR reading light sensor (ADS1115?): {e} — skipping cycle.")
            time.sleep(SAMPLE_TIME)  # prevent rapid spin if ADS1115 is unavailable
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
    Graduated pulse irrigation based on soil moisture level.

      moisture <= 45%   → 2s pump pulse, wait 45 min
      moisture 46–50%   → 1.5s pump pulse, wait 45 min
      moisture 51–59%   → 1s pump pulse, wait 45 min
      moisture >= 60%   → pump OFF, check every 30s

    Safety guards:
      - RS485 None/NaN/0/<=5% all treated as sensor errors, never as dry soil
      - 3 consecutive failed/suspicious reads → pump locked for 1 hour
      - Max 4 pump activations per hour to prevent runaway irrigation
    """
    PUMP_DC          = 1800
    ABSORB_WAIT_SEC  = 2700   # 45 minutes after any pump pulse
    CHECK_INTERVAL   = 30

    MOISTURE_OK           = 60.0
    MOISTURE_MID          = 50.0
    MOISTURE_LOW          = 45.0
    MOISTURE_MIN_PLAUSIBLE = 5.0   # below this is a sensor error, not dry soil
    MAX_FAILURES_BEFORE_LOCK = 3   # consecutive bad reads before locking pump
    MAX_PUMPS_PER_HOUR    = 4      # safety cap on activations per hour
    SENSOR_LOCK_SEC       = 3600   # lock pump for 1 hour after repeated failures
    MAX_PUMP_SEC          = 3      # hard safety cap: pump never runs longer than this

    first_valid_read = False       # pump is blocked until first valid sensor reading
    consecutive_failures = 0
    pump_activation_times = []    # timestamps of recent pump activations

    def _fire_pump(pulse_sec):
        nonlocal pump_activation_times
        pulse_sec = min(pulse_sec, MAX_PUMP_SEC)  # hard safety cap
        now = datetime.datetime.now()

        # Remove activations older than 1 hour
        pump_activation_times = [t for t in pump_activation_times
                                  if (now - t).total_seconds() < 3600]

        if len(pump_activation_times) >= MAX_PUMPS_PER_HOUR:
            _CUSTOM_PRINT_FUNC(
                f"[Soil] SAFETY: pump fired {len(pump_activation_times)} times in the last hour "
                f"(max={MAX_PUMPS_PER_HOUR}). Skipping activation."
            )
            return False

        if light_pause_event is not None:
            light_pause_event.clear()
            time.sleep(0.2)

        _CUSTOM_PRINT_FUNC(
            f"[Soil] Pump ON — {pulse_sec}s pulse at {now.strftime('%H:%M:%S')}"
        )
        env_actuators.set_water_pump_duty_cycle(PUMP_DC)
        env_actuators.set_mqtt_dc_value_water_pump(PUMP_DC)
        time.sleep(pulse_sec)
        # Retry pump OFF — must succeed; I2C failure cannot leave pump running
        for _att in range(5):
            if env_actuators.set_water_pump_duty_cycle(0):
                break
            _CUSTOM_PRINT_FUNC(f"[Soil] WARNING: pump OFF command failed (attempt {_att+1}/5) — retrying")
            time.sleep(0.2)
        env_actuators.set_mqtt_dc_value_water_pump(0)
        _CUSTOM_PRINT_FUNC(
            f"[Soil] Pump OFF — finished {pulse_sec}s pulse at "
            f"{datetime.datetime.now().strftime('%H:%M:%S')}"
        )

        if light_pause_event is not None:
            light_pause_event.set()

        pump_activation_times.append(now)

        flow_rate = 0.0
        try:
            flow_rate = env_sensors.get_water_flow_rate()
        except Exception:
            pass

        db_handler.insert_pump_log('water', pulse_sec, PUMP_DC, flow_rate)
        _CUSTOM_PRINT_FUNC(
            f"[Soil] Waiting {ABSORB_WAIT_SEC}s for water to absorb..."
        )
        return True

    while True:
        soil_pause_event.wait()

        soil_semaphore.acquire()
        try:
            _, _, soil_humidity, _ = env_sensors.get_soil_values()
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[Soil] ERROR reading sensor (I2C/RS485?): {e} — pump forced OFF.")
            env_actuators.set_water_pump_duty_cycle(0)
            consecutive_failures += 1
            time.sleep(CHECK_INTERVAL)
            continue
        finally:
            soil_semaphore.release()

        # Failed read — None, NaN, 0, or below the plausible floor all mean RS485 failure
        _rs485_bad = (
            soil_humidity is None
            or soil_humidity != soil_humidity   # NaN (IEEE 754: NaN != NaN)
            or soil_humidity == 0.0
            or soil_humidity < MOISTURE_MIN_PLAUSIBLE
        )
        if _rs485_bad:
            consecutive_failures += 1
            _CUSTOM_PRINT_FUNC(
                f"[Soil] ERROR: RS485 returned invalid moisture={soil_humidity} — "
                f"treating as sensor failure, NOT dry soil. "
                f"Consecutive failures: {consecutive_failures}/{MAX_FAILURES_BEFORE_LOCK}."
            )
            if consecutive_failures >= MAX_FAILURES_BEFORE_LOCK:
                _CUSTOM_PRINT_FUNC(
                    f"[Soil] SAFETY LOCK: {consecutive_failures} consecutive bad reads. "
                    f"Pump disabled for {SENSOR_LOCK_SEC}s."
                )
                env_actuators.set_water_pump_duty_cycle(0)
                time.sleep(SENSOR_LOCK_SEC)
                consecutive_failures = 0
            else:
                time.sleep(CHECK_INTERVAL)
            continue

        # Successful read — reset failure counter
        consecutive_failures = 0
        if not first_valid_read:
            first_valid_read = True
            _CUSTOM_PRINT_FUNC("[Soil] First valid moisture read confirmed. Automatic pump control enabled.")
        _CUSTOM_PRINT_FUNC(f"[Soil] Moisture={soil_humidity:.1f}%")

        if soil_humidity >= MOISTURE_OK:
            _CUSTOM_PRINT_FUNC("[Soil] Moisture OK — no irrigation needed.")
            time.sleep(CHECK_INTERVAL)

        elif soil_humidity > MOISTURE_MID:
            _CUSTOM_PRINT_FUNC(f"[Soil] Moisture {soil_humidity:.1f}% (51–59%) — firing 1s pulse.")
            if _fire_pump(1):
                time.sleep(ABSORB_WAIT_SEC)
            else:
                time.sleep(CHECK_INTERVAL)

        elif soil_humidity > MOISTURE_LOW:
            _CUSTOM_PRINT_FUNC(f"[Soil] Moisture {soil_humidity:.1f}% (46–50%) — firing 1.5s pulse.")
            if _fire_pump(1.5):
                time.sleep(ABSORB_WAIT_SEC)
            else:
                time.sleep(CHECK_INTERVAL)

        else:
            _CUSTOM_PRINT_FUNC(f"[Soil] Moisture {soil_humidity:.1f}% (<= 45%) — firing 2s pulse.")
            if _fire_pump(2):
                time.sleep(ABSORB_WAIT_SEC)
            else:
                time.sleep(CHECK_INTERVAL)


def fertilizer_pump_control_task(
    env_sensors, env_actuators, setpoints,
    soil_semaphore, fertilizer_pause_event, db_handler,
    light_pause_event=None,
):
    """
    Graduated EC-based fertilization for lettuce.

    Every hour:
      EC >= 2000        → DANGER: fertilizer OFF, water dilution pulse, alert
      EC >= 1800        → too high: fertilizer OFF, water dilution pulse
      EC 1200–1800      → OK: fertilizer OFF; if pH > 6.8 log warning
      EC 1000–1200      → low: fire 1s fertilizer pulse, wait 1 hour
      EC 700–1000       → very low: fire 1.5s fertilizer pulse, wait 1 hour
      EC < 700          → critically low: fire 2s fertilizer pulse, wait 1 hour
    """
    FERT_DC         = 2662   # fertilizer pump duty cycle (~65%)
    WATER_DC        = 1800
    WATER_PULSE_SEC = 1
    SETTLE_WAIT_SEC = 3600
    CHECK_INTERVAL  = 3600

    EC_TARGET    = 1200.0
    EC_MID       = 1000.0
    EC_LOW       = 700.0
    EC_HIGH      = 1800.0
    EC_DANGER    = 2000.0
    PH_HIGH_WARN = 6.8

    # Safety thresholds — readings outside these are sensor errors, not real values
    EC_MIN_VALID  = 50.0    # EC=0 means sensor dead, not "no nutrients"
    EC_MAX_VALID  = 9000.0
    PH_MIN_VALID  = 2.0
    PH_MAX_VALID  = 12.0

    MAX_FAILURES_BEFORE_LOCK = 3
    SENSOR_LOCK_SEC          = 3600
    MAX_PUMPS_PER_HOUR       = 3
    MAX_PULSE_SEC            = 2   # hard safety cap on fertilizer pump pulse length

    first_valid_read = False       # pump blocked until first valid EC reading
    consecutive_failures  = 0
    pump_activation_times = []

    def _alert(msg):
        _CUSTOM_PRINT_FUNC(f"[Fertilizer] ALERT: {msg}")

    def _dilute_with_water():
        if light_pause_event is not None:
            light_pause_event.clear()
            time.sleep(0.2)
        _CUSTOM_PRINT_FUNC(f"[Fertilizer] Water pump ON — dilution pulse {WATER_PULSE_SEC}s")
        env_actuators.set_water_pump_duty_cycle(WATER_DC)
        time.sleep(WATER_PULSE_SEC)
        env_actuators.set_water_pump_duty_cycle(0)
        _CUSTOM_PRINT_FUNC("[Fertilizer] Water pump OFF — dilution done.")
        if light_pause_event is not None:
            light_pause_event.set()

    def _fire_fertilizer(pulse_sec):
        nonlocal pump_activation_times
        pulse_sec = min(pulse_sec, MAX_PULSE_SEC)  # hard safety cap
        now = datetime.datetime.now()

        # Remove activations older than 1 hour
        pump_activation_times = [t for t in pump_activation_times
                                  if (now - t).total_seconds() < 3600]

        if len(pump_activation_times) >= MAX_PUMPS_PER_HOUR:
            _CUSTOM_PRINT_FUNC(
                f"[Fertilizer] SAFETY: pump fired {len(pump_activation_times)}x in last hour "
                f"(max={MAX_PUMPS_PER_HOUR}). Skipping activation."
            )
            return False

        if light_pause_event is not None:
            light_pause_event.clear()
            time.sleep(0.2)

        _CUSTOM_PRINT_FUNC(
            f"[Fertilizer] Pump ON — {pulse_sec}s pulse at {now.strftime('%H:%M:%S')}"
        )
        pump_on_ok = False
        for _att in range(10):
            if env_actuators.set_fertilizer_pump_duty_cycle(FERT_DC):
                pump_on_ok = True
                break
            _CUSTOM_PRINT_FUNC(f"[Fertilizer] WARNING: pump ON failed (attempt {_att+1}/10)")
            time.sleep(0.1)
        if not pump_on_ok:
            _CUSTOM_PRINT_FUNC("[Fertilizer] ERROR: Could not turn ON fertilizer pump — aborting pulse.")
            env_actuators.set_fertilizer_pump_duty_cycle(0)
            if light_pause_event is not None:
                light_pause_event.set()
            return False
        time.sleep(pulse_sec)

        fert_flow_rate = 0.0
        try:
            fert_flow_rate = env_sensors.get_fertilizer_flow_rate()
        except Exception:
            pass

        # Retry pump OFF — must succeed; I2C failure cannot leave pump running
        for _att in range(10):
            if env_actuators.set_fertilizer_pump_duty_cycle(0):
                break
            _CUSTOM_PRINT_FUNC(f"[Fertilizer] WARNING: pump OFF failed (attempt {_att+1}/10) — retrying")
            time.sleep(0.1)

        _CUSTOM_PRINT_FUNC(
            f"[Fertilizer] Pump OFF — finished {pulse_sec}s at "
            f"{datetime.datetime.now().strftime('%H:%M:%S')}. "
            f"Cooldown {SETTLE_WAIT_SEC}s."
        )

        if light_pause_event is not None:
            light_pause_event.set()

        pump_activation_times.append(now)
        db_handler.insert_pump_log('fertilizer', pulse_sec, FERT_DC, fert_flow_rate)
        return True

    while True:
        fertilizer_pause_event.wait()

        # ── Read sensors ───────────────────────────────────────────────────────
        soil_semaphore.acquire()
        try:
            soil_ph, soil_ec, _, _ = env_sensors.get_soil_values()
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[Fertilizer] ERROR reading sensor: {e} — pump disabled this cycle.")
            env_actuators.set_fertilizer_pump_duty_cycle(0)
            consecutive_failures += 1
            time.sleep(CHECK_INTERVAL)
            continue
        finally:
            soil_semaphore.release()

        # ── Validate sensor readings before any pump decision ─────────────────
        # Check for None or NaN first — range comparison crashes on None
        if (soil_ec is None or soil_ph is None
                or soil_ec != soil_ec or soil_ph != soil_ph):   # NaN check
            consecutive_failures += 1
            _CUSTOM_PRINT_FUNC(
                f"[Fertilizer] ERROR: RS485 returned None/NaN — EC={soil_ec}, pH={soil_ph}. "
                f"Fertilizer pump disabled. "
                f"Consecutive failures: {consecutive_failures}/{MAX_FAILURES_BEFORE_LOCK}"
            )
            env_actuators.set_fertilizer_pump_duty_cycle(0)
            if consecutive_failures >= MAX_FAILURES_BEFORE_LOCK:
                _CUSTOM_PRINT_FUNC(
                    f"[Fertilizer] SAFETY LOCK: {consecutive_failures} bad RS485 reads. "
                    f"Pump disabled for {SENSOR_LOCK_SEC}s."
                )
                time.sleep(SENSOR_LOCK_SEC)
                consecutive_failures = 0
            else:
                time.sleep(CHECK_INTERVAL)
            continue

        ec_valid = EC_MIN_VALID <= soil_ec <= EC_MAX_VALID
        ph_valid = PH_MIN_VALID <= soil_ph <= PH_MAX_VALID

        if not ec_valid:
            consecutive_failures += 1
            _CUSTOM_PRINT_FUNC(
                f"[Fertilizer] ERROR: EC={soil_ec:.1f} is invalid (valid range: "
                f"{EC_MIN_VALID}–{EC_MAX_VALID}). Fertilizer pump disabled. "
                f"Consecutive failures: {consecutive_failures}/{MAX_FAILURES_BEFORE_LOCK}"
            )
            env_actuators.set_fertilizer_pump_duty_cycle(0)
            if consecutive_failures >= MAX_FAILURES_BEFORE_LOCK:
                _CUSTOM_PRINT_FUNC(
                    f"[Fertilizer] SAFETY LOCK: {consecutive_failures} bad EC reads. "
                    f"Pump disabled for {SENSOR_LOCK_SEC}s."
                )
                time.sleep(SENSOR_LOCK_SEC)
                consecutive_failures = 0
            else:
                time.sleep(CHECK_INTERVAL)
            continue

        if not ph_valid:
            _CUSTOM_PRINT_FUNC(
                f"[Fertilizer] WARNING: pH={soil_ph:.2f} is invalid — using EC only for decisions."
            )
            soil_ph = PH_HIGH_WARN  # treat as neutral warning, don't block fertilization

        consecutive_failures = 0
        if not first_valid_read:
            first_valid_read = True
            _CUSTOM_PRINT_FUNC("[Fertilizer] First valid EC/pH read confirmed. Automatic fertilizer control enabled.")
        _CUSTOM_PRINT_FUNC(f"[Fertilizer] EC={soil_ec:.1f} µS/cm  pH={soil_ph:.2f}")

        # ── 1. EC DANGER ───────────────────────────────────────────────────────
        if soil_ec >= EC_DANGER:
            env_actuators.set_fertilizer_pump_duty_cycle(0)
            _alert(
                f"DANGER: EC={soil_ec:.1f} µS/cm critically high (>= {EC_DANGER:.0f}). "
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
        if soil_ec >= EC_TARGET:
            env_actuators.set_fertilizer_pump_duty_cycle(0)
            _CUSTOM_PRINT_FUNC(
                f"[Fertilizer] EC OK — {soil_ec:.1f} µS/cm in target range 1200–1800."
            )
            if soil_ph > PH_HIGH_WARN:
                _alert(f"pH={soil_ph:.2f} high. Add pH Down manually.")
            time.sleep(CHECK_INTERVAL)
            continue

        # ── 4. EC 1000–1200 → 1 second pulse ──────────────────────────────────
        if soil_ec >= EC_MID:
            _CUSTOM_PRINT_FUNC(f"[Fertilizer] EC={soil_ec:.1f} (1000–1200) — firing 1s pulse.")
            if soil_ph > PH_HIGH_WARN:
                _alert(f"pH={soil_ph:.2f} high, but EC low. Fertilizing anyway.")
            if _fire_fertilizer(1):
                time.sleep(SETTLE_WAIT_SEC)
            else:
                time.sleep(CHECK_INTERVAL)
            continue

        # ── 5. EC 700–1000 → 1.5 second pulse ────────────────────────────────
        if soil_ec >= EC_LOW:
            _CUSTOM_PRINT_FUNC(f"[Fertilizer] EC={soil_ec:.1f} (700–1000) — firing 1.5s pulse.")
            if soil_ph > PH_HIGH_WARN:
                _alert(f"pH={soil_ph:.2f} high, but EC low. Fertilizing anyway.")
            if _fire_fertilizer(1.5):
                time.sleep(SETTLE_WAIT_SEC)
            else:
                time.sleep(CHECK_INTERVAL)
            continue

        # ── 6. EC < 700 → 2 second pulse ─────────────────────────────────────
        _CUSTOM_PRINT_FUNC(f"[Fertilizer] EC={soil_ec:.1f} critically low (< 700) — firing 2s pulse.")
        if soil_ph > PH_HIGH_WARN:
            _alert(f"pH={soil_ph:.2f} high, but EC critically low. Fertilizing anyway.")
        if _fire_fertilizer(2):
            time.sleep(SETTLE_WAIT_SEC)
        else:
            time.sleep(CHECK_INTERVAL)
