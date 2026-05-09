"""
app_loop.py — Main sensor-polling / actuator-logging background loop.

Call init() once at startup, then start a thread targeting app_task().
get_last_sensor_update() and _sensor_cache / _sensor_cache_lock are exported
for use by other modules (e.g. routes).
"""
import datetime
import threading

import actuator_helpers
from utils.utils import _CUSTOM_PRINT_FUNC

# ── Module-level state ────────────────────────────────────────────────────────
last_sensor_update = datetime.datetime.now() - datetime.timedelta(seconds=10)

_sensor_cache      = {}
_sensor_cache_lock = threading.Lock()

_env_sensors    = None
_env_actuators  = None
_setpoints      = None
_mqtt_handler   = None
_mongo_db       = None
_temp_sem       = None
_light_sem      = None
_soil_sem       = None
_elec_sem       = None
_wf_sem         = None
_resources_interval_hours = 1


def init(env_sensors, env_actuators, setpoints, mqtt_handler, mongo_db_handler,
         temperature_semaphore, light_semaphore, soil_semaphore,
         electricity_semaphore, water_flow_semaphore,
         resources_interval_hours=1):
    global _env_sensors, _env_actuators, _setpoints, _mqtt_handler, _mongo_db
    global _temp_sem, _light_sem, _soil_sem, _elec_sem, _wf_sem
    global _resources_interval_hours
    _env_sensors   = env_sensors
    _env_actuators = env_actuators
    _setpoints     = setpoints
    _mqtt_handler  = mqtt_handler
    _mongo_db      = mongo_db_handler
    _temp_sem      = temperature_semaphore
    _light_sem     = light_semaphore
    _soil_sem      = soil_semaphore
    _elec_sem      = electricity_semaphore
    _wf_sem        = water_flow_semaphore
    _resources_interval_hours = resources_interval_hours


def get_last_sensor_update():
    """Return the last sensor update timestamp as a formatted string."""
    return last_sensor_update.strftime('%Y-%m-%d %H:%M:%S')


