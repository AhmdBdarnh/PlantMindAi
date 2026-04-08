"""
Quick test script for the YF-S201 water flow sensor (gpiod v2 API).
Run:
    cd Backend
    venv/bin/python3 tests/test_water_sensor.py
"""
import time
import gpiod
from datetime import timedelta

GPIO_PIN         = 12
PULSES_PER_LITRE = 450.0
TEST_DURATION    = 10  # seconds

print(f"=== YF-S201 Water Flow Sensor Test ===")
print(f"GPIO pin      : {GPIO_PIN}")
print(f"Test duration : {TEST_DURATION}s")
print()
print("Let water flow through the sensor now...")
print(f"Listening for {TEST_DURATION} seconds...\n")

chip = gpiod.Chip('/dev/gpiochip4')
lines = chip.request_lines(
    consumer="test_water_flow",
    config={GPIO_PIN: gpiod.LineSettings(
        direction=gpiod.line.Direction.INPUT,
        edge_detection=gpiod.line.Edge.RISING,
        bias=gpiod.line.Bias.PULL_UP,
    )}
)

pulse_count = 0
start = time.time()

try:
    while time.time() - start < TEST_DURATION:
        remaining = TEST_DURATION - (time.time() - start)
        if lines.wait_edge_events(timedelta(seconds=min(1.0, remaining))):
            for event in lines.read_edge_events():
                if event.event_type == gpiod.line.Edge.RISING:
                    pulse_count += 1
            elapsed = time.time() - start
            flow_lpm = (pulse_count / PULSES_PER_LITRE) * 60.0 / elapsed if elapsed > 0 else 0
            print(f"  Pulses: {pulse_count:4d}  |  Flow: {flow_lpm:.3f} L/min", end='\r')
finally:
    lines.release()

elapsed = time.time() - start
flow_lpm  = (pulse_count / PULSES_PER_LITRE) * 60.0 / elapsed if elapsed > 0 else 0
volume_ml = (pulse_count / PULSES_PER_LITRE) * 1000

print(f"\n\n=== Results ===")
print(f"Total pulses  : {pulse_count}")
print(f"Elapsed time  : {elapsed:.1f}s")
print(f"Avg flow rate : {flow_lpm:.3f} L/min")
print(f"Total volume  : {volume_ml:.1f} mL")
print()
if pulse_count == 0:
    print("NO pulses detected — is water actually flowing through the sensor?")
else:
    print(f"Sensor is working! Detected {pulse_count} pulses.")
