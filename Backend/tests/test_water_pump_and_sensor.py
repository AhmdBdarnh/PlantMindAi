"""
Combined test: turns the water pump ON via I2C, reads the flow sensor, then turns pump OFF.
Run with backend OFF (needs GPIO 12 and I2C free).
Usage: python test_water_pump_and_sensor.py
"""
import gpiod
import time
import board
import busio
from datetime import timedelta

# ── ESP32 I2C settings (same as actuators.py) ──
ESP32_ADDRESS   = 0x30
JOB_INIT_PWM    = 0b000
JOB_SET_DUTY    = 0b001
PUMP_PIN        = 33
PUMP_CHANNEL    = 4
PUMP_TIMER_SRC  = 2
PUMP_FREQUENCY  = 1000
FRAME_SIZE      = 32

# ── Water flow sensor ──
GPIO_PIN           = 12
PULSES_PER_LITRE   = 450.0
TEST_DURATION_SEC  = 10   # seconds to run the pump during test


def send_frame(i2c, frame: bytes):
    while not i2c.try_lock():
        time.sleep(0.05)
    try:
        i2c.writeto(ESP32_ADDRESS, frame)
    finally:
        i2c.unlock()


def init_pump(i2c):
    """Send JOB_INIT_PWM — required once before set_duty works."""
    payload = (
        PUMP_FREQUENCY.to_bytes(4, 'big') +
        (0).to_bytes(2, 'big') +          # initial duty = 0
        PUMP_PIN.to_bytes(1, 'big') +
        PUMP_CHANNEL.to_bytes(1, 'big') +
        PUMP_TIMER_SRC.to_bytes(1, 'big')
    )
    first_byte = (JOB_INIT_PWM << 5) | (len(payload) & 0x1F)
    frame = first_byte.to_bytes(1, 'big') + payload
    frame += b'\x00' * (FRAME_SIZE - len(frame))
    send_frame(i2c, frame)
    time.sleep(1)  # give ESP32 time to initialize


def set_pump(i2c, duty_cycle: int):
    payload = (
        duty_cycle.to_bytes(2, 'big') +
        PUMP_PIN.to_bytes(1, 'big') +
        PUMP_CHANNEL.to_bytes(1, 'big')
    )
    first_byte = (JOB_SET_DUTY << 5) | (len(payload) & 0x1F)
    frame = first_byte.to_bytes(1, 'big') + payload
    frame += b'\x00' * (FRAME_SIZE - len(frame))
    send_frame(i2c, frame)


# ── Setup I2C ──
print("Initializing I2C...")
try:
    i2c = busio.I2C(board.SCL, board.SDA)
    print("I2C OK")
except Exception as e:
    print(f"ERROR: I2C failed: {e}")
    exit(1)

# ── Setup flow sensor ──
print(f"Opening GPIO {GPIO_PIN} for flow sensor...")
try:
    chip = gpiod.chip('/dev/gpiochip4')
    line = chip.get_line(GPIO_PIN)
    config = gpiod.line_request()
    config.consumer = 'water_test'
    config.request_type = gpiod.line_request.EVENT_BOTH_EDGES
    line.request(config)
    print("Flow sensor OK\n")
except Exception as e:
    print(f"ERROR: Could not open GPIO {GPIO_PIN}: {e}")
    exit(1)

# ── Run test ──
try:
    print("Initializing pump on ESP32...")
    init_pump(i2c)
    print("Turning pump ON...")
    set_pump(i2c, 4095)
    time.sleep(0.5)  # let water start moving

    print(f"Reading flow for {TEST_DURATION_SEC} seconds...\n")

    total_pulses = 0
    start = time.time()

    while time.time() - start < TEST_DURATION_SEC:
        if line.event_wait(timedelta(seconds=0.1)):
            event = line.event_read()
            if event.type == gpiod.line_event.RISING_EDGE:
                total_pulses += 1

        elapsed = time.time() - start
        flow_rate = (total_pulses / PULSES_PER_LITRE) / (elapsed / 60.0) if elapsed > 0 else 0
        print(f"\r  Elapsed: {elapsed:.1f}s | Pulses: {total_pulses} | Flow: {flow_rate:.3f} L/min", end='', flush=True)

    elapsed = time.time() - start
    total_litres = total_pulses / PULSES_PER_LITRE
    flow_rate    = total_litres / (elapsed / 60.0)

    print(f"\n\n── Results ──────────────────────────")
    print(f"  Total pulses : {total_pulses}")
    print(f"  Total water  : {total_litres * 1000:.1f} mL  ({total_litres:.4f} L)")
    print(f"  Avg flow rate: {flow_rate:.3f} L/min")

    if total_pulses == 0:
        print("\n  NO PULSES DETECTED — check sensor wiring on GPIO 12")
    else:
        print("\n  Sensor is working!")

finally:
    print("\nTurning pump OFF...")
    set_pump(i2c, 0)
    line.release()
    print("Done.")
