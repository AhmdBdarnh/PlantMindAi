"""
app.py — PlantMind AI entry point.

Initialises all hardware objects, wires up modules, and starts background threads.
Business logic lives in the imported modules; this file is intentionally thin.
"""
from dotenv import load_dotenv
load_dotenv()

import datetime
import logging
import os
import sys
import time
import threading

# ── Process lockfile — prevent two instances running at the same time ─────────
_LOCKFILE = '/tmp/plantmind_ai.lock'

def _acquire_lockfile():
    if os.path.exists(_LOCKFILE):
        try:
            with open(_LOCKFILE) as f:
                old_pid = int(f.read().strip())
            # Check if old PID is still alive
            os.kill(old_pid, 0)
            print(f"[STARTUP] ERROR: Another PlantMind AI process is already running (PID {old_pid}). Exiting.")
            sys.exit(1)
        except (ProcessLookupError, ValueError):
            # Old PID is dead — stale lockfile, safe to overwrite
            pass
    with open(_LOCKFILE, 'w') as f:
        f.write(str(os.getpid()))

def _release_lockfile():
    try:
        os.remove(_LOCKFILE)
    except FileNotFoundError:
        pass

import atexit
_acquire_lockfile()
atexit.register(_release_lockfile)

import board
import busio
from flask import Flask
from flask_cors import CORS

from Sensors.sensors    import GH_Sensors
from Actuators.actuators import GH_Actuators
from mqtt_handler       import MqttHandler
from mongo_db_handler   import MongoDBHandler
from aws_s3_handler     import S3Handler
from rpi_camera         import GH_Camera
from setpoints          import GH_Setpoints
from plant_health       import PlantHealthChecker
from serial_logger      import serial_logger_task

import actuator_helpers
import capture_manager
import app_loop
import control_loops
import growth_metrics
import ai_setpoint_advisor
import routes

from config import (
    RESOURCES_CONSUMPTION_LOG_AND_RESET_INTERVAL,
    DHT22_PIN,
    WATER_FLOW_SENSOR_PIN,
    ADS1115_SOIL_CH,
    ADS1115_LIGHT_CH,
    ADS1115_SOIL_DRY_VAL,
    ADS1115_SOIL_WET_VAL,
    ESP32_I2C_ADDRESS,
    ESP32_ENDIANNESS,
    MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASS,
    MONGO_URI, MONGO_DB_NAME,
    AWS_S3_BUCKET, AWS_REGION,
)
from utils.utils import _CUSTOM_PRINT_FUNC, set_serial_log_enabled

# ── External services ─────────────────────────────────────────────────────────

mqtt_handler = MqttHandler(MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASS)
mongo_db_handler = MongoDBHandler(MONGO_URI, MONGO_DB_NAME)

# ── Hardware setup ────────────────────────────────────────────────────────────

i2c = busio.I2C(board.SCL, board.SDA)
fertilizer_flow_sensor_pin = 16
_CUSTOM_PRINT_FUNC("[STARTUP] Initializing sensors — checking ADS1115 at 0x48...")
env_sensors = GH_Sensors(i2c, mongo_db_handler=mongo_db_handler)
# Use print() directly so this line is always visible regardless of serial-log state.
if env_sensors._ads_ok:
    print("[STARTUP] ADS1115 OK — light sensor active.")
else:
    print(
        "[STARTUP] WARNING: ADS1115 not detected. "
        "Light sensor disabled. Water pump and fertilizer pump are NOT affected "
        "(they use the RS485 soil sensor)."
    )
env_sensors.set_dht22_pin(DHT22_PIN)
env_sensors.set_soil_moisture_ads1115_channel(ADS1115_SOIL_CH)
env_sensors.set_light_intensity_ads1115_channel(ADS1115_LIGHT_CH)
env_sensors.calibrate_soil_moisture_ads1115(ADS1115_SOIL_DRY_VAL, ADS1115_SOIL_WET_VAL)
env_sensors.set_soil_sensor_pins()
env_sensors.set_electricity_sensor_pin()
try:
    env_sensors.set_water_flow_sensor_pin(WATER_FLOW_SENSOR_PIN)
