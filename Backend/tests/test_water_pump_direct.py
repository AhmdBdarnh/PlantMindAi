"""
test_water_pump_direct.py — Direct I2C test for water pump only.
No flow sensor. No Flask. No backend.

Run with the backend STOPPED:
  sudo systemctl stop plantmind   (or however you run the backend)
  python3 tests/test_water_pump_direct.py

Steps:
  1. Re-initialises the pump PWM channel on the ESP32
  2. Ramps duty cycle: 0 → 1000 → 2000 → 3000 → 4095 (100%)
  3. Holds at 100% for 5 seconds — you should hear/feel the pump
  4. Turns off

If the pump does NOT respond at any step, the problem is hardware
(wiring, 12V supply, motor driver) — not the code.
"""

import time
import board
import busio

ESP32_ADDRESS  = 0x30
JOB_INIT_PWM   = 0b000
JOB_SET_DUTY   = 0b001
PUMP_PIN       = 33
PUMP_CHANNEL   = 4
PUMP_TIMER_SRC = 2
PUMP_FREQUENCY = 1000
FRAME_SIZE     = 32


def send_frame(i2c, frame: bytes):
    while not i2c.try_lock():
        time.sleep(0.05)
    try:
        i2c.writeto(ESP32_ADDRESS, frame)
        print(f"  → Sent: {frame[:8].hex()}...")
    except Exception as e:
        print(f"  ✗ I2C write error: {e}")
    finally:
        i2c.unlock()


def init_pump(i2c):
    print("  Sending INIT frame (JOB_INIT_PWM)...")
    payload = (
        PUMP_FREQUENCY.to_bytes(4, 'big') +
        (0).to_bytes(2, 'big') +
        PUMP_PIN.to_bytes(1, 'big') +
        PUMP_CHANNEL.to_bytes(1, 'big') +
        PUMP_TIMER_SRC.to_bytes(1, 'big')
    )
    first_byte = (JOB_INIT_PWM << 5) | (len(payload) & 0x1F)
    frame = first_byte.to_bytes(1, 'big') + payload
    frame += b'\x00' * (FRAME_SIZE - len(frame))
    send_frame(i2c, frame)
    time.sleep(1.0)


def set_duty(i2c, duty_cycle: int):
    payload = (
        duty_cycle.to_bytes(2, 'big') +
        PUMP_PIN.to_bytes(1, 'big') +
        PUMP_CHANNEL.to_bytes(1, 'big')
    )
    first_byte = (JOB_SET_DUTY << 5) | (len(payload) & 0x1F)
    frame = first_byte.to_bytes(1, 'big') + payload
    frame += b'\x00' * (FRAME_SIZE - len(frame))
    send_frame(i2c, frame)


# ── Main ──────────────────────────────────────────────────────────────────────

print("=" * 50)
print("  Water Pump Direct I2C Test")
print("=" * 50)

print("\n[1] Connecting to I2C bus...")
try:
    i2c = busio.I2C(board.SCL, board.SDA)
    print("  I2C connected OK")
except Exception as e:
    print(f"  ERROR: {e}")
    exit(1)

print("\n[2] Initialising pump PWM channel on ESP32...")
init_pump(i2c)
print("  Init done")

steps = [
    (0,    "0%   — pump should be OFF"),
    (1000, "24%  — low speed"),
    (2000, "49%  — medium speed"),
    (3000, "73%  — high speed"),
    (4095, "100% — full power — hold 5 seconds"),
]

try:
    for duty, label in steps:
        print(f"\n[SET] duty={duty}  ({label})")
        set_duty(i2c, duty)
        hold = 5 if duty == 4095 else 2
        print(f"  Holding for {hold}s... (watch/listen to pump now)")
        time.sleep(hold)

    print("\n[RESULT]")
    print("  If pump made noise or vibrated at any step → hardware is fine, check 12V supply & driver wiring.")
    print("  If pump was completely silent at 4095 → check:")
    print("    1. 12V supply connected and switched ON")
    print("    2. Motor driver board powered and IN/OUT wires correct")
    print("    3. GPIO33 wire from ESP32 to driver board IN pin")

finally:
    print("\n[OFF] Turning pump off...")
    set_duty(i2c, 0)
    print("  Pump OFF. Test complete.")
