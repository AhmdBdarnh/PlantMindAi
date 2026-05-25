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
from config import (
    WATER_PRICE_PER_LITER_NIS,
    ELECTRICITY_PRICE_PER_KWH_NIS,
    FERTILIZER_PRICE_PER_5_LITERS_NIS,
)

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

# Running resource totals — always growing, saved every 10s, survive restarts
_total_water_liters      = 0.0
_total_energy_wh         = 0.0
_total_fertilizer_liters = 0.0

# Previous sensor readings — used to compute deltas (handles hourly resets cleanly)
_prev_water_sensor      = 0.0
_prev_energy_sensor     = 0.0
_prev_fertilizer_sensor = 0.0


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


def get_total_water_liters() -> float:
    return _total_water_liters

def get_total_fertilizer_liters() -> float:
    return _total_fertilizer_liters

def get_total_energy_wh() -> float:
    return _total_energy_wh

def reset_resources():
    """Reset all resource counters to zero — call when starting a new plant cycle."""
    global _total_water_liters, _total_fertilizer_liters, _total_energy_wh
    global _prev_water_sensor, _prev_fertilizer_sensor, _prev_energy_sensor
    _total_water_liters      = 0.0
    _total_fertilizer_liters = 0.0
    _total_energy_wh         = 0.0
    # Reset the flow sensor hardware counters (total volume) to zero
    _env_sensors.reset_water_amount()
    _env_sensors.reset_fertilizer_amount()
    # Snapshot at zero so delta logic starts fresh
    _prev_water_sensor      = 0.0
    _prev_fertilizer_sensor = 0.0
    try:
        _, _, _, _e, _, _, _ = _env_sensors.get_electricity_values()
        _prev_energy_sensor = _e
    except Exception:
        _prev_energy_sensor = 0.0
    # Save zeros to MongoDB so restart doesn't reload old values
    _mongo_db.upsert_state('total_water_liters',      0.0)
    _mongo_db.upsert_state('total_fertilizer_liters', 0.0)
    _mongo_db.upsert_state('total_energy_wh',         0.0)
    # Clear all historical logs for the new plant cycle
    _mongo_db.clear_collection('sensors_data')
    _mongo_db.clear_collection('actuators_data')
    _mongo_db.clear_collection('resources')
    _mongo_db.clear_collection('pump_logs')
    _mongo_db.clear_collection('plant_images')
    # Update sensor cache immediately so frontend sees 0 right away
    with _sensor_cache_lock:
        _sensor_cache.update({
            'water_amount':         0.0,
            'fertilizer_amount':    0.0,
            'energy':               0.0,
            'water_cost_nis':       0.0,
            'electricity_cost_nis': 0.0,
            'fertilizer_cost_nis':  0.0,
            'total_cost_nis':       0.0,
        })
    _CUSTOM_PRINT_FUNC("[Resources] All counters and logs reset — new plant cycle started.")