except OSError as e:
    _CUSTOM_PRINT_FUNC(f"[Warning] Water flow sensor GPIO busy ({e}) — continuing without it")

try:
    env_sensors.set_fertilizer_flow_sensor_pin(fertilizer_flow_sensor_pin)
except OSError as e:
    _CUSTOM_PRINT_FUNC(f"[Warning] Fertilizer flow sensor GPIO busy ({e}) — continuing without it")

env_actuators = GH_Actuators(ESP32_I2C_ADDRESS, i2c, ESP32_ENDIANNESS)
setpoints     = GH_Setpoints(mqtt_handler, mongo_db_handler, env_actuators)


def _retry(fn, label, max_retries=3, delay=5):
    """Try fn() up to max_retries times; log and continue if all fail."""
    for attempt in range(1, max_retries + 1):
        if fn():
            return True
        _CUSTOM_PRINT_FUNC(
            f"[Warning] {label} failed (attempt {attempt}/{max_retries}), retrying..."
        )
        if attempt < max_retries:
            time.sleep(delay)
    _CUSTOM_PRINT_FUNC(
        f"[Warning] {label} gave up after {max_retries} attempts — continuing without it"
    )
    return False


# Reset ESP32 then wait for it to be ready
_retry(env_actuators.restart_esp32, "ESP32 restart", max_retries=3, delay=5)

last_date_time = datetime.datetime.now()
_CUSTOM_PRINT_FUNC("Initializing actuators...", end='')
while datetime.datetime.now() - last_date_time < datetime.timedelta(seconds=10):
    _CUSTOM_PRINT_FUNC(".", end='')
    time.sleep(1)

# PWM channel setup on ESP32
_retry(lambda: env_actuators.setup_light_strip_1_esp32(pin=16, channel=0, timer_src=0, frequency=5000, duty_cycle=0),  "light strip 1 setup")
time.sleep(1)
_retry(lambda: env_actuators.setup_light_strip_2_esp32(pin=15, channel=5, timer_src=0, frequency=5000, duty_cycle=0),  "light strip 2 setup")
time.sleep(1)
_retry(lambda: env_actuators.setup_heater_esp32(pin=17, channel=1, timer_src=1, frequency=50, duty_cycle=0),           "heater setup")
time.sleep(1)
_retry(lambda: env_actuators.setup_heater_fan_esp32(pin=18, channel=2, timer_src=0, frequency=5000, duty_cycle=0),     "heater fan setup")
time.sleep(1)
_retry(lambda: env_actuators.setup_fan_esp32(pin=19, channel=3, timer_src=0, frequency=5000, duty_cycle=0),            "fan setup")
time.sleep(5)
_retry(lambda: env_actuators.setup_water_pump_esp32(pin=33, channel=4, timer_src=2, frequency=1000, duty_cycle=0),     "water pump setup")
time.sleep(5)
_retry(lambda: env_actuators.setup_fertilizer_pump_esp32(pin=25, channel=6, timer_src=2, frequency=1000, duty_cycle=0), "fertilizer pump setup")
time.sleep(5)

# ── Explicit pump OFF — safety guarantee on every startup ────────────────────
_CUSTOM_PRINT_FUNC("[STARTUP] Setting all pumps to OFF (safety init)...")
env_actuators.set_water_pump_duty_cycle(0)
env_actuators.set_fertilizer_pump_duty_cycle(0)
_CUSTOM_PRINT_FUNC("[STARTUP] Water pump OFF. Fertilizer pump OFF.")

# ── MQTT subscriptions / publications ─────────────────────────────────────────

