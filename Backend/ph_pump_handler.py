"""
pH Pump handler — controls a USB water pump via a GPIO relay module.

Wiring:
  Relay IN  →  RPi GPIO pin (PH_PUMP_GPIO_PIN)
  Relay VCC →  RPi 5V
  Relay GND →  RPi GND
  Relay COM →  USB 5V wire of the pump (cut the red wire)
  Relay NO  →  pump side of the red wire

The relay defaults to OFF (pump off) when initialized.
"""

import importlib.util
import sys
import threading
from utils.utils import _CUSTOM_PRINT_FUNC

PH_PUMP_GPIO_PIN = 24


def _load_system_gpiod():
    if '_system_gpiod' in sys.modules:
        return sys.modules['_system_gpiod']
    so_path = '/usr/lib/python3/dist-packages/gpiod.cpython-311-aarch64-linux-gnu.so'
    spec = importlib.util.spec_from_file_location('_system_gpiod', so_path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.modules['_system_gpiod'] = mod
    return mod


_gpiod = _load_system_gpiod()


class PHPumpHandler:
    """
    Controls the pH pump via a single GPIO relay.
    Initializes to OFF immediately on startup.
    """

    def __init__(self, gpio_pin: int = PH_PUMP_GPIO_PIN):
        self._pin   = gpio_pin
        self._state = False
        self._lock  = threading.Lock()
        self._line  = None

        try:
            chip = _gpiod.Chip('/dev/gpiochip4')
            self._line = chip.get_line(gpio_pin)
            self._line.request(
                consumer="ph_pump",
                type=_gpiod.LINE_REQ_DIR_OUT,
                flags=0,
            )
            self._line.set_value(0)  # pump OFF on startup
            _CUSTOM_PRINT_FUNC(f"[PHPump] Relay initialized on GPIO {gpio_pin} — pump is OFF")
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[PHPump] Error initializing GPIO relay: {e}")

    def turn_on(self) -> bool:
        with self._lock:
            try:
                self._line.set_value(1)
                self._state = True
                _CUSTOM_PRINT_FUNC("[PHPump] pH pump ON")
                return True
            except Exception as e:
                _CUSTOM_PRINT_FUNC(f"[PHPump] Error turning on: {e}")
                return False

    def turn_off(self) -> bool:
        with self._lock:
            try:
                self._line.set_value(0)
                self._state = False
                _CUSTOM_PRINT_FUNC("[PHPump] pH pump OFF")
                return True
            except Exception as e:
                _CUSTOM_PRINT_FUNC(f"[PHPump] Error turning off: {e}")
                return False

    def get_state(self) -> bool:
        """Returns True if ON, False if OFF."""
        return self._state