def app_task():
    global last_sensor_update
    global _total_water_liters, _total_energy_wh, _total_fertilizer_liters
    global _prev_water_sensor, _prev_energy_sensor, _prev_fertilizer_sensor

    last_sensor_update    = datetime.datetime.now() - datetime.timedelta(seconds=10)
    last_actuators_update = datetime.datetime.now() - datetime.timedelta(seconds=1)

    # Load last-saved running totals so restarts never lose data
    saved = _mongo_db.get_state('total_water_liters')
    if saved is not None:
        _total_water_liters = float(saved)
    saved = _mongo_db.get_state('total_energy_wh')
    if saved is not None:
        _total_energy_wh = float(saved)
    saved = _mongo_db.get_state('total_fertilizer_liters')
    if saved is not None:
        _total_fertilizer_liters = float(saved)

    # Snapshot sensor values at startup — used to avoid double-counting
    # (sensors may have resumed from their own saved state)
    _prev_water_sensor      = _env_sensors.get_total_water_amount()
    _prev_fertilizer_sensor = _env_sensors.get_total_fertilizer_amount()
    try:
        _, _, _, _e, _, _, _ = _env_sensors.get_electricity_values()
        _prev_energy_sensor = _e
    except Exception:
        _prev_energy_sensor = 0.0

    _CUSTOM_PRINT_FUNC(
        f"[Resources] Loaded totals — "
        f"water={_total_water_liters:.3f}L  "
        f"energy={_total_energy_wh:.3f}Wh  "
        f"fertilizer={_total_fertilizer_liters:.3f}L"
    )

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
      try:
        # ── Sensor reads every 10 s ───────────────────────────────────────────
        if (datetime.datetime.now() - last_sensor_update).total_seconds() > 10:
            # Defaults so cache update never fails on a partial read
            air_temp_c = air_temp_f = air_humidity = 0.0
            light_intensity = 0.0
            soil_ph = soil_ec = soil_humidity = soil_temp = 0.0
            voltage = current = power = energy = frequency = power_factor = 0.0
            alarm = False

            _temp_sem.acquire()
            try:
                air_temp_c   = _env_sensors.get_air_temperature_C()
                air_temp_f   = _env_sensors.get_air_temperature_F()
                air_humidity = _env_sensors.get_air_humidity()
            except Exception as e:
                _CUSTOM_PRINT_FUNC(f"[AppLoop] Error reading temperature: {e}")
            finally:
                _temp_sem.release()

            _light_sem.acquire()
            try:
                light_intensity = _env_sensors.get_light_intensity()
            except Exception as e:
                _CUSTOM_PRINT_FUNC(f"[AppLoop] Error reading light: {e}")
            finally:
                _light_sem.release()

            _soil_sem.acquire()
            try:
                soil_ph, soil_ec, soil_humidity, soil_temp = _env_sensors.get_soil_values()
            except Exception as e:
                _CUSTOM_PRINT_FUNC(f"[AppLoop] Error reading soil: {e}")
            finally:
                _soil_sem.release()

            _elec_sem.acquire()
            try:
                voltage, current, power, energy, frequency, power_factor, alarm = (
                    _env_sensors.get_electricity_values()
                )
            except Exception as e:
                _CUSTOM_PRINT_FUNC(f"[AppLoop] Error reading electricity: {e}")
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

            # Water flow / fertilizer flow reads
            _wf = _ff = _wa = _fa = 0.0
            _wf_sem.acquire()
            try:
                _wf = _env_sensors.get_water_flow_rate()
                _wa = _env_sensors.get_total_water_amount()
                _ff = _env_sensors.get_fertilizer_flow_rate()
                _fa = _env_sensors.get_total_fertilizer_amount()
            except Exception as e:
                _CUSTOM_PRINT_FUNC(f"[AppLoop] Error reading flow sensors: {e}")
            finally:
                _wf_sem.release()

            # Delta-based accumulation
            delta_water      = max(0.0, _wa  - _prev_water_sensor)
            delta_energy     = max(0.0, energy - _prev_energy_sensor)
            delta_fertilizer = max(0.0, _fa  - _prev_fertilizer_sensor)

            _total_water_liters      = round(_total_water_liters      + delta_water,      4)
            _total_energy_wh         = round(_total_energy_wh         + delta_energy,     4)
            _total_fertilizer_liters = round(_total_fertilizer_liters + delta_fertilizer, 4)

            _prev_water_sensor      = _wa
            _prev_energy_sensor     = energy
            _prev_fertilizer_sensor = _fa

            water_cost_nis = round(_total_water_liters      * WATER_PRICE_PER_LITER_NIS,                4)
            elec_cost_nis  = round((_total_energy_wh / 1000.0) * ELECTRICITY_PRICE_PER_KWH_NIS,         4)
            fert_cost_nis  = round((_total_fertilizer_liters / 5.0) * FERTILIZER_PRICE_PER_5_LITERS_NIS, 4)
            total_cost_nis = round(water_cost_nis + elec_cost_nis + fert_cost_nis,                      4)

            # Update sensor cache FIRST — before any MQTT/MongoDB that could fail
            with _sensor_cache_lock:
                _sensor_cache.update({
                    'air_temperature':      air_temp_c,
                    'air_humidity':         air_humidity,
                    'light_intensity':      light_intensity,
                    'soil_ph':              soil_ph,
                    'soil_ec':              soil_ec,
                    'soil_humidity':        soil_humidity,
                    'soil_temperature':     soil_temp,
                    'water_flow':           _wf,
                    'water_amount':         _total_water_liters,
                    'fertilizer_flow':      _ff,
                    'fertilizer_amount':    _total_fertilizer_liters,
                    'voltage':              voltage,
                    'current':              current,
                    'power':                power,
                    'energy':               _total_energy_wh,
                    'frequency':            frequency,
                    'power_factor':         power_factor,
                    'water_cost_nis':       water_cost_nis,
                    'electricity_cost_nis': elec_cost_nis,
                    'fertilizer_cost_nis':  fert_cost_nis,
                    'total_cost_nis':       total_cost_nis,
                })

            _mqtt_handler.publish("env_monitoring_system/sensors/fertilizer_flow",     _ff)
            _mqtt_handler.publish("env_monitoring_system/resources/fertilizer_amount", _fa)

            # Save totals to system_state every 10s — survives any restart
            _mongo_db.upsert_state('total_water_liters',      _total_water_liters)
            _mongo_db.upsert_state('total_energy_wh',         _total_energy_wh)
            _mongo_db.upsert_state('total_fertilizer_liters', _total_fertilizer_liters)

            # Upsert resources collection (1 doc per resource, updated live)
            _mongo_db.upsert_resource_data("water consumption",      _total_water_liters,      cost_nis=water_cost_nis)
            _mongo_db.upsert_resource_data("energy consumption",     _total_energy_wh,         cost_nis=elec_cost_nis)
            _mongo_db.upsert_resource_data("fertilizer consumption", _total_fertilizer_liters, cost_nis=fert_cost_nis)

        # ── Sensor reset every N hours ────────────────────────────────────────
        # Totals are already saved every 10s, so just reset the hardware counters.
        # The delta logic in the sensor loop handles the reset seamlessly.
        if (datetime.datetime.now() - last_resources_reset_and_log).total_seconds() > (
            _resources_interval_hours * 3600
        ):
            _elec_sem.acquire()
            try:
                _env_sensors.reset_energy()
            except Exception as e:
                _CUSTOM_PRINT_FUNC(f"[Resources] Error resetting electricity sensor: {e}")
            finally:
                _elec_sem.release()

            _wf_sem.acquire()
            try:
                _env_sensors.reset_water_amount()
                _env_sensors.reset_fertilizer_amount()
            except Exception as e:
                _CUSTOM_PRINT_FUNC(f"[Resources] Error resetting water/fertilizer sensor: {e}")
            finally:
                _wf_sem.release()

            last_resources_reset_and_log = datetime.datetime.now()

            with open('consumption/last_resources_reset.txt', 'w') as file:
                file.write(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

            _CUSTOM_PRINT_FUNC("[Resources] Sensor reset done — totals preserved in system_state")

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
                _mongo_db.upsert_actuator_data("heater", heater_duty_cycle)

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
                _mongo_db.upsert_actuator_data("light", light_duty_cycle)

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
                _mongo_db.upsert_actuator_data("water pump", water_pump_duty_cycle)

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
                _mongo_db.upsert_actuator_data("fertilizer pump", fertilizer_pump_duty_cycle)

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
                _mongo_db.upsert_actuator_data("fan", fan_duty_cycle)

      except Exception as e:
          _CUSTOM_PRINT_FUNC(f"[AppLoop] Cycle error (will retry): {e}")
