"""
control_loops.py — PID and hysteresis control loop thread functions.

Each function is designed to run as a daemon thread target.
All dependencies are passed as arguments so the functions are self-contained.
"""
import time
import datetime
from simple_pid import PID
from utils.utils import _CUSTOM_PRINT_FUNC
from telegram_alerts import (
    alert_sensor_error, alert_sensor_lock, alert_actuator_failure,
    alert_pump_rate_limit, alert_dangerous_ec, alert_ec_high,
    alert_ec_above_target, alert_ec_low, alert_ph_warning, alert_ph_critical,
    alert_moisture_critical, alert_moisture_high, alert_temperature_error,
)

# ── Fan schedule mode ─────────────────────────────────────────────────────────
# Renamed from FAN_SCHEDULE_TEST_ENABLED → FAN_SCHEDULE_ENABLED (Step 8).
# The day/night schedule is now permanent production behavior.
# Set to False only to restore temperature-PID fan control.
FAN_SCHEDULE_ENABLED      = True
FAN_SCHEDULE_TEST_ENABLED = FAN_SCHEDULE_ENABLED   # backward-compatible alias

FAN_DAY_START_HOUR   = 6   # 06:00 — fan at full day duty
FAN_NIGHT_START_HOUR = 20  # 20:00 — fan at reduced night duty