mqtt_handler.set_subscription("env_monitoring_system/actuators/heater/dc",     env_actuators.set_mqtt_dc_value_heater)
mqtt_handler.set_subscription("env_monitoring_system/actuators/light/dc",      env_actuators.set_mqtt_dc_value_light_strip)
mqtt_handler.set_subscription("env_monitoring_system/actuators/water_pump/dc", env_actuators.set_mqtt_dc_value_water_pump)
mqtt_handler.set_subscription("env_monitoring_system/actuators/fan/dc",        env_actuators.set_mqtt_dc_value_fan)
mqtt_handler.set_subscription("env_monitoring_system/actuators/fertilizer_pump/dc", env_actuators.set_mqtt_dc_value_fertilizer_pump)
mqtt_handler.set_subscription("loops/setpoints/temperature",                   setpoints.set_temperature_setpoint)
mqtt_handler.set_subscription("loops/setpoints/light_intensity",               setpoints.set_light_setpoint)
mqtt_handler.set_subscription("loops/setpoints/soil_moisture",                 setpoints.set_soil_humidity_setpoint)
mqtt_handler.set_subscription("loops/setpoints/water_flow",                    setpoints.set_water_flow_setpoint)
mqtt_handler.set_subscription("loops/setpoints/fertilizer_flow",               setpoints.set_fertilizer_flow_setpoint)
mqtt_handler.set_subscription("loops/setpoints/operation_mode",                setpoints.set_operation_mode)

mqtt_handler.set_publish("env_monitoring_system/sensors/air_temperature_C", 0)
mqtt_handler.set_publish("env_monitoring_system/sensors/air_humidity",       0)
mqtt_handler.set_publish("env_monitoring_system/sensors/light_intensity",    0)
mqtt_handler.set_publish("env_monitoring_system/sensors/soil_ph",            0)
mqtt_handler.set_publish("env_monitoring_system/sensors/soil_ec",            0)
mqtt_handler.set_publish("env_monitoring_system/sensors/soil_temp",          0)
mqtt_handler.set_publish("env_monitoring_system/sensors/soil_humidity",      0)
mqtt_handler.set_publish("env_monitoring_system/sensors/water_flow",         0)
mqtt_handler.set_publish("env_monitoring_system/sensors/fertilizer_flow",    0)
mqtt_handler.set_publish("env_monitoring_system/sensors/voltage",            0)
mqtt_handler.set_publish("env_monitoring_system/sensors/current",            0)
mqtt_handler.set_publish("env_monitoring_system/resources/energy",           0)
mqtt_handler.set_publish("env_monitoring_system/resources/water_amount",     0)
mqtt_handler.set_publish("env_monitoring_system/resources/fertilizer_amount", 0)
mqtt_handler.set_publish("env_monitoring_system/actuators/heater/state",     0)
mqtt_handler.set_publish("env_monitoring_system/actuators/light/state",      0)
mqtt_handler.set_publish("env_monitoring_system/actuators/water_pump/state", 0)
mqtt_handler.set_publish("env_monitoring_system/actuators/fan/state",        0)
mqtt_handler.set_publish("env_monitoring_system/actuators/fertilizer_pump/state", 0)
# ── MongoDB collections ───────────────────────────────────────────────────────

