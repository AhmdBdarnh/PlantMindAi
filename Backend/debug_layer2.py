"""
debug_layer2.py — Show the real Layer 2 payload sent to OpenAI.

Reads live data from MongoDB and the latest actuator/sensor state,
builds the full prompt exactly as _build_prompt() produces it,
and prints it without making any OpenAI API call.

Run from the Backend directory:
    python3 debug_layer2.py
"""
import sys
import os
import threading
import pymongo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Load .env if python-dotenv is available ───────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Imports that need the project environment ─────────────────────────────────
from config import MONGO_URI, MONGO_DB_NAME
from mongo_db_handler import MongoDBHandler

print("="*80)
print("Connecting to MongoDB...")
print("="*80)
mongo = MongoDBHandler(MONGO_URI, MONGO_DB_NAME)
db    = mongo._MongoDBHandler__db


# ── Minimal mock for GH_Setpoints (reads from MongoDB) ───────────────────────
class _MockSetpoints:
    def get_all_setpoints(self):
        doc = db['setpoints'].find_one({'_id': 'greenhouse_setpoints'})
        if doc:
            return {
                'temperature':     float(doc.get('temperature',     21.0)),
                'humidity':        float(doc.get('humidity',        68.0)),
                'light':           float(doc.get('light',           600.0)),
                'soil_ph':         float(doc.get('soil_ph',         6.3)),
                'soil_ec':         float(doc.get('soil_ec',         850.0)),
                'soil_temp':       float(doc.get('soil_temp',       21.0)),
                'soil_moisture':   float(doc.get('soil_moisture',   50.0)),
                'soil_hysteresis': float(doc.get('soil_hysteresis', 10.0)),
                'water_flow':      float(doc.get('water_flow',      2.0)),
                'fertilizer_flow': float(doc.get('fertilizer_flow', 0.5)),
                'operation_mode':  doc.get('operation_mode', 'autonomous'),
            }
        print("[Mock] No setpoints document found — using defaults")
        return {
            'temperature': 21.0, 'humidity': 68.0, 'light': 600.0,
            'soil_ph': 6.3, 'soil_ec': 850.0, 'soil_temp': 21.0,
            'soil_moisture': 50.0, 'soil_hysteresis': 10.0,
            'water_flow': 2.0, 'fertilizer_flow': 0.5,
            'operation_mode': 'autonomous',
        }


# ── Populate app_loop._sensor_cache from MongoDB ──────────────────────────────
# Import app_loop first so its module-level lock and cache exist
import app_loop  # noqa: E402 — must come after sys.path insert

print("\n[Sensor Cache] Populating from latest MongoDB sensor readings...")

# Map MongoDB sensor_id  →  sensor cache key
_SENSOR_MAP = {
    'dht22.temperature':      'air_temperature',
    'dht22.humidity':         'air_humidity',
    'ads1115.light_intensity':'light_intensity',
    'soil_ph':                'soil_ph',
    'soil_ec':                'soil_ec',
    'soil_temp':              'soil_temperature',
    'soil_humidity':          'soil_humidity',
    'water_flow':             'water_flow',
    'fertilizer_flow':        'fertilizer_flow',
}

cache_patch = {}
for sensor_id, cache_key in _SENSOR_MAP.items():
    doc = db['sensors_data'].find_one(
        {'sensor_id': sensor_id},
        sort=[('timestamp', pymongo.DESCENDING)],
    )
    val = doc.get('sensor_value') if doc else None
    cache_patch[cache_key] = float(val) if val is not None else None
    ts  = doc.get('timestamp') if doc else None
    print(f"  {cache_key:22s} = {cache_patch[cache_key]}  "
          f"(timestamp: {ts})" if val is not None
          else f"  {cache_key:22s} = None  (no data in MongoDB)")

# Actuator states from the upserted actuators_data collection
print("\n[Actuator Cache] Populating from actuators_data...")
_ACTUATOR_MAP = {
    'heater':          ('heater_pct',  None),
    'light':           ('light_pct',   None),
    'fan':             ('fan_pct',     None),
    'water_pump':      (None,          'water_pump_state'),
    'fertilizer_pump': (None,          'fertilizer_pump_state'),
}
for actuator_id, (pct_key, state_key) in _ACTUATOR_MAP.items():
    doc = db['actuators_data'].find_one({'actuator_id': actuator_id})
    if doc:
        val  = float(doc.get('actuator_value', 0))
        pct  = round((val / 4095) * 100, 1)
        state= 'Off' if val == 0 else f'On at {pct}%'
        if pct_key:
            cache_patch[pct_key] = pct
        if state_key:
            cache_patch[state_key] = state
        print(f"  {actuator_id:20s} => {state}  (duty={val:.0f}/4095)")
    else:
        if pct_key:
            cache_patch[pct_key] = 0.0
        if state_key:
            cache_patch[state_key] = 'unknown (no actuators_data record)'
        print(f"  {actuator_id:20s} => not found in actuators_data")

with app_loop._sensor_cache_lock:
    app_loop._sensor_cache.update(cache_patch)

print("\n[system_state] Resource totals:")
for key in ['total_water_liters', 'total_energy_wh', 'total_fertilizer_liters']:
    doc = db['system_state'].find_one({'key': key})
    print(f"  {key} = {doc.get('value') if doc else 'not found'}")

# ── Initialize ai_setpoint_advisor with real MongoDB + mock setpoints ─────────
import ai_setpoint_advisor  # noqa: E402
ai_setpoint_advisor.init(_MockSetpoints(), mongo)

# ── Collect context data (same as what run_advisor() calls) ───────────────────
print("\n" + "="*80)
print("COLLECTING CONTEXT DATA  (same call as run_advisor)")
print("="*80)
data = ai_setpoint_advisor._collect_context_data()

print("\n[Missing / stale data flags]:")
missing = data.get("missing_data") or []
if missing:
    for m in missing:
        print(f"  ⚠  {m}")
else:
    print("  None — all data collected successfully.")

print("\n[Data age]:")
for k, v in (data.get("data_age") or {}).items():
    print(f"  {k}: {v}h ago" if v is not None else f"  {k}: unknown")

# ── Build final prompt ────────────────────────────────────────────────────────
print("\n" + "="*80)
print("FINAL PROMPT  (exact text sent to OpenAI)")
print("="*80 + "\n")
prompt = ai_setpoint_advisor._build_prompt(data)
print(prompt)

print("="*80)
print(f"Total prompt length: {len(prompt)} characters / ~{len(prompt)//4} tokens (estimate)")
print("="*80)