# Hard-coded fallback values — used when GH_Setpoints DB read fails or returns None.
# These constants are the safety net; the live values come from GH_Setpoints.
FAN_DAY_DUTY   = 4095            # 100%  (4095 = max on ESP32 PWM)
FAN_NIGHT_DUTY = int(4095 * 0.25)  # 25%  ≈ 1024


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
            alert_temperature_error(str(e))
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
            # Fan schedule overrides cooling fan — do not touch it
            if not FAN_SCHEDULE_TEST_ENABLED:
                env_actuators.set_fan_duty_cycle(0)

        elif control_output < 0:  # COOLING
            cool_power_scaled = abs(control_output)
            fan_duty_cycle = int(MIN_POWER + (POWER_RANGE * cool_power_scaled))
            fan_duty_cycle = max(MIN_POWER, min(MAX_POWER, fan_duty_cycle))
            env_actuators.set_heater_duty_cycle(0)
            env_actuators.set_heater_fan_duty_cycle(0)
            # Fan schedule overrides cooling fan — do not touch it
            if not FAN_SCHEDULE_TEST_ENABLED:
                if setpoints.get_operation_mode() == 'manual':
                    _CUSTOM_PRINT_FUNC("[TEMP] COOLING — MANUAL mode, fan not changed automatically")
                else:
                    _CUSTOM_PRINT_FUNC(f"[TEMP] COOLING → fan duty={fan_duty_cycle}")
                    if not env_actuators.set_fan_duty_cycle(fan_duty_cycle):
                        _CUSTOM_PRINT_FUNC("[TEMP] WARNING: fan set failed")
            else:
                _CUSTOM_PRINT_FUNC("[TEMP] COOLING — fan controlled by schedule, skipping PID override")

        else:  # IDLE
            _CUSTOM_PRINT_FUNC("[TEMP] IDLE — heater OFF")
            env_actuators.set_heater_duty_cycle(0)
            env_actuators.set_heater_fan_duty_cycle(0)
            # Fan schedule overrides — do not touch it
            if not FAN_SCHEDULE_TEST_ENABLED:
                if setpoints.get_operation_mode() != 'manual':
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
    Graduated pulse irrigation driven by the LIVE soil moisture setpoint.

    Thresholds are computed every cycle from the in-memory setpoints object:
      T = setpoints.get_soil_humidity_setpoint()   — moisture target %
      H = setpoints.get_soil_humidity_hysteresis() — dead-band %

    Irrigation bands (update automatically after AI Advisor Confirm):
      moisture >= T           → pump OFF (target reached)
      T-H   <= moisture < T   → pump OFF (acceptable range)
      T-H-5 <= moisture < T-H → 1s pulse, then 2h absorb wait
      T-H-10<= moisture < T-H-5 → 1.5s pulse, then 2h absorb wait
      moisture < T-H-10       → 2s pulse, then 2h absorb wait
      moisture > 75%          → high-moisture Telegram alert (absolute)

    Safety guards (unchanged):
      - RS485 None/NaN/0/<=5% treated as sensor errors, never as dry soil
      - 3 consecutive bad reads → pump locked for 1 hour
      - Max 4 pump activations per hour
      - 3s hard cap on any single pump pulse
    """
    PUMP_DC          = 1800
    ABSORB_WAIT_SEC  = 7200   # 2 hours after any pump pulse
    CHECK_INTERVAL   = 30     # seconds between moisture checks

    MOISTURE_MIN_PLAUSIBLE   = 5.0    # below this is a sensor error, not dry soil
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
            alert_pump_rate_limit("Water Pump", len(pump_activation_times), MAX_PUMPS_PER_HOUR)
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
            alert_sensor_error("Soil Moisture Sensor", None, str(e))
            env_actuators.set_water_pump_duty_cycle(0)
            consecutive_failures += 1
            soil_pause_event.wait(timeout=CHECK_INTERVAL)
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
                alert_sensor_lock("Soil Moisture Sensor", SENSOR_LOCK_SEC // 60)
                env_actuators.set_water_pump_duty_cycle(0)
                soil_pause_event.wait(timeout=SENSOR_LOCK_SEC)
                consecutive_failures = 0
            else:
                soil_pause_event.wait(timeout=CHECK_INTERVAL)
            continue

        # Successful read — reset failure counter
        consecutive_failures = 0
        if not first_valid_read:
            first_valid_read = True
            _CUSTOM_PRINT_FUNC("[Water Pump] First valid moisture read confirmed. Automatic pump control enabled.")

        # ── Read live setpoints every cycle ───────────────────────────────────
        # setpoints object is updated in-memory the moment AI Advisor Confirm runs,
        # so the very next 30-second cycle will use the new target automatically.
        moisture_target = setpoints.get_soil_humidity_setpoint()
        hysteresis      = setpoints.get_soil_humidity_hysteresis()

        # Compute dynamic irrigation bands from live setpoints
        band_ok         = moisture_target                       # pump OFF
        band_acceptable = moisture_target - hysteresis          # acceptable, pump OFF
        band_1s         = moisture_target - hysteresis - 5.0    # 1s pulse
        band_1_5s       = moisture_target - hysteresis - 10.0   # 1.5s pulse; below → 2s

        _CUSTOM_PRINT_FUNC(
            f"[Water Pump] Live moisture target={moisture_target:.1f}%  "
            f"hysteresis={hysteresis:.1f}%  "
            f"bands: OFF>={band_ok:.1f} | acceptable>={band_acceptable:.1f} | "
            f"1s>={band_1s:.1f} | 1.5s>={band_1_5s:.1f} | 2s<{band_1_5s:.1f}"
        )
        _CUSTOM_PRINT_FUNC(f"[Water Pump] Current moisture={soil_humidity:.1f}%")

        # ── High moisture alert (absolute threshold 75%, always active) ────────
        if soil_humidity > 75.0:
            alert_moisture_high(soil_humidity)

        # ── Pump decision based on dynamic bands ───────────────────────────────
        if soil_humidity >= band_ok:
            _CUSTOM_PRINT_FUNC(
                f"[Water Pump] Decision=OFF  "
                f"moisture {soil_humidity:.1f}% >= target {band_ok:.1f}%"
            )
            soil_pause_event.wait(timeout=CHECK_INTERVAL)

        elif soil_humidity >= band_acceptable:
            _CUSTOM_PRINT_FUNC(
                f"[Water Pump] Decision=OFF  "
                f"moisture {soil_humidity:.1f}% in acceptable band "
                f"{band_acceptable:.1f}–{band_ok:.1f}%"
            )
            soil_pause_event.wait(timeout=CHECK_INTERVAL)

        elif soil_humidity >= band_1s:
            _CUSTOM_PRINT_FUNC(
                f"[Water Pump] Decision=1s pulse  "
                f"moisture {soil_humidity:.1f}% in band {band_1s:.1f}–{band_acceptable:.1f}%"
            )
            if _fire_pump(1):
                soil_pause_event.wait(timeout=ABSORB_WAIT_SEC)
            else:
                soil_pause_event.wait(timeout=CHECK_INTERVAL)

        elif soil_humidity >= band_1_5s:
            _CUSTOM_PRINT_FUNC(
                f"[Water Pump] Decision=1.5s pulse  "
                f"moisture {soil_humidity:.1f}% in band {band_1_5s:.1f}–{band_1s:.1f}%"
            )
            if _fire_pump(1.5):
                soil_pause_event.wait(timeout=ABSORB_WAIT_SEC)
            else:
                soil_pause_event.wait(timeout=CHECK_INTERVAL)

        else:
            _CUSTOM_PRINT_FUNC(
                f"[Water Pump] Decision=2s pulse  "
                f"moisture {soil_humidity:.1f}% < {band_1_5s:.1f}%"
            )
            alert_moisture_critical(soil_humidity)
            if _fire_pump(2):
                soil_pause_event.wait(timeout=ABSORB_WAIT_SEC)
            else:
                soil_pause_event.wait(timeout=CHECK_INTERVAL)


def fertilizer_pump_control_task(
    env_sensors, env_actuators, setpoints,
    soil_semaphore, fertilizer_pause_event, db_handler,
    light_pause_event=None,
):
    """
    Graduated EC-based fertilization driven by the LIVE soil EC setpoint.

    EC_TARGET is read every cycle from the in-memory setpoints object:
      ec_target   = setpoints.get_soil_ec_setpoint()
      ec_close    = ec_target - 200   (acceptable band lower edge)
      ec_pulse_1s = ec_target - 400   (1s pulse lower edge)

    Decision bands (update automatically after AI Advisor Confirm):
      EC >= 2000             → DANGER: pump OFF + water dilution + Telegram DANGER (absolute)
      EC >= 1600             → too high: pump OFF + Telegram WARNING (absolute)
      EC > 1000              → above safe range: pump OFF + Telegram WARNING (absolute)
      EC >= ec_target        → at/above target: pump OFF, no alert
      ec_close <= EC < target→ acceptable (target-200 to target): pump OFF, no alert
      ec_pulse_1s <= EC < ec_close → low (target-400 to target-200): 1s pulse, 4h cooldown
      EC < ec_pulse_1s       → very low (< target-400): 1.5s pulse, 4h cooldown
      EC < 550               → Telegram WARNING "EC low" (absolute, fires alongside pump)

    pH is warning-only: thresholds unchanged.
    Anti-spam: Telegram cooldowns handled by telegram_alerts.py.
    """
    FERT_DC         = 2662   # fertilizer pump duty cycle (~65%)
    WATER_DC        = 1800
    WATER_PULSE_SEC = 1
    SETTLE_WAIT_SEC = 14400  # 4 hours after any fertilizer pulse
    CHECK_INTERVAL  = 3600

    # ── Absolute safety limits (never relative to setpoint) ───────────────────
    EC_DANGER       = 2000.0   # root burn risk — absolute, always
    EC_HIGH         = 1600.0   # dangerously high — absolute, always
    EC_ABOVE_WARN   = 1000.0   # above safe range → Telegram WARNING (absolute)
    EC_LOW_ALERT    = 550.0    # below this → Telegram WARNING "EC low" (absolute)
    # EC_TARGET, EC_CLOSE are computed live from setpoints each cycle (see while loop)
    PH_CRITICAL_LOW = 4.8   # CRITICAL alert threshold — roots at serious risk
    PH_LOW_WARN     = 5.2   # WARNING alert threshold — too low for lettuce
    PH_HIGH_WARN    = 7.5

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
            alert_pump_rate_limit("Fertilizer Pump", len(pump_activation_times), MAX_PUMPS_PER_HOUR)
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
            alert_actuator_failure("Fertilizer Pump", "ON", 10)
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
            alert_sensor_error("EC/pH Sensor", None, str(e))
            env_actuators.set_fertilizer_pump_duty_cycle(0)
            consecutive_failures += 1
            fertilizer_pause_event.wait(timeout=CHECK_INTERVAL)
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
                alert_sensor_lock("EC/pH Sensor", SENSOR_LOCK_SEC // 60)
                fertilizer_pause_event.wait(timeout=SENSOR_LOCK_SEC)
                consecutive_failures = 0
            else:
                fertilizer_pause_event.wait(timeout=CHECK_INTERVAL)
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
                fertilizer_pause_event.wait(timeout=SENSOR_LOCK_SEC)
                consecutive_failures = 0
            else:
                fertilizer_pause_event.wait(timeout=CHECK_INTERVAL)
            continue

        if not ph_valid:
            _CUSTOM_PRINT_FUNC(
                f"[Fertilizer] WARNING: pH={soil_ph:.2f} is invalid — using EC only for decisions."
            )
            soil_ph = PH_HIGH_WARN  # treat as neutral warning, don't block fertilization

        consecutive_failures = 0
        if not first_valid_read:
            first_valid_read = True
            _CUSTOM_PRINT_FUNC("[Fertilizer Pump] First valid EC/pH read confirmed. Automatic fertilizer control enabled.")

        # ── Read live EC setpoint every cycle ─────────────────────────────────
        # setpoints object is updated in-memory when AI Advisor Confirm runs,
        # so the very next hourly cycle will use the new target automatically.
        ec_target      = setpoints.get_soil_ec_setpoint()
        ec_close       = ec_target - 200.0   # acceptable zone lower edge  (target - 200)
        ec_pulse_1s    = ec_target - 400.0   # 1s pulse lower edge         (target - 400)
        # below ec_pulse_1s → 1.5s pulse

        _CUSTOM_PRINT_FUNC(
            f"[Fertilizer Pump] Live EC target = {ec_target:.0f} µS/cm"
        )
        _CUSTOM_PRINT_FUNC(
            f"[Fertilizer Pump] EC acceptable band = {ec_close:.0f}–{ec_target:.0f}"
        )
        _CUSTOM_PRINT_FUNC(
            f"[Fertilizer Pump] EC 1s pulse band = {ec_pulse_1s:.0f}–{ec_close:.0f}  |  "
            f"1.5s pulse band = <{ec_pulse_1s:.0f}"
        )
        _CUSTOM_PRINT_FUNC(
            f"[Fertilizer Pump] Current EC = {soil_ec:.1f} µS/cm  pH={soil_ph:.2f}"
        )

        # ── pH check (warning-only — does not block fertilization) ────────────
        if soil_ph < PH_CRITICAL_LOW:
            _alert(f"pH={soil_ph:.2f} CRITICALLY low (< {PH_CRITICAL_LOW}). Immediate action needed!")
            alert_ph_critical(soil_ph)
        elif soil_ph < PH_LOW_WARN:
            _alert(f"pH={soil_ph:.2f} too low (< {PH_LOW_WARN}). Add pH Up manually.")
            alert_ph_warning(soil_ph, "low")
        elif soil_ph > PH_HIGH_WARN:
            _alert(f"pH={soil_ph:.2f} too high (> {PH_HIGH_WARN}). Add pH Down manually.")
            alert_ph_warning(soil_ph, "high")

        # ── Low EC Telegram alert (absolute, fires alongside any pump decision) ─
        if soil_ec < EC_LOW_ALERT:
            alert_ec_low(soil_ec)

        # ── 1. EC DANGER (absolute >= 2000 — root burn risk) ──────────────────
        if soil_ec >= EC_DANGER:
            env_actuators.set_fertilizer_pump_duty_cycle(0)
            _alert(
                f"DANGER: EC={soil_ec:.1f} µS/cm critically high (>= {EC_DANGER:.0f}). "
                f"Root burn risk! Fertilizer pump LOCKED OFF. Activating water to dilute."
            )
            alert_dangerous_ec(soil_ec)
            _dilute_with_water()
            fertilizer_pause_event.wait(timeout=CHECK_INTERVAL)
            continue

        # ── 2. EC too high (absolute >= 1600) ─────────────────────────────────
        if soil_ec >= EC_HIGH:
            env_actuators.set_fertilizer_pump_duty_cycle(0)
            _CUSTOM_PRINT_FUNC(
                f"[Fertilizer Pump] Decision=OFF  "
                f"EC={soil_ec:.1f} too high (>= {EC_HIGH:.0f}). Pump OFF."
            )
            alert_ec_high(soil_ec)
            fertilizer_pause_event.wait(timeout=CHECK_INTERVAL)
            continue

        # ── 3. EC above safe range (absolute > 1000) ──────────────────────────
        if soil_ec > EC_ABOVE_WARN:
            env_actuators.set_fertilizer_pump_duty_cycle(0)
            _CUSTOM_PRINT_FUNC(
                f"[Fertilizer Pump] Decision=OFF  "
                f"EC={soil_ec:.1f} > {EC_ABOVE_WARN:.0f} — above safe range. Pump OFF."
            )
            alert_ec_above_target(soil_ec)
            fertilizer_pause_event.wait(timeout=CHECK_INTERVAL)
            continue

        # ── 4. EC at or above live target — pump OFF, no alert ────────────────
        if soil_ec >= ec_target:
            env_actuators.set_fertilizer_pump_duty_cycle(0)
            _CUSTOM_PRINT_FUNC(
                f"[Fertilizer Pump] Decision=OFF  "
                f"EC={soil_ec:.1f} >= target {ec_target:.0f}."
            )
            fertilizer_pause_event.wait(timeout=CHECK_INTERVAL)
            continue

        # ── 5. EC acceptable (target-200 to target) — pump OFF, no alert ──────
        if soil_ec >= ec_close:
            env_actuators.set_fertilizer_pump_duty_cycle(0)
            _CUSTOM_PRINT_FUNC(
                f"[Fertilizer Pump] Decision=OFF  "
                f"EC={soil_ec:.1f} in acceptable band {ec_close:.0f}–{ec_target:.0f}."
            )
            fertilizer_pause_event.wait(timeout=CHECK_INTERVAL)
            continue

        # ── 6. EC low (target-400 to target-200) → 1s pulse ──────────────────
        if soil_ec >= ec_pulse_1s:
            _CUSTOM_PRINT_FUNC(
                f"[Fertilizer Pump] Decision=1s pulse  "
                f"EC={soil_ec:.1f} in band {ec_pulse_1s:.0f}–{ec_close:.0f}."
            )
            if _fire_fertilizer(1):
                fertilizer_pause_event.wait(timeout=SETTLE_WAIT_SEC)
            else:
                fertilizer_pause_event.wait(timeout=CHECK_INTERVAL)
            continue

        # ── 7. EC very low (< target-400) → 1.5s pulse ───────────────────────
        _CUSTOM_PRINT_FUNC(
            f"[Fertilizer Pump] Decision=1.5s pulse  "
            f"EC={soil_ec:.1f} very low (< {ec_pulse_1s:.0f})."
        )
        if _fire_fertilizer(1.5):
            fertilizer_pause_event.wait(timeout=SETTLE_WAIT_SEC)
        else:
            fertilizer_pause_event.wait(timeout=CHECK_INTERVAL)


def fan_schedule_task(env_actuators, setpoints, check_interval_sec=60):
    """
    Day/night fan schedule (production mode — formerly 'test' mode):
      06:00–20:00  →  Fan at day duty   (from GH_Setpoints, fallback: FAN_DAY_DUTY   = 4095)
      20:00–06:00  →  Fan at night duty (from GH_Setpoints, fallback: FAN_NIGHT_DUTY = 1024)

    Duty values are read from GH_Setpoints every cycle so Layer 3 approved changes
    take effect on the next tick without a restart.
    If GH_Setpoints returns None, 0, or raises, the hardcoded fallback is used —
    the fan NEVER stops because of a DB or setter error.

    Runs as a daemon thread. Only active when FAN_SCHEDULE_ENABLED = True.
    In MANUAL operation mode the schedule is paused — the fan is not touched.
    check_interval_sec: how often (seconds) the schedule is re-evaluated.
    """
    _CUSTOM_PRINT_FUNC(
        f"[Fan Schedule] Task started — "
        f"Day({FAN_DAY_START_HOUR:02d}:00) fallback={FAN_DAY_DUTY}  "
        f"Night({FAN_NIGHT_START_HOUR:02d}:00) fallback={FAN_NIGHT_DUTY}"
    )
    last_mode = None

    while True:
        # In MANUAL mode: skip automatic fan control entirely
        if setpoints.get_operation_mode() == 'manual':
            _CUSTOM_PRINT_FUNC(
                "[Fan Schedule] MANUAL mode — automatic fan control paused"
            )
            last_mode = None   # reset so the next AUTONOMOUS transition logs cleanly
            time.sleep(check_interval_sec)
            continue

        now  = datetime.datetime.now()
        hour = now.hour

        is_day = FAN_DAY_START_HOUR <= hour < FAN_NIGHT_START_HOUR
        mode   = 'day' if is_day else 'night'

        # Read live duty from GH_Setpoints; fall back to module constant if unavailable
        try:
            duty = setpoints.get_fan_day_duty() if is_day else setpoints.get_fan_night_duty()
            if duty is None or not (0 < duty <= 4095):
                duty = FAN_DAY_DUTY if is_day else FAN_NIGHT_DUTY
        except Exception:
            duty = FAN_DAY_DUTY if is_day else FAN_NIGHT_DUTY

        pct = round((duty / 4095) * 100, 1)

        if mode != last_mode:
            if is_day:
                _CUSTOM_PRINT_FUNC(
                    f"[Fan Schedule] DAY mode — time={now.strftime('%H:%M')}  "
                    f"fan duty={duty} ({pct}%)"
                )
            else:
                _CUSTOM_PRINT_FUNC(
                    f"[Fan Schedule] NIGHT mode — time={now.strftime('%H:%M')}  "
                    f"fan duty={duty} ({pct}%)"
                )
            last_mode = mode

        env_actuators.set_fan_duty_cycle(duty)
        _CUSTOM_PRINT_FUNC(
            f"[Fan Schedule] time={now.strftime('%H:%M')}  "
            f"mode={'Day' if is_day else 'Night'}  fan={pct}%"
        )

        time.sleep(check_interval_sec)
