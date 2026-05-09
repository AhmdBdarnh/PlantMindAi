"""
actuator_helpers.py — Actuator convenience wrappers.

Call init(env_actuators) once at startup, then use set_all_light_strip_dc(),
set_all_heater_dc(), and set_actuators_manual_values() freely from any module.
"""
import time
from utils.utils import _CUSTOM_PRINT_FUNC

_env_actuators = None

_prev_light_dc_value     = 0
_prev_heater_dc_value    = 0
_prev_water_pump_dc_value = 0
_prev_fertilizer_pump_dc_value = 0
_prev_fan_dc_value       = 0


def init(env_actuators):
    global _env_actuators
    _env_actuators = env_actuators


def set_all_light_strip_dc(duty_cycle=0):
    """Set the duty cycle for both light strips."""
    while not _env_actuators.set_light_strip_1_duty_cycle(duty_cycle):
        _CUSTOM_PRINT_FUNC("Setting light strip 1 duty cycle again...")
        time.sleep(0.1)

    while not _env_actuators.set_light_strip_2_duty_cycle(duty_cycle):
        _CUSTOM_PRINT_FUNC("Setting light strip 2 duty cycle again...")
        time.sleep(0.1)

    return True


def set_all_heater_dc(duty_cycle=0):
    """Set the duty cycle for both heater and heater fan."""
    while not _env_actuators.set_heater_duty_cycle(duty_cycle):
        _CUSTOM_PRINT_FUNC("Setting heater duty cycle again...")
        time.sleep(0.1)

    while not _env_actuators.set_heater_fan_duty_cycle(duty_cycle):
        _CUSTOM_PRINT_FUNC("Setting heater fan duty cycle again...")
        time.sleep(0.1)

    return True


def set_actuators_manual_values():
    """Apply any MQTT-commanded duty-cycle changes that have not yet been sent to hardware."""
    global _prev_light_dc_value, _prev_heater_dc_value, _prev_water_pump_dc_value, _prev_fertilizer_pump_dc_value, _prev_fan_dc_value

    if _prev_fan_dc_value != _env_actuators.get_mqtt_dc_value_fan():
        if not _env_actuators.set_fan_duty_cycle(_env_actuators.get_mqtt_dc_value_fan()):
            _CUSTOM_PRINT_FUNC("Failed to set fan duty cycle, retrying...")
            time.sleep(0.1)
        _prev_fan_dc_value = _env_actuators.get_mqtt_dc_value_fan()

    if _prev_heater_dc_value != _env_actuators.get_mqtt_dc_value_heater():
        if not set_all_heater_dc(_env_actuators.get_mqtt_dc_value_heater()):
            _CUSTOM_PRINT_FUNC("Failed to set heater duty cycle, retrying...")
            time.sleep(0.1)
        _prev_heater_dc_value = _env_actuators.get_mqtt_dc_value_heater()

    if _prev_light_dc_value != _env_actuators.get_mqtt_dc_value_light_strip():
        if not set_all_light_strip_dc(_env_actuators.get_mqtt_dc_value_light_strip()):
            _CUSTOM_PRINT_FUNC("Failed to set light strip duty cycle, retrying...")
            time.sleep(0.1)
        _prev_light_dc_value = _env_actuators.get_mqtt_dc_value_light_strip()

    if _prev_water_pump_dc_value != _env_actuators.get_mqtt_dc_value_water_pump():
        if not _env_actuators.set_water_pump_duty_cycle(_env_actuators.get_mqtt_dc_value_water_pump()):
            _CUSTOM_PRINT_FUNC("Failed to set water pump duty cycle, retrying...")
            time.sleep(0.1)
        _prev_water_pump_dc_value = _env_actuators.get_mqtt_dc_value_water_pump()

    if _prev_fertilizer_pump_dc_value != _env_actuators.get_mqtt_dc_value_fertilizer_pump():
        if not _env_actuators.set_fertilizer_pump_duty_cycle(_env_actuators.get_mqtt_dc_value_fertilizer_pump()):
            _CUSTOM_PRINT_FUNC("Failed to set fertilizer pump duty cycle, retrying...")
            time.sleep(0.1)
        _prev_fertilizer_pump_dc_value = _env_actuators.get_mqtt_dc_value_fertilizer_pump()