mongo_db_handler.create_collection("sensors_data", "air temp",       mongo_db_handler.sensor_field_doc_temp("dht22.temperature",       "temperature", 0.0, "C"))
mongo_db_handler.create_collection("sensors_data", "air humidity",   mongo_db_handler.sensor_field_doc_temp("dht22.humidity",          "humidity",    0.0, "%"))
mongo_db_handler.create_collection("sensors_data", "light intensity",mongo_db_handler.sensor_field_doc_temp("ads1115.light_intensity",  "intensity",   0.0, "Lux"))
mongo_db_handler.create_collection("sensors_data", "soil ph",        mongo_db_handler.sensor_field_doc_temp("soil_ph",                 "ph",          0.0, "pH"))
mongo_db_handler.create_collection("sensors_data", "soil ec",        mongo_db_handler.sensor_field_doc_temp("soil_ec",                 "ec",          0.0, "uS/cm"))
mongo_db_handler.create_collection("sensors_data", "soil temp",      mongo_db_handler.sensor_field_doc_temp("soil_temp",               "temperature", 0.0, "C"))
mongo_db_handler.create_collection("sensors_data", "soil humidity",  mongo_db_handler.sensor_field_doc_temp("soil_humidity",           "humidity",    0.0, "%"))
mongo_db_handler.create_collection("sensors_data", "water flow",     mongo_db_handler.sensor_field_doc_temp("water_flow",              "flow",        0.0, "L/min"))
mongo_db_handler.create_collection("sensors_data", "fertilizer flow", mongo_db_handler.sensor_field_doc_temp("fertilizer_flow",       "flow",        0.0, "L/min"))
mongo_db_handler.create_collection("sensors_data", "voltage",        mongo_db_handler.sensor_field_doc_temp("pzem-004t.voltage",       "voltage",     0.0, "V"))
mongo_db_handler.create_collection("sensors_data", "current",        mongo_db_handler.sensor_field_doc_temp("pzem-004t.current",       "current",     0.0, "A"))
mongo_db_handler.create_collection("resources",    "energy consumption",  mongo_db_handler.resource_field_doc_temp("pzem-004t.energy",     "energy_consumption", 0.0, "Wh"))
mongo_db_handler.create_collection("resources",    "water consumption",   mongo_db_handler.resource_field_doc_temp("water_flow.total_amount", "water_amount",   0.0, "L"))
mongo_db_handler.create_collection("resources",    "fertilizer consumption", mongo_db_handler.resource_field_doc_temp("fertilizer_flow.total_amount", "fertilizer_amount", 0.0, "L"))
mongo_db_handler.create_collection("actuators_data", "heater",       mongo_db_handler.actuator_field_doc_temp("heater",     "heater",     0))
mongo_db_handler.create_collection("actuators_data", "light",        mongo_db_handler.actuator_field_doc_temp("light",      "light",      0))
mongo_db_handler.create_collection("actuators_data", "water pump",   mongo_db_handler.actuator_field_doc_temp("water_pump", "water pump", 0))
mongo_db_handler.create_collection("actuators_data", "fan",          mongo_db_handler.actuator_field_doc_temp("fan",        "fan",        0))
mongo_db_handler.create_collection("actuators_data", "fertilizer pump", mongo_db_handler.actuator_field_doc_temp("fertilizer_pump", "fertilizer pump", 0))
mongo_db_handler.create_collection("plant_images",   "plant image",  {"_id": "", "image": "", "timestamp": datetime.datetime.now()})

# ── Other singletons ──────────────────────────────────────────────────────────

s3_handler           = S3Handler(AWS_S3_BUCKET, AWS_REGION)
plant_health_checker = PlantHealthChecker()
camera               = GH_Camera()

# ── Growth metrics init ───────────────────────────────────────────────────────
growth_metrics.init(s3_handler, mongo_db_handler)

# ── AI Setpoint Advisor init ──────────────────────────────────────────────────
ai_setpoint_advisor.init(setpoints, mongo_db_handler)

# ── Semaphores / events ───────────────────────────────────────────────────────

temperature_semaphore   = threading.Semaphore(1)
temperature_pause_event = threading.Event()
temperature_pause_event.set()

light_semaphore   = threading.Semaphore(1)
light_pause_event = threading.Event()
light_pause_event.set()

soil_semaphore   = threading.Semaphore(1)
soil_pause_event = threading.Event()
soil_pause_event.set()

fertilizer_pause_event = threading.Event()
fertilizer_pause_event.set()

electricity_semaphore   = threading.Semaphore(1)
electricity_pause_event = threading.Event()
electricity_pause_event.set()

water_flow_semaphore = threading.Semaphore(1)

# ── Module initialisation ─────────────────────────────────────────────────────

actuator_helpers.init(env_actuators)

capture_manager.init(
    camera, s3_handler, mongo_db_handler, plant_health_checker,
    env_actuators, setpoints, light_pause_event,
)

