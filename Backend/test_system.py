#!/usr/bin/env python3
"""
test_system.py — PlantMind AI Hardware Diagnostic

Usage:
    python test_system.py --all          # full sensor + actuator test
    python test_system.py --sensors      # sensors only
    python test_system.py --actuators    # actuators only
    python test_system.py --dry-run      # print what would be tested, no hardware
"""
import sys
import os
import time
import math
import argparse
import datetime
import traceback
import glob
import subprocess
import io

# ── Make sure Backend package root is importable ──────────────────────────────
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# ── Silence internal library chatter during hardware init ─────────────────────
# We patch _CUSTOM_PRINT_FUNC to /dev/null while creating hardware objects,
# then restore it so our own output is unaffected.
import utils.utils as _utils_mod
_original_print = _utils_mod._CUSTOM_PRINT_FUNC

def _quiet(*args, **kwargs):
    pass

def _silence():
    _utils_mod._CUSTOM_PRINT_FUNC = _quiet

def _unsilence():
    _utils_mod._CUSTOM_PRINT_FUNC = _original_print

# ── ANSI helpers ──────────────────────────────────────────────────────────────
_GREEN  = "\033[92m"
_RED    = "\033[91m"
_YELLOW = "\033[93m"
_CYAN   = "\033[96m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_RST    = "\033[0m"

OK   = f"{_GREEN}✅{_RST}"
FAIL = f"{_RED}❌{_RST}"
WARN = f"{_YELLOW}⚠️ {_RST}"


# ── Result accumulator ────────────────────────────────────────────────────────
_results: list = []   # (component, kind, status, value, notes)

def _record(component: str, kind: str, status: str, value: str = "", notes: str = ""):
    """status: 'PASS' | 'FAIL' | 'WARN'"""
    _results.append((component, kind, status, value, notes))


# ── Value validation ──────────────────────────────────────────────────────────
def _bad(v) -> bool:
    """True if v is None, NaN, or ±Inf — unusable sensor data."""
    if v is None:
        return True
    try:
        return math.isnan(float(v)) or math.isinf(float(v))
    except (TypeError, ValueError):
        return True


def _in_range(v, lo, hi) -> bool:
    return not _bad(v) and lo <= v <= hi


# ── Print helpers ─────────────────────────────────────────────────────────────
def _section(title: str):
    print(f"\n{_BOLD}{_CYAN}{'=' * 60}{_RST}")
    print(f"{_BOLD}{_CYAN}  {title}{_RST}")
    print(f"{_BOLD}{_CYAN}{'=' * 60}{_RST}")


def _row(label: str, ok, value: str = "", note: str = "", skip: bool = False):
    """Print one test line and record the result."""
    if skip:
        icon   = WARN
        status = "WARN"
    elif ok:
        icon   = OK
        status = "PASS"
    else:
        icon   = FAIL
        status = "FAIL"

    val_str  = f"  {_GREEN}{value}{_RST}" if (value and ok)  else (f"  {_RED}{value}{_RST}" if value else "")
    note_str = f"  {_DIM}({note}){_RST}" if note else ""
    print(f"  {icon}  {label:<38}{val_str}{note_str}")
    _record(label, "", status, value, note)


def _emergency_off(actuators):
    """Best-effort attempt to cut all actuators."""
    try:
        actuators.stop_all_actuators()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
#  SENSOR TESTS
# ─────────────────────────────────────────────────────────────────────────────

def test_dht22(env_sensors):
    _section("DHT22 — Air Temperature & Humidity")
    # Give DHT22 two attempts (it can fail on first read)
    temp = hum = None
    for _ in range(3):
        try:
            temp = env_sensors.get_air_temperature_C()
            hum  = env_sensors.get_air_humidity()
            if temp and hum:
                break
        except Exception:
            pass
        time.sleep(2)

    t_ok = _in_range(temp, -10.0, 60.0)
    h_ok = _in_range(hum,   0.0, 100.0)

    # DHT22 returns previous value (0.0) on failure
    t_real = t_ok and temp != 0.0
    h_real = h_ok and hum  != 0.0

    _row("Air temperature (DHT22)", t_real,
         f"{temp:.1f} °C" if not _bad(temp) else str(temp),
         "" if t_real else "returned 0.0 — sensor may not be responding")

    _row("Air humidity (DHT22)", h_real,
         f"{hum:.1f} %" if not _bad(hum) else str(hum),
         "" if h_real else "returned 0.0 — sensor may not be responding")


def test_rs485_soil(env_sensors):
    _section("RS485 UART — Soil Sensor (/dev/ttyAMA0)")

    # Check serial port exists
    port_exists = os.path.exists("/dev/ttyAMA0")
    _row("RS485 port /dev/ttyAMA0", port_exists,
         "present" if port_exists else "not found",
         "" if port_exists else "check UART enabled in raspi-config")
    if not port_exists:
        return

    # Read all four values in one Modbus transaction
    try:
        ph, ec, moisture, soil_temp = env_sensors.get_soil_values()
    except Exception as e:
        _row("RS485 soil read",        False, "", f"Exception: {e}")
        _row("Soil moisture (RS485)",  False, "", "read failed")
        _row("Soil EC (RS485)",        False, "", "read failed")
        _row("Soil pH (RS485)",        False, "", "read failed")
        _row("Soil temperature (RS485)", False, "", "read failed")
        return

    # All-zeros means the sensor did not respond (modbus returned None internally)
    all_zero = (ph == 0.0 and ec == 0.0 and moisture == 0.0 and soil_temp == 0.0)
    _row("RS485 Modbus response", not all_zero,
         "OK" if not all_zero else "no response",
         "" if not all_zero else "check wiring & RS485 address (0x01)")

    m_ok = _in_range(moisture, 1.0, 100.0) and not all_zero
    _row("Soil moisture (RS485)", m_ok,
         f"{moisture:.1f} %" if not all_zero else "0.0 %",
         "" if m_ok else "0 or out-of-range — not dry soil, treat as sensor error")

    ec_ok = _in_range(ec, 50.0, 9000.0) and not all_zero
    _row("Soil EC (RS485)", ec_ok,
         f"{ec:.0f} µS/cm" if not all_zero else "0 µS/cm",
         "" if ec_ok else "0 or out-of-range — not low EC, treat as sensor error")

    ph_ok = _in_range(ph, 2.0, 12.0) and not all_zero
    _row("Soil pH (RS485)", ph_ok,
         f"{ph:.1f}" if not all_zero else "0.0",
         "" if ph_ok else "0 or out-of-range — sensor error")

    st_ok = _in_range(soil_temp, 0.0, 60.0) and not all_zero
    _row("Soil temperature (RS485)", st_ok,
         f"{soil_temp:.1f} °C" if not all_zero else "0.0 °C",
         "" if st_ok else "0 or out-of-range")


def test_ads1115(env_sensors):
    _section("ADS1115 — I2C ADC (0x48)")

    ads_ok = env_sensors._ads_ok
    _row("ADS1115 detected at 0x48", ads_ok,
         "detected" if ads_ok else "not found",
         "" if ads_ok else "light PID disabled; water/fertilizer pumps use RS485, not affected")

    if not ads_ok:
        _row("Light intensity (ADS1115 ch1)", False, "skipped", "ADS1115 not detected", skip=True)
        _row("Soil moisture ADS1115 (ch0)",   False, "skipped", "ADS1115 not detected", skip=True)
        return

    # Light intensity
    try:
        lux = env_sensors.get_light_intensity()
        lux_ok = not _bad(lux) and lux >= 0.0
        _row("Light intensity (ADS1115 ch1)", lux_ok,
             f"{lux:.1f} lux" if lux_ok else str(lux),
             "" if lux_ok else "unexpected value")
    except Exception as e:
        _row("Light intensity (ADS1115 ch1)", False, "", f"Exception: {e}")

    # ADS1115 soil moisture
    try:
        ads_moisture = env_sensors.get_soil_moisture_ads1115()
        am_ok = _in_range(ads_moisture, 0.0, 100.0)
        _row("Soil moisture ADS1115 (ch0)", am_ok,
             f"{ads_moisture:.1f} %" if am_ok else str(ads_moisture),
             "" if am_ok else "out of range")
    except Exception as e:
        _row("Soil moisture ADS1115 (ch0)", False, "", f"Exception: {e}")


def test_electricity(env_sensors):
    _section("PZEM-004T — Electricity Sensor (/dev/ttyAMA1)")

    port_exists = os.path.exists("/dev/ttyAMA1")
    _row("UART port /dev/ttyAMA1", port_exists,
         "present" if port_exists else "not found",
         "" if port_exists else "check UART enabled in raspi-config")
    if not port_exists:
        return

    try:
        voltage, current, power, energy, freq, pf, alarm = env_sensors.get_electricity_values()
    except Exception as e:
        _row("Electricity sensor read", False, "", f"Exception: {e}")
        return

    all_zero = (voltage == 0.0 and current == 0.0 and freq == 0.0)
    _row("PZEM-004T Modbus response", not all_zero,
         "OK" if not all_zero else "no response",
         "" if not all_zero else "check RS485 wiring to PZEM-004T")

    v_ok = _in_range(voltage, 0.0, 300.0) and not all_zero
    _row("Voltage (PZEM-004T)", v_ok,
         f"{voltage:.1f} V" if not all_zero else "0.0 V",
         "" if v_ok else "0V — not plugged in or sensor error")

    f_ok = _in_range(freq, 40.0, 70.0) if not all_zero else False
    _row("Frequency (PZEM-004T)", f_ok or all_zero,
         f"{freq:.1f} Hz" if not all_zero else "—",
         "" if (f_ok or all_zero) else f"unusual frequency {freq:.1f} Hz",
         skip=all_zero)

    _row("Current (PZEM-004T)", not _bad(current),
         f"{current:.3f} A",
         "no load is OK")

    _row("Power factor (PZEM-004T)", not _bad(pf),
         f"{pf:.2f}",
         "")


def test_cameras():
    _section("Cameras")

    # CSI camera (Raspberry Pi)
    try:
        from picamera2 import Picamera2
        cams = Picamera2.global_camera_info()
        csi_found = any('usb' not in c.get('Id', '').lower() for c in cams)
        _row("RPi CSI camera (picamera2)", csi_found,
             "detected" if csi_found else "not found",
             "" if csi_found else "not connected or libcamera not available")
    except Exception as e:
        _row("RPi CSI camera (picamera2)", False, "not found", f"{e}")

    # USB cameras — same name-based detection as rpi_camera.py
    def _find(name_pattern):
        for path in sorted(glob.glob('/dev/video[0-9]')):
            try:
                idx = int(path.replace('/dev/video', ''))
                result = subprocess.run(
                    ['v4l2-ctl', '--device', path, '--info'],
                    capture_output=True, text=True, timeout=2
                )
                info = result.stdout.lower()
                if name_pattern.lower() in info and 'video capture' in info:
                    return idx, path
            except Exception:
                pass
        return None, None

    for label, pattern in [
        ("2K USB camera",    "2k usb"),
        ("4K USB camera",    "4k usb"),
        ("USB Webcam",       "usb-webcam"),
    ]:
        idx, dev_path = _find(pattern)
        if idx is None:
            _row(label, False, "not found",
                 f"no v4l2 device matched '{pattern}'")
            continue

        # Try to open and grab one frame
        try:
            import cv2
            cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
            opened = cap.isOpened()
            frame_ok = False
            if opened:
                for _ in range(5):   # discard warmup frames
                    cap.read()
                ret, frame = cap.read()
                frame_ok = ret and frame is not None and frame.size > 0
            cap.release()
            _row(label, frame_ok,
                 f"frame {frame.shape[1]}×{frame.shape[0]} from {dev_path}" if frame_ok else f"found at {dev_path} but no frame",
                 "" if frame_ok else "device found but capture failed")
        except Exception as e:
            _row(label, False, f"found at {dev_path}", f"cv2 error: {e}")


def test_flow_sensors():
    _section("Flow Sensors (GPIO — gpiod)")

    from config import WATER_FLOW_SENSOR_PIN

    for label, pin in [
        ("Water flow sensor GPIO", WATER_FLOW_SENSOR_PIN),
        ("Fertilizer flow sensor GPIO", 16),
    ]:
        try:
            # Just verify the GPIO line can be acquired — we can't test actual
            # pulses without water actually flowing through the sensor.
            import importlib.util
            so_path = '/usr/lib/python3/dist-packages/gpiod.cpython-311-aarch64-linux-gnu.so'
            spec = importlib.util.spec_from_file_location('gpiod', so_path)
            mod  = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            chip = mod.Chip('/dev/gpiochip4')
            line = chip.get_line(pin)
            line.request(consumer="test_diag", type=mod.LINE_REQ_DIR_IN)
            line.release()
            _row(label, True, f"GPIO {pin} — line OK",
                 "pulse count not tested (needs water flow)")
        except Exception as e:
            _row(label, False, f"GPIO {pin}", f"{e}")


# ─────────────────────────────────────────────────────────────────────────────
#  ACTUATOR TESTS
# ─────────────────────────────────────────────────────────────────────────────

def _pulse(label, fn_on, fn_off, duty_on, pulse_sec, actuators):
    """
    Fire an actuator for pulse_sec, then force it off.
    Returns True if both ON and OFF commands succeeded.
    """
    try:
        ok_on = fn_on(duty_on)
        time.sleep(pulse_sec)
        ok_off = fn_off(0)
        if not ok_off:
            # retry OFF — safety critical
            for _ in range(3):
                time.sleep(0.2)
                ok_off = fn_off(0)
                if ok_off:
                    break
        return ok_on and ok_off
    except Exception as e:
        try:
            fn_off(0)
        except Exception:
            pass
        _emergency_off(actuators)
        return False


def test_esp32(env_actuators):
    _section("ESP32 — I2C Communication (0x30)")
    try:
        ok = env_actuators.restart_esp32()
        _row("ESP32 restart via I2C", ok,
             "responded OK" if ok else "no response",
             "" if ok else "check I2C wiring and ESP32_I2C_ADDRESS in config.py")
        if ok:
            time.sleep(3)   # let ESP32 boot
        return ok
    except Exception as e:
        _row("ESP32 restart via I2C", False, "", f"Exception: {e}")
        return False


def test_actuators_full(env_actuators, dry_run: bool):
    _section("Actuators — PWM via ESP32")

    if dry_run:
        for label in ["Water pump (1 s pulse)", "Fertilizer pump (0.5 s pulse)",
                      "Fan (1 s)", "Heater fan (1 s)", "Heater (0.5 s)",
                      "Grow light strip 1 (1 s)", "Grow light strip 2 (1 s)"]:
            _row(label, True, "DRY RUN — skipped", "", skip=True)
        return

    # ── Init all PWM channels (same params as app.py) ─────────────────────────
    _silence()
    inits = [
        ("light strip 1",   lambda: env_actuators.setup_light_strip_1_esp32(pin=16, channel=0, timer_src=0, frequency=5000, duty_cycle=0)),
        ("light strip 2",   lambda: env_actuators.setup_light_strip_2_esp32(pin=15, channel=5, timer_src=0, frequency=5000, duty_cycle=0)),
        ("heater",          lambda: env_actuators.setup_heater_esp32(pin=17, channel=1, timer_src=1, frequency=50, duty_cycle=0)),
        ("heater fan",      lambda: env_actuators.setup_heater_fan_esp32(pin=18, channel=2, timer_src=0, frequency=5000, duty_cycle=0)),
        ("fan",             lambda: env_actuators.setup_fan_esp32(pin=19, channel=3, timer_src=0, frequency=5000, duty_cycle=0)),
        ("water pump",      lambda: env_actuators.setup_water_pump_esp32(pin=33, channel=4, timer_src=2, frequency=1000, duty_cycle=0)),
        ("fertilizer pump", lambda: env_actuators.setup_fertilizer_pump_esp32(pin=25, channel=6, timer_src=2, frequency=1000, duty_cycle=0)),
    ]
    for name, fn in inits:
        fn()
        time.sleep(1)
    _unsilence()

    # Safety: force all OFF before any test
    _emergency_off(env_actuators)
    time.sleep(1)

    # ── Water pump — max 1 s pulse ────────────────────────────────────────────
    ok = _pulse("Water pump", env_actuators.set_water_pump_duty_cycle,
                env_actuators.set_water_pump_duty_cycle, 1800, 1.0, env_actuators)
    _row("Water pump (1 s pulse @DC 1800)", ok,
         "ON → OFF OK" if ok else "command failed",
         "max 1 s safety limit applied")

    time.sleep(1)

    # ── Fertilizer pump — max 0.5 s pulse ────────────────────────────────────
    ok = _pulse("Fertilizer pump", env_actuators.set_fertilizer_pump_duty_cycle,
                env_actuators.set_fertilizer_pump_duty_cycle, 2662, 0.5, env_actuators)
    _row("Fertilizer pump (0.5 s pulse @DC 2662)", ok,
         "ON → OFF OK" if ok else "command failed",
         "max 0.5 s safety limit applied")

    time.sleep(1)

    # ── Cooling fan ───────────────────────────────────────────────────────────
    ok = _pulse("Fan", env_actuators.set_fan_duty_cycle,
                env_actuators.set_fan_duty_cycle, 2000, 1.0, env_actuators)
    _row("Fan (1 s @DC 2000)", ok,
         "ON → OFF OK" if ok else "command failed")

    time.sleep(1)

    # ── Heater fan (NOT the heater element) ───────────────────────────────────
    ok = _pulse("Heater fan", env_actuators.set_heater_fan_duty_cycle,
                env_actuators.set_heater_fan_duty_cycle, 2000, 1.0, env_actuators)
    _row("Heater fan (1 s @DC 2000)", ok,
         "ON → OFF OK" if ok else "command failed")

    time.sleep(1)

    # ── Heater element — brief low-power pulse ────────────────────────────────
    ok = _pulse("Heater", env_actuators.set_heater_duty_cycle,
                env_actuators.set_heater_duty_cycle, 800, 0.5, env_actuators)
    _row("Heater element (0.5 s @DC 800)", ok,
         "ON → OFF OK" if ok else "command failed",
         "low DC, brief pulse — verify physically")

    time.sleep(1)

    # ── Grow light strip 1 ────────────────────────────────────────────────────
    ok = _pulse("Light strip 1", env_actuators.set_light_strip_1_duty_cycle,
                env_actuators.set_light_strip_1_duty_cycle, 2000, 1.0, env_actuators)
    _row("Grow light strip 1 (1 s @DC 2000)", ok,
         "ON → OFF OK" if ok else "command failed")

    time.sleep(1)

    # ── Grow light strip 2 ────────────────────────────────────────────────────
    ok = _pulse("Light strip 2", env_actuators.set_light_strip_2_duty_cycle,
                env_actuators.set_light_strip_2_duty_cycle, 2000, 1.0, env_actuators)
    _row("Grow light strip 2 (1 s @DC 2000)", ok,
         "ON → OFF OK" if ok else "command failed")

    # Final safety: everything OFF
    _emergency_off(env_actuators)
    print(f"\n  {OK}  All actuators forced OFF after testing.")


# ─────────────────────────────────────────────────────────────────────────────
#  SUMMARY & REPORT
# ─────────────────────────────────────────────────────────────────────────────

def print_summary():
    _section("Summary")
    col_w = [38, 8, 20, 30]
    header = (f"  {'Component':<{col_w[0]}}{'Status':<{col_w[1]}}"
              f"{'Value':<{col_w[2]}}{'Notes'}")
    print(f"{_BOLD}{header}{_RST}")
    print("  " + "─" * 100)

    passed = failed = warned = 0
    for (comp, kind, status, value, notes) in _results:
        icon = OK if status == "PASS" else (WARN if status == "WARN" else FAIL)
        if status == "PASS":
            passed += 1
        elif status == "FAIL":
            failed += 1
        else:
            warned += 1
        print(f"  {icon} {comp:<{col_w[0]-3}}{status:<{col_w[1]}}  "
              f"{value:<{col_w[2]}}{notes}")

    total = passed + failed + warned
    print("  " + "─" * 100)
    print(f"\n  Results: {_GREEN}{passed} passed{_RST}  "
          f"{_RED}{failed} failed{_RST}  "
          f"{_YELLOW}{warned} warnings{_RST}  "
          f"(total {total})")

    print()
    if failed == 0:
        print(f"  {OK}  {_BOLD}{_GREEN}System test PASSED{_RST}")
    else:
        print(f"  {FAIL}  {_BOLD}{_RED}System test FAILED — {failed} item(s) above need attention{_RST}")
    print()


def save_report(path: str = "hardware_test_report.txt"):
    """Write a plain-text version of the results to a file."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "=" * 70,
        f"PlantMind AI Hardware Test Report",
        f"Generated: {now}",
        "=" * 70,
        "",
        f"{'Component':<40}{'Status':<8}{'Value':<22}Notes",
        "-" * 90,
    ]
    passed = failed = warned = 0
    for (comp, kind, status, value, notes) in _results:
        lines.append(f"{comp:<40}{status:<8}{value:<22}{notes}")
        if status == "PASS":   passed  += 1
        elif status == "FAIL": failed  += 1
        else:                  warned  += 1

    lines += [
        "-" * 90,
        f"Passed: {passed}   Failed: {failed}   Warnings: {warned}",
        "",
        "RESULT: PASSED" if failed == 0 else f"RESULT: FAILED ({failed} failures)",
        "=" * 70,
    ]
    report_path = os.path.join(_BACKEND_DIR, path)
    with open(report_path, "w") as f:
        f.write("\n".join(lines))
    print(f"  {OK}  Report saved → {report_path}")


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="PlantMind AI hardware diagnostic"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all",       action="store_true", help="Run full sensor + actuator test")
    group.add_argument("--sensors",   action="store_true", help="Run sensor tests only")
    group.add_argument("--actuators", action="store_true", help="Run actuator tests only")
    group.add_argument("--dry-run",   action="store_true", help="Print what would be tested, no hardware activated")
    args = parser.parse_args()

    dry_run      = args.dry_run
    run_sensors  = args.all or args.sensors  or dry_run
    run_actuators = args.all or args.actuators or dry_run

    print()
    print(f"{_BOLD}{_CYAN}{'=' * 60}{_RST}")
    print(f"{_BOLD}{_CYAN}  PlantMind AI Hardware Test{_RST}")
    print(f"{_BOLD}{_CYAN}  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{_RST}")
    if dry_run:
        print(f"{_BOLD}{_YELLOW}  DRY RUN — no hardware will be activated{_RST}")
    print(f"{_BOLD}{_CYAN}{'=' * 60}{_RST}")

    # ── Import hardware drivers ───────────────────────────────────────────────
    try:
        import board
        import busio
        from config import (
            DHT22_PIN, WATER_FLOW_SENSOR_PIN,
            ADS1115_SOIL_CH, ADS1115_LIGHT_CH,
            ADS1115_SOIL_DRY_VAL, ADS1115_SOIL_WET_VAL,
            ESP32_I2C_ADDRESS, ESP32_ENDIANNESS,
        )
        from Sensors.sensors   import GH_Sensors
        from Actuators.actuators import GH_Actuators
    except ImportError as e:
        print(f"\n{FAIL}  Failed to import hardware drivers: {e}")
        print(f"       Run this script from the Backend/ directory.")
        sys.exit(1)

    # ── I2C bus ───────────────────────────────────────────────────────────────
    print(f"\n{_DIM}  Initialising I2C bus and sensor objects...{_RST}")
    _silence()
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
    except Exception as e:
        _unsilence()
        print(f"\n{FAIL}  Could not open I2C bus: {e}")
        sys.exit(1)

    # ── Sensors object ────────────────────────────────────────────────────────
    env_sensors = env_actuators = None
    try:
        env_sensors = GH_Sensors(i2c)
        env_sensors.set_dht22_pin(DHT22_PIN)
        env_sensors.set_soil_sensor_pins()
        env_sensors.set_soil_moisture_ads1115_channel(ADS1115_SOIL_CH)
        env_sensors.set_light_intensity_ads1115_channel(ADS1115_LIGHT_CH)
        env_sensors.calibrate_soil_moisture_ads1115(ADS1115_SOIL_DRY_VAL, ADS1115_SOIL_WET_VAL)
        env_sensors.set_electricity_sensor_pin()
    except Exception as e:
        _unsilence()
        print(f"\n{FAIL}  Sensor init failed: {e}")
        print(f"       {traceback.format_exc()}")
        sys.exit(1)

    # ── Actuators object ──────────────────────────────────────────────────────
    try:
        env_actuators = GH_Actuators(ESP32_I2C_ADDRESS, i2c, ESP32_ENDIANNESS)
    except Exception as e:
        _unsilence()
        print(f"\n{FAIL}  Actuator init failed: {e}")
        sys.exit(1)
    _unsilence()
    print(f"  {OK}  Hardware objects initialised.\n")

    # ── SENSOR TESTS ──────────────────────────────────────────────────────────
    if run_sensors:
        if dry_run:
            _section("Sensors — DRY RUN")
            for label in [
                "Air temperature (DHT22)",
                "Air humidity (DHT22)",
                "RS485 port /dev/ttyAMA0",
                "Soil moisture (RS485)",
                "Soil EC (RS485)",
                "Soil pH (RS485)",
                "Soil temperature (RS485)",
                "ADS1115 detected at 0x48",
                "Light intensity (ADS1115 ch1)",
                "PZEM-004T /dev/ttyAMA1",
                "Voltage (PZEM-004T)",
                "RPi CSI camera",
                "2K USB camera",
                "4K USB camera",
                "USB Webcam",
                "Water flow sensor GPIO",
                "Fertilizer flow sensor GPIO",
            ]:
                _row(label, True, "DRY RUN — skipped", "", skip=True)
        else:
            test_dht22(env_sensors)
            test_rs485_soil(env_sensors)
            test_ads1115(env_sensors)
            test_electricity(env_sensors)
            test_cameras()
            test_flow_sensors()

    # ── ACTUATOR TESTS ────────────────────────────────────────────────────────
    if run_actuators and not dry_run:
        _section("Actuator Test — Confirmation Required")
        print(f"\n  {_YELLOW}{_BOLD}WARNING:{_RST} Actuator test will briefly activate pumps, fan,")
        print(f"  heater, and grow lights.")
        print(f"  Make sure the greenhouse is safe to test.")
        print()
        try:
            answer = input(f"  Type  YES  to continue, anything else to skip: ").strip()
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer == "YES":
            esp32_ok = test_esp32(env_actuators)
            if esp32_ok:
                test_actuators_full(env_actuators, dry_run=False)
            else:
                _section("Actuators — Skipped (ESP32 not responding)")
                for label in ["Water pump", "Fertilizer pump", "Fan", "Heater fan",
                               "Heater", "Light strip 1", "Light strip 2"]:
                    _row(label, False, "skipped — ESP32 unreachable")
        else:
            _section("Actuators — Skipped by user")
            for label in ["Water pump", "Fertilizer pump", "Fan", "Heater fan",
                          "Heater", "Light strip 1", "Light strip 2"]:
                _row(label, True, "skipped by user", "", skip=True)

    elif run_actuators and dry_run:
        test_esp32_dry = True
        _section("ESP32 — I2C Communication (DRY RUN)")
        _row("ESP32 restart via I2C", True, "DRY RUN — skipped", "", skip=True)
        test_actuators_full(env_actuators, dry_run=True)

    # ── Final safety: ensure all actuators are OFF ────────────────────────────
    if env_actuators is not None and not dry_run:
        _emergency_off(env_actuators)

    # ── Summary ───────────────────────────────────────────────────────────────
    print_summary()
    save_report()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n  {WARN} Test interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n{FAIL}  Unexpected error: {e}")
        print(traceback.format_exc())
        sys.exit(1)