def app_task():
    global last_sensor_update

    last_sensor_update   = datetime.datetime.now() - datetime.timedelta(seconds=10)
    last_actuators_update = datetime.datetime.now() - datetime.timedelta(seconds=1)

    # Retrieve last resource-reset time from local file
    try:
        with open('consumption/last_resources_reset.txt', 'r') as file:
            last_resources_reset_and_log = datetime.datetime.strptime(
                file.read().strip(), '%Y-%m-%d %H:%M:%S'
            )
            _env_sensors.set_last_resource_reset_time(
                last_resources_reset_and_log.strftime('%Y-%m-%d %H:%M:%S')
            )
            _CUSTOM_PRINT_FUNC(
                f"Last resources reset and log time was : {last_resources_reset_and_log}"
            )
    except FileNotFoundError:
        _CUSTOM_PRINT_FUNC(
            "No previous resources reset time found, setting to current time minus interval."
        )
        last_resources_reset_and_log = datetime.datetime.now() - datetime.timedelta(
            hours=_resources_interval_hours
        )
        _CUSTOM_PRINT_FUNC(
            f"Last resources reset and log time was : {last_resources_reset_and_log}"
        )

    prev_light_duty_cycle      = 0.0
    prev_heater_duty_cycle     = 0.0
    prev_heater_fan_duty_cycle = 0.0
    prev_fan_duty_cycle        = 0.0
    prev_water_pump_duty_cycle = 0.0
    prev_fertilizer_pump_duty_cycle = 0.0

    while True:
        # ── Sensor reads every 10 s ───────────────────────────────────────────
        if (datetime.datetime.now() - last_sensor_update).total_seconds() > 10:
            _temp_sem.acquire()
            try:
                air_temp_c  = _env_sensors.get_air_temperature_C()
                air_temp_f  = _env_sensors.get_air_temperature_F()
                air_humidity = _env_sensors.get_air_humidity()
            finally:
                _temp_sem.release()

            _light_sem.acquire()
            try:
                light_intensity = _env_sensors.get_light_intensity()
            finally:
                _light_sem.release()

            _soil_sem.acquire()
            try:
                soil_ph, soil_ec, soil_humidity, soil_temp = _env_sensors.get_soil_values()
            finally:
                _soil_sem.release()

            _elec_sem.acquire()
            try:
                voltage, current, power, energy, frequency, power_factor, alarm = (
                    _env_sensors.get_electricity_values()
                )
            except Exception as e:
                _CUSTOM_PRINT_FUNC(f"Error reading electricity sensor: {e}")
            finally:
                _elec_sem.release()

            # MQTT publish — sensors
            _mqtt_handler.publish("env_monitoring_system/sensors/air_temperature_C", air_temp_c)
            _mqtt_handler.publish("env_monitoring_system/sensors/air_humidity",      air_humidity)
            _mqtt_handler.publish("env_monitoring_system/sensors/light_intensity",   light_intensity)
            _mqtt_handler.publish("env_monitoring_system/sensors/soil_ph",           soil_ph)
            _mqtt_handler.publish("env_monitoring_system/sensors/soil_ec",           soil_ec)
            _mqtt_handler.publish("env_monitoring_system/sensors/soil_temp",         soil_temp)
            _mqtt_handler.publish("env_monitoring_system/sensors/soil_humidity",     soil_humidity)
            _mqtt_handler.publish("env_monitoring_system/sensors/voltage",           voltage)
            _mqtt_handler.publish("env_monitoring_system/sensors/current",           current)
            _mqtt_handler.publish("env_monitoring_system/resources/energy",          energy)
            _mqtt_handler.publish(
                "env_monitoring_system/resources/water_amount",
                _env_sensors.get_total_water_amount(),
            )

            # MongoDB insert — sensors
            _mongo_db.insert_sensor_data("air temp",        air_temp_c)
            _mongo_db.insert_sensor_data("air humidity",    air_humidity)
            _mongo_db.insert_sensor_data("light intensity", light_intensity)
            _mongo_db.insert_sensor_data("soil ph",         soil_ph)
            _mongo_db.insert_sensor_data("soil ec",         soil_ec)
            _mongo_db.insert_sensor_data("soil temp",       soil_temp)
            _mongo_db.insert_sensor_data("soil humidity",   soil_humidity)

            last_sensor_update = datetime.datetime.now()

            # Update sensor cache so Flask routes can respond instantly
            _wf_sem.acquire()
            try:
                _wf = _env_sensors.get_water_flow_rate()
                _wa = _env_sensors.get_total_water_amount()
                _ff = _env_sensors.get_fertilizer_flow_rate()
                _fa = _env_sensors.get_total_fertilizer_amount()
            finally:
                _wf_sem.release()

            _mqtt_handler.publish("env_monitoring_system/sensors/fertilizer_flow",     _ff)
            _mqtt_handler.publish("env_monitoring_system/resources/fertilizer_amount", _fa)

            with _sensor_cache_lock:
                _sensor_cache.update({
                    'air_temperature':   air_temp_c,
                    'air_humidity':      air_humidity,
                    'light_intensity':   light_intensity,
                    'soil_ph':           soil_ph,
                    'soil_ec':           soil_ec,
                    'soil_humidity':     soil_humidity,
                    'soil_temperature':  soil_temp,
                    'water_flow':        _wf,
                    'water_amount':      _wa,
                    'fertilizer_flow':   _ff,
                    'fertilizer_amount': _fa,
                    'voltage':           voltage,
                    'current':           current,
                    'power':             power,
                    'energy':            energy,
                    'frequency':         frequency,
                    'power_factor':      power_factor,
                })

        # ── Resource log & reset every N hours ───────────────────────────────
        if (datetime.datetime.now() - last_resources_reset_and_log).total_seconds() > (
            _resources_interval_hours * 3600
        ):
            _elec_sem.acquire()
            try:
                _, _, _, energy_cons, _, _, _ = _env_sensors.get_electricity_values()
                _mqtt_handler.publish("env_monitoring_system/resources/energy", energy_cons)
                _mongo_db.insert_resource_data("energy consumption", energy_cons)
                _mongo_db.resource_field_doc_temp(
                    "pzem-004t.energy", "energy_consumption", energy_cons, "Wh"
                )
                _env_sensors.reset_energy()
            except Exception as e:
                _CUSTOM_PRINT_FUNC(f"Error reading electricity sensor: {e}")
            finally:
                _elec_sem.release()

            _wf_sem.acquire()
            try:
                water_amount = _env_sensors.get_total_water_amount()
                _mqtt_handler.publish(
                    "env_monitoring_system/resources/water_amount", water_amount
                )
                _mongo_db.insert_resource_data("water consumption", water_amount)
                _env_sensors.reset_water_amount()
            except Exception as e:
                _CUSTOM_PRINT_FUNC(f"Error reading water flow sensor: {e}")
            finally:
                _wf_sem.release()

            last_resources_reset_and_log = datetime.datetime.now()

            with open('consumption/last_resources_reset.txt', 'w') as file:
                file.write(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

            _CUSTOM_PRINT_FUNC(
                f"Last resources reset and log time updated to: {last_resources_reset_and_log}"
            )

        # ── Actuator state publish every 1 s ─────────────────────────────────
        if (datetime.datetime.now() - last_actuators_update).total_seconds() > 1:
            last_actuators_update = datetime.datetime.now()

            if _setpoints.get_operation_mode() == 'manual':
                actuator_helpers.set_actuators_manual_values()

            _wf_sem.acquire()
            try:
                water_flow = _env_sensors.get_water_flow_rate()
                _mongo_db.insert_sensor_data("water flow", water_flow)
                _mqtt_handler.publish(
                    "env_monitoring_system/sensors/water_flow", water_flow
                )
            finally:
                _wf_sem.release()

            heater_duty_cycle      = _env_actuators.get_heater_duty_cycle()
            light_duty_cycle       = _env_actuators.get_light_strip_1_duty_cycle()
            water_pump_duty_cycle  = _env_actuators.get_water_pump_duty_cycle()
            fertilizer_pump_duty_cycle = _env_actuators.get_fertilizer_pump_duty_cycle()
            fan_duty_cycle         = _env_actuators.get_fan_duty_cycle()

            if heater_duty_cycle != prev_heater_duty_cycle:
                prev_heater_duty_cycle = heater_duty_cycle
                if heater_duty_cycle == 0:
                    _mqtt_handler.publish(
                        "env_monitoring_system/actuators/heater/state", 'Off'
                    )
                else:
                    _mqtt_handler.publish(
                        "env_monitoring_system/actuators/heater/state",
                        f'On at {heater_duty_cycle * 100 / 4095:.2f}%',
                    )
                _mongo_db.insert_actuator_data("heater", heater_duty_cycle)

            if light_duty_cycle != prev_light_duty_cycle:
                prev_light_duty_cycle = light_duty_cycle
                if light_duty_cycle == 0:
                    _mqtt_handler.publish(
                        "env_monitoring_system/actuators/light/state", 'Off'
                    )
                else:
                    _mqtt_handler.publish(
                        "env_monitoring_system/actuators/light/state",
                        f'On at {light_duty_cycle * 100 / 4095:.2f}%',
                    )
                _mongo_db.insert_actuator_data("light", light_duty_cycle)

            if water_pump_duty_cycle != prev_water_pump_duty_cycle:
                prev_water_pump_duty_cycle = water_pump_duty_cycle
                if water_pump_duty_cycle == 0:
                    _mqtt_handler.publish(
                        "env_monitoring_system/actuators/water_pump/state", 'Off'
                    )
                else:
                    _mqtt_handler.publish(
                        "env_monitoring_system/actuators/water_pump/state",
                        f'On at {water_pump_duty_cycle * 100 / 4095:.2f}%',
                    )
                _mongo_db.insert_actuator_data("water pump", water_pump_duty_cycle)

            if fertilizer_pump_duty_cycle != prev_fertilizer_pump_duty_cycle:
                prev_fertilizer_pump_duty_cycle = fertilizer_pump_duty_cycle
                if fertilizer_pump_duty_cycle == 0:
                    _mqtt_handler.publish(
                        "env_monitoring_system/actuators/fertilizer_pump/state", 'Off'
                    )
                else:
                    _mqtt_handler.publish(
                        "env_monitoring_system/actuators/fertilizer_pump/state",
                        f'On at {fertilizer_pump_duty_cycle * 100 / 4095:.2f}%',
                    )
                _mongo_db.insert_actuator_data("fertilizer pump", fertilizer_pump_duty_cycle)

            if fan_duty_cycle != prev_fan_duty_cycle:
                prev_fan_duty_cycle = fan_duty_cycle
                if fan_duty_cycle == 0:
                    _mqtt_handler.publish(
                        "env_monitoring_system/actuators/fan/state", 'Off'
                    )
                else:
                    _mqtt_handler.publish(
                        "env_monitoring_system/actuators/fan/state",
                        f'On at {fan_duty_cycle * 100 / 4095:.2f}%',
                    )
                _mongo_db.insert_actuator_data("fan", fan_duty_cycle)