app_loop.init(
    env_sensors, env_actuators, setpoints, mqtt_handler, mongo_db_handler,
    temperature_semaphore, light_semaphore, soil_semaphore,
    electricity_semaphore, water_flow_semaphore,
    resources_interval_hours=RESOURCES_CONSUMPTION_LOG_AND_RESET_INTERVAL,
)

# ── Flask application ─────────────────────────────────────────────────────────

app = Flask(__name__)
CORS(app)

# ── Suppress repetitive polling GET logs (DEBUG_VERBOSE=false, the default) ───
# POST requests, errors (4xx/5xx), and all non-polling GETs are always shown.
# Set DEBUG_VERBOSE=true in .env to restore full werkzeug access logging.
class _QuietPollingFilter(logging.Filter):
    _QUIET = frozenset({
        '/api/sensors', '/api/actuators', '/api/operation_mode',
        '/api/setpoints', '/api/health',
        '/api/plant_health', '/api/plant-health/latest', '/api/plant-health/history',
        '/api/growth/latest', '/api/growth/history',
        '/api/pump-logs', '/api/capture_sessions',
        '/video_c1', '/video_c2', '/video_c4',
    })

    def filter(self, record):
        msg = record.getMessage()
        # Only consider suppressing GET requests
        if '"GET ' not in msg:
            return True
        # Always show error responses (4xx / 5xx)
        try:
            status = int(msg.rsplit('"', 1)[-1].split()[0])
            if status >= 400:
                return True
        except (ValueError, IndexError):
            return True
        # Suppress if the path matches a quiet endpoint.
        # Check for path followed by space, query string (?), or closing quote
        # so that /api/foo does not accidentally match /api/foobar.
        for path in self._QUIET:
            if f'"GET {path} ' in msg or f'"GET {path}?' in msg or f'"GET {path}"' in msg:
                return False
        return True

if not os.environ.get('DEBUG_VERBOSE', 'false').strip().lower() == 'true':
    logging.getLogger('werkzeug').addFilter(_QuietPollingFilter())

routes.init_routes(
    app,
    env_sensors, env_actuators, setpoints,
    camera, s3_handler, mongo_db_handler,
    temperature_semaphore, light_semaphore, soil_semaphore,
    electricity_semaphore, water_flow_semaphore,
)


def run_flask():
    app.run(host='0.0.0.0', port=5000, threaded=True, debug=False)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":

    setpoints.set_control_thread_event("temperature", temperature_pause_event)
    setpoints.set_control_thread_event("light",       light_pause_event)
    setpoints.set_control_thread_event("moisture",    soil_pause_event)
    setpoints.set_control_thread_event("fertilizer",  fertilizer_pause_event)
    # Restore saved mode from MongoDB; fall back to autonomous if nothing was saved
    saved_mode = setpoints.get_operation_mode()
    setpoints.set_operation_mode(saved_mode if saved_mode in ("manual", "autonomous") else "autonomous")
    _CUSTOM_PRINT_FUNC(f"[STARTUP] Operation mode: {setpoints.get_operation_mode()}. Pumps will activate only after first valid sensor reading.")
    # Clear old DB records and write all current setpoints fresh
    setpoints.save_all_setpoints()

    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    serial_logger_thread = threading.Thread(
        target=serial_logger_task,
        args=(
            env_sensors, app_loop.get_last_sensor_update, env_actuators, setpoints,
            temperature_semaphore, light_semaphore, soil_semaphore,
            water_flow_semaphore, electricity_semaphore,
        ),
    )

    temperature_thread = threading.Thread(
        target=control_loops.temperature_sp_adjustment_task,
        args=(env_sensors, env_actuators, setpoints, temperature_semaphore, temperature_pause_event),
    )
    light_thread = threading.Thread(
        target=control_loops.light_sp_adjustment_task,
        args=(env_sensors, env_actuators, setpoints, light_semaphore, light_pause_event),
    )
    soil_thread = threading.Thread(
        target=control_loops.set_soil_moisture_setpoint_task,
        args=(env_sensors, env_actuators, setpoints, soil_semaphore, soil_pause_event, mongo_db_handler, light_pause_event),
    )
    fertilizer_thread = threading.Thread(
        target=control_loops.fertilizer_pump_control_task,
        args=(env_sensors, env_actuators, setpoints, soil_semaphore, fertilizer_pause_event, mongo_db_handler),
        kwargs={'light_pause_event': light_pause_event},
    )
    app_thread = threading.Thread(target=app_loop.app_task)

    # 14:00 — health capture → s3://captures/ + PlantID health check
    daily_capture_thread = threading.Thread(
        target=capture_manager.daily_capture_task,
        kwargs={'hour': 14, 'minute': 0},
        daemon=True,
    )

    # 14:10 — dedicated growth capture → s3://growth_capture_input/  (no health check)
    daily_growth_capture_thread = threading.Thread(
        target=capture_manager.daily_growth_capture_task,
        kwargs={'hour': 14, 'minute': 10},
        daemon=True,
    )

    def _daily_growth_task():
        """
        Fire a growth analysis from S3 every day at 14:15 — 5 minutes after the
        dedicated growth capture (14:10) so images are guaranteed to be in S3.
        Reads from growth_capture_input/ which contains ONLY growth photos,
        completely separate from the health check captures in captures/.
        """
        import time
        import os as _os
        while True:
            now    = datetime.datetime.now()
            target = now.replace(hour=14, minute=15, second=0, microsecond=0)
            if now >= target:
                target += datetime.timedelta(days=1)
            sleep_secs = (target - now).total_seconds()
            _CUSTOM_PRINT_FUNC(
                f"[GrowthScheduler] Next growth analysis at "
                f"{target.strftime('%Y-%m-%d %H:%M')} (in {sleep_secs / 3600:.1f}h)"
            )
            time.sleep(sleep_secs)
            try:
                # Always read from growth_capture_input/ — never from captures/
                prefix = _os.environ.get('AWS_S3_GROWTH_PREFIX', 'growth_capture_input/')
                growth_metrics.run_from_s3(prefix=prefix)
            except Exception as e:
                _CUSTOM_PRINT_FUNC(f"[GrowthScheduler] Daily run failed: {e}")

    daily_growth_thread = threading.Thread(target=_daily_growth_task, daemon=True)

    # 15:30 — AI Setpoint Advisor: collect data → call GPT → save pending recommendation
    daily_ai_advisor_thread = threading.Thread(
        target=ai_setpoint_advisor.daily_advisor_task,
        kwargs={'hour': 15, 'minute': 30},
        daemon=True,
    )

    # ── Fan schedule test thread (2-day time-based schedule) ─────────────────
    if control_loops.FAN_SCHEDULE_TEST_ENABLED:
        fan_schedule_thread = threading.Thread(
            target=control_loops.fan_schedule_task,
            args=(env_actuators, setpoints),
            kwargs={'check_interval_sec': 60},
            daemon=True,
        )
        fan_schedule_thread.start()
        _CUSTOM_PRINT_FUNC(
            "[STARTUP] Fan schedule test ENABLED — "
            "06:00–20:00 = 100%,  20:00–06:00 = 25%"
        )
    else:
        _CUSTOM_PRINT_FUNC("[STARTUP] Fan schedule test DISABLED — using PID fan control.")

    temperature_thread.start()
    light_thread.start()
    soil_thread.start()
    fertilizer_thread.start()
    app_thread.start()
    daily_capture_thread.start()          # 14:00 — health capture → captures/
    daily_growth_capture_thread.start()   # 14:10 — growth capture → growth_capture_input/
    daily_growth_thread.start()           # 14:15 — growth analysis from growth_capture_input/
    daily_ai_advisor_thread.start()       # 15:30 — AI Setpoint Advisor

    _CUSTOM_PRINT_FUNC("Starting serial logger thread...")
    set_serial_log_enabled(True)
    serial_logger_thread.start()

    serial_logger_thread.join()
    temperature_thread.join()
    light_thread.join()
    soil_thread.join()
    fertilizer_thread.join()
    app_thread.join()
