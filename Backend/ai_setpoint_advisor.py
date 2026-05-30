"""
ai_setpoint_advisor.py — AI-powered setpoint recommendation system for PlantMind AI.

Every day at 15:30 this module:
  1. Collects plant health, growth, sensor, and setpoint data from MongoDB + sensor cache
  2. Sends structured JSON to GPT (model configured via OPENAI_MODEL env var) for analysis
  3. Validates the AI's recommendations against hard safety limits
  4. Saves the recommendation to ai_setpoint_recommendations (status=pending)
  5. Sends a Telegram notification

The recommendation is NEVER applied automatically.
A human must Confirm (approve) or Reject via the frontend.
Only after Confirm does the backend apply changes via setpoints.set_*() methods.

Config (.env):
    OPENAI_API_KEY=...
    OPENAI_MODEL=gpt-5.5
    AI_APPLY_MODE=manual_review
    AI_USE_IMAGES=false
    AI_MAX_CALLS_PER_DAY=3
"""

import os
import json
import time
import threading
import datetime
import uuid

from utils.utils import _CUSTOM_PRINT_FUNC

# ── Config from env ───────────────────────────────────────────────────────────

OPENAI_API_KEY       = os.getenv('OPENAI_API_KEY', '')
OPENAI_MODEL         = os.getenv('OPENAI_MODEL', 'gpt-4o')
AI_APPLY_MODE        = os.getenv('AI_APPLY_MODE', 'manual_review')
AI_USE_IMAGES        = os.getenv('AI_USE_IMAGES', 'false').lower() == 'true'
AI_MAX_CALLS_PER_DAY = int(os.getenv('AI_MAX_CALLS_PER_DAY', '3'))

# ── Module-level singletons ───────────────────────────────────────────────────

_setpoints        = None
_mongo_db_handler = None
_run_lock         = threading.Lock()

# Rate limiting — reset at midnight
_call_count_today = 0
_call_count_date  = None
_rate_limit_lock  = threading.Lock()


def init(setpoints_obj, mongo_db_handler_obj):
    global _setpoints, _mongo_db_handler
    _setpoints        = setpoints_obj
    _mongo_db_handler = mongo_db_handler_obj
    _CUSTOM_PRINT_FUNC("[AI Advisor] Module initialized.")


# ── Lettuce optimal setpoint ranges (boundaries and guidelines for the AI) ────

LETTUCE_OPTIMAL = {
    "Temperature":     {"min": 18.0, "max": 24.0,   "ideal": 21.0,  "unit": "°C"},
    "Humidity":        {"min": 60.0, "max": 80.0,   "ideal": 68.0,  "unit": "%"},
    "Light":           {"min": 400.0, "max": 800.0, "ideal": 600.0, "unit": "sensor units (NOT calibrated lux)"},
    "Soil pH":         {"min": 5.5,  "max": 7.0,   "ideal": 6.3,   "unit": "pH"},
    "Soil EC":         {"min": 600.0, "max": 1200.0,"ideal": 850.0, "unit": "µS/cm"},
    "Soil Temp":       {"min": 18.0, "max": 24.0,   "ideal": 21.0,  "unit": "°C"},
    "Soil Moisture":   {"min": 40.0, "max": 70.0,   "ideal": 50.0,  "unit": "%"},
    "Soil Hysteresis": {"min": 5.0,  "max": 20.0,   "ideal": 10.0,  "unit": "%"},
}

# ── Safety limits — maximum allowed change per AI recommendation ──────────────

# reject_above: hard limit — any AI change beyond this is fully rejected
# absolute_max: soft ceiling — AI can go here but triggers needs_manual_review
# max_change:   normal preferred maximum — exceeding triggers needs_manual_review
SAFETY_LIMITS = {
    "Temperature":     {"max_change": 1.0,   "absolute_max": 2.0,   "reject_above": 2.0},
    "Humidity":        {"max_change": 5.0,   "absolute_max": 10.0,  "reject_above": 10.0},
    "Light":           {"max_change": 100.0, "absolute_max": 200.0, "reject_above": 300.0,
                        "notes": "Light sensor may not be calibrated — prefer keeping current value if uncertain."},
    "Soil pH":         {"max_change": 0.2,   "absolute_max": 0.3,   "reject_above": 0.3,
                        "notes": "pH changes ≥1.0 are always unsafe. Max ±0.3 pH."},
    "Soil EC":         {"max_change": 100.0, "absolute_max": 200.0, "reject_above": 200.0},
    "Soil Temp":       {"max_change": 1.0,   "absolute_max": 2.0,   "reject_above": 2.0},
    "Soil Moisture":   {"max_change": 10.0,  "absolute_max": 15.0,  "reject_above": 15.0},
    "Soil Hysteresis": {"max_change": 2.0,   "absolute_max": 5.0,   "reject_above": 5.0,
                        "notes": "Any change to Soil Hysteresis requires manual review."},
    # Locked — AI must never change these
    "Water Flow":      {"locked": True,  "reason": "Water flow must never be changed by AI"},
    "Fertilizer Flow": {"locked": True,  "reason": "Fertilizer flow must never be changed by AI"},
    "Operation Mode":  {"locked": True,  "reason": "Operation mode must never be changed by AI"},
}

PARAM_UNITS = {
    "Temperature":     "°C",
    "Humidity":        "%",
    "Light":           "",
    "Soil pH":         "pH",
    "Soil EC":         "µS/cm",
    "Soil Temp":       "°C",
    "Soil Moisture":   "%",
    "Soil Hysteresis": "%",
}

# Maps AI setpoint key names → GH_Setpoints setter method names
SETPOINT_KEY_TO_SETTER = {
    "Temperature":     "set_temperature_setpoint",
    "Humidity":        "set_humidity_setpoint",
    "Light":           "set_light_setpoint",
    "Soil pH":         "set_soil_ph_setpoint",
    "Soil EC":         "set_soil_ec_setpoint",
    "Soil Temp":       "set_soil_temp_setpoint",
    "Soil Moisture":   "set_soil_humidity_setpoint",
    "Soil Hysteresis": "set_soil_humidity_hysteresis",
}


# ── Rate limiting ─────────────────────────────────────────────────────────────

def _check_and_increment_rate_limit() -> bool:
    """Returns True if we are under the daily limit and increments the counter."""
    global _call_count_today, _call_count_date
    today = datetime.date.today()
    with _rate_limit_lock:
        if _call_count_date != today:
            _call_count_today = 0
            _call_count_date  = today
        if _call_count_today >= AI_MAX_CALLS_PER_DAY:
            return False
        _call_count_today += 1
        return True


def _decrement_rate_limit():
    """Roll back the counter if an attempt fails before any API call is made."""
    global _call_count_today
    with _rate_limit_lock:
        if _call_count_today > 0:
            _call_count_today -= 1


def get_rate_limit_info() -> dict:
    """Return current rate limit status (exposed to the manual-trigger endpoint)."""
    today = datetime.date.today()
    with _rate_limit_lock:
        if _call_count_date != today:
            remaining = AI_MAX_CALLS_PER_DAY
        else:
            remaining = max(0, AI_MAX_CALLS_PER_DAY - _call_count_today)
    return {
        "max_per_day": AI_MAX_CALLS_PER_DAY,
        "remaining_today": remaining,
        "date": today.isoformat(),
    }


# ── Data helpers ──────────────────────────────────────────────────────────────

def _safe_float(val, default=None):
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _clean_health_doc(doc: dict) -> dict:
    ts = doc.get("created_at")
    diseases = doc.get("diseases") or []
    # Keep only name + probability to reduce prompt size
    clean_diseases = []
    for d in diseases[:5]:
        if isinstance(d, dict):
            clean_diseases.append({
                "name":        d.get("name", "unknown"),
                "probability": _safe_float(d.get("probability")),
            })
    return {
        "is_healthy":         doc.get("is_healthy"),
        "health_probability": _safe_float(doc.get("health_probability")),
        "diseases":           clean_diseases,
        "date":               ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
    }


def _clean_growth_doc(doc: dict) -> dict:
    ts = doc.get("captured_at") or doc.get("created_at")
    return {
        "area_cm2":   _safe_float(doc.get("area_cm2")),
        "height_cm":  _safe_float(doc.get("height_cm")),
        "width_cm":   _safe_float(doc.get("width_cm")),
        "volume_cm3": _safe_float(doc.get("volume_cm3")),
        "agr":        _safe_float(doc.get("agr")),
        "rgr":        _safe_float(doc.get("rgr")),
        "growth_pct": _safe_float(doc.get("growth_pct")),
        "date":       ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
    }


def _compute_growth_trend(docs: list) -> dict:
    """Simple trend from 3–7 growth records (newest first)."""
    areas   = [_safe_float(d.get("area_cm2"))  for d in docs if _safe_float(d.get("area_cm2"))  is not None]
    heights = [_safe_float(d.get("height_cm")) for d in docs if _safe_float(d.get("height_cm")) is not None]
    if len(areas) < 2:
        return {"trend": "insufficient_data", "points": len(areas)}
    area_delta   = areas[0] - areas[-1]
    height_delta = heights[0] - heights[-1] if len(heights) >= 2 else None
    return {
        "trend":           "growing" if area_delta > 0 else ("stable" if area_delta == 0 else "declining"),
        "area_delta_cm2":  round(area_delta, 3),
        "height_delta_cm": round(height_delta, 3) if height_delta is not None else None,
        "data_points":     len(areas),
        "latest_area_cm2": areas[0],
        "oldest_area_cm2": areas[-1],
    }


# ── Data collection ───────────────────────────────────────────────────────────

def _data_age_hours(doc: dict, *timestamp_fields) -> float | None:
    """Return how many hours ago a document was timestamped, or None if not determinable."""
    for field in timestamp_fields:
        ts = doc.get(field)
        if ts is not None:
            try:
                if hasattr(ts, 'timestamp'):
                    delta = (datetime.datetime.now() - ts).total_seconds()
                    return round(delta / 3600, 1)
            except Exception:
                pass
    return None


def _collect_context_data() -> dict:
    """
    Collect all context data for the AI prompt.
    Missing fields are noted in the 'missing_data' list for data quality assessment.
    """
    import app_loop

    data = {
        "current_setpoints":      None,
        "current_sensors":        None,
        "sensor_stats_24h":       {},
        "plant_health_latest":    None,
        "plant_health_yesterday": None,
        "growth_latest":          None,
        "growth_yesterday":       None,
        "growth_trend":           None,
        "actuators_summary":      None,
        "pump_history":           None,
        "resource_usage":         None,
        "data_age":               {},
        "collection_timestamp":   datetime.datetime.now().isoformat(),
        "missing_data":           [],
    }

    # ── Current setpoints ─────────────────────────────────────────────────────
    try:
        data["current_setpoints"] = _setpoints.get_all_setpoints()
    except Exception as e:
        data["missing_data"].append(f"setpoints: {e}")

    # ── Current sensor readings from cache ────────────────────────────────────
    try:
        with app_loop._sensor_cache_lock:
            cache = dict(app_loop._sensor_cache)
        if cache:
            data["current_sensors"] = {
                "air_temperature":  _safe_float(cache.get("air_temperature")),
                "air_humidity":     _safe_float(cache.get("air_humidity")),
                "light_intensity":  _safe_float(cache.get("light_intensity")),
                "soil_ph":          _safe_float(cache.get("soil_ph")),
                "soil_ec":          _safe_float(cache.get("soil_ec")),
                "soil_humidity":    _safe_float(cache.get("soil_humidity")),
                "soil_temperature": _safe_float(cache.get("soil_temperature")),
                "water_flow":       _safe_float(cache.get("water_flow")),
                "fertilizer_flow":  _safe_float(cache.get("fertilizer_flow")),
            }
            _CUSTOM_PRINT_FUNC(
                f"[AI Advisor] sensor cache: OK — "
                f"temp={data['current_sensors']['air_temperature']}, "
                f"humidity={data['current_sensors']['air_humidity']}, "
                f"ph={data['current_sensors']['soil_ph']}, "
                f"ec={data['current_sensors']['soil_ec']}"
            )
        else:
            data["missing_data"].append("current_sensors: sensor cache is empty — sensor loop may not be running")
            _CUSTOM_PRINT_FUNC("[AI Advisor]   WARNING: sensor cache is empty")
    except Exception as e:
        data["missing_data"].append(f"current_sensors: {e}")
        _CUSTOM_PRINT_FUNC(f"[AI Advisor]   ERROR reading sensor cache: {e}")

    # ── 24h sensor stats from MongoDB ─────────────────────────────────────────
    # Each entry: display_name -> (sensor_id, min_plausible, max_plausible)
    # min/max are passed to get_sensor_stats() to exclude glitch/restart spikes
    # before computing avg/min/max so OpenAI receives clean statistics.
    sensor_ids = {
        "air_temperature":  ("dht22.temperature",       0.0,   31.0),
        "air_humidity":     ("dht22.humidity",           0.0,  100.0),
        "light_intensity":  ("ads1115.light_intensity",  0.0, 1500.0),
        "soil_ph":          ("soil_ph",                  2.0,   12.0),
        "soil_ec":          ("soil_ec",                 50.0, 9000.0),
        "soil_temperature": ("soil_temp",                5.0,   40.0),
        "soil_humidity":    ("soil_humidity",             1.0,  100.0),
        "water_flow":       ("water_flow",               0.0,   50.0),
        "fertilizer_flow":  ("fertilizer_flow",          0.0,   50.0),
    }
    for display_name, (sensor_id, min_val, max_val) in sensor_ids.items():
        try:
            stats = _mongo_db_handler.get_sensor_stats(
                sensor_id, hours=24, min_value=min_val, max_value=max_val
            )
            if stats and stats.get("count", 0) > 0:
                data["sensor_stats_24h"][display_name] = stats
            elif display_name == "fertilizer_flow":
                data["missing_data"].append(
                    "fertilizer_flow: no 24h records in sensors_data — "
                    "flow sensor may not be logging to MongoDB yet"
                )
        except Exception as e:
            data["missing_data"].append(f"sensor_stats_{display_name}: {e}")

    # ── Plant health — latest two records ─────────────────────────────────────
    try:
        health_history = _mongo_db_handler.get_plant_health_history(7)
        _CUSTOM_PRINT_FUNC(
            f"[AI Advisor] plant_health_results: {len(health_history)} docs found"
        )
        if health_history:
            ts = health_history[0].get("created_at")
            _CUSTOM_PRINT_FUNC(f"[AI Advisor]   latest health: {ts}")
            data["plant_health_latest"] = _clean_health_doc(health_history[0])
        if len(health_history) > 1:
            data["plant_health_yesterday"] = _clean_health_doc(health_history[1])
        if not health_history:
            data["missing_data"].append("plant_health: no records in plant_health_results collection yet")
            _CUSTOM_PRINT_FUNC("[AI Advisor]   WARNING: no plant health records found")
    except Exception as e:
        data["missing_data"].append(f"plant_health: {e}")
        _CUSTOM_PRINT_FUNC(f"[AI Advisor]   ERROR reading plant health: {e}")

    # ── Growth metrics — latest, previous, trend ──────────────────────────────
    try:
        growth_history = _mongo_db_handler.get_growth_history(7)
        good = [g for g in growth_history if g.get("status") == "success"]
        _CUSTOM_PRINT_FUNC(
            f"[AI Advisor] growth_measurements: {len(growth_history)} total, {len(good)} successful"
        )
        if good:
            ts = good[0].get("created_at") or good[0].get("captured_at")
            _CUSTOM_PRINT_FUNC(f"[AI Advisor]   latest growth: {ts}")
            data["growth_latest"] = _clean_growth_doc(good[0])
        if len(good) > 1:
            data["growth_yesterday"] = _clean_growth_doc(good[1])
        if len(good) >= 3:
            data["growth_trend"] = _compute_growth_trend(good)
            _CUSTOM_PRINT_FUNC(f"[AI Advisor]   growth trend: {data['growth_trend'].get('trend')}")
        else:
            _CUSTOM_PRINT_FUNC(
                f"[AI Advisor]   growth trend unavailable — need ≥3 successful measurements, have {len(good)}"
            )
        if not good:
            data["missing_data"].append("growth_metrics: no successful records in growth_measurements collection yet")
            _CUSTOM_PRINT_FUNC("[AI Advisor]   WARNING: no successful growth records found")
    except Exception as e:
        data["missing_data"].append(f"growth_metrics: {e}")
        _CUSTOM_PRINT_FUNC(f"[AI Advisor]   ERROR reading growth metrics: {e}")

    # ── Actuator states ───────────────────────────────────────────────────────
    try:
        with app_loop._sensor_cache_lock:
            cache = dict(app_loop._sensor_cache)
        data["actuators_summary"] = {
            "heater_pct":            _safe_float(cache.get("heater_pct")),
            "light_pct":             _safe_float(cache.get("light_pct")),
            "fan_pct":               _safe_float(cache.get("fan_pct")),
            "water_pump_state":      cache.get("water_pump_state", "unknown"),
            "fertilizer_pump_state": cache.get("fertilizer_pump_state", "unknown"),
        }
    except Exception as e:
        data["missing_data"].append(f"actuators: {e}")

    # ── Pump history summary ──────────────────────────────────────────────────
    try:
        pump_logs = _mongo_db_handler.get_pump_logs(limit=20)
        if pump_logs:
            water_logs = [p for p in pump_logs if p.get('pump') == 'water']
            fert_logs  = [p for p in pump_logs if p.get('pump') == 'fertilizer']

            def _last_ts(logs):
                ts = logs[0].get('timestamp') if logs else None
                return ts.isoformat() if hasattr(ts, 'isoformat') else None

            def _avg_pulse(logs):
                vals = [p.get('pulse_sec', 0) for p in logs if p.get('pulse_sec')]
                return round(sum(vals) / len(vals), 2) if vals else None

            data["pump_history"] = {
                "water_activations_recent":      len(water_logs),
                "fertilizer_activations_recent": len(fert_logs),
                "last_water_pump":               _last_ts(water_logs),
                "last_fertilizer_pump":          _last_ts(fert_logs),
                "avg_water_pulse_sec":           _avg_pulse(water_logs),
                "avg_fert_pulse_sec":            _avg_pulse(fert_logs),
            }
            _CUSTOM_PRINT_FUNC(
                f"[AI Advisor] pump_history: water={len(water_logs)} fert={len(fert_logs)} "
                f"(last 20 events each)"
            )
        else:
            data["missing_data"].append("pump_history: no pump log records found yet")
    except Exception as e:
        data["missing_data"].append(f"pump_history: {e}")
        _CUSTOM_PRINT_FUNC(f"[AI Advisor]   ERROR reading pump logs: {e}")

    # ── Resource usage (cumulative totals from system_state) ──────────────────
    try:
        water_l   = _mongo_db_handler.get_state('total_water_liters')
        energy_wh = _mongo_db_handler.get_state('total_energy_wh')
        fert_l    = _mongo_db_handler.get_state('total_fertilizer_liters')
        if any(v is not None for v in [water_l, energy_wh, fert_l]):
            data["resource_usage"] = {
                "total_water_liters":      round(float(water_l   or 0), 3),
                "total_energy_wh":         round(float(energy_wh or 0), 3),
                "total_fertilizer_liters": round(float(fert_l    or 0), 3),
            }
            _CUSTOM_PRINT_FUNC(
                f"[AI Advisor] resource_usage: water={data['resource_usage']['total_water_liters']}L  "
                f"energy={data['resource_usage']['total_energy_wh']}Wh  "
                f"fert={data['resource_usage']['total_fertilizer_liters']}L"
            )
        else:
            data["missing_data"].append("resource_usage: system_state totals not found")
    except Exception as e:
        data["missing_data"].append(f"resource_usage: {e}")
        _CUSTOM_PRINT_FUNC(f"[AI Advisor]   ERROR reading resource usage: {e}")

    # ── Data age — hours since last health check and growth measurement ────────
    try:
        health_doc = _mongo_db_handler.get_latest_plant_health_result()
        if health_doc:
            age = _data_age_hours(health_doc, 'created_at', 'timestamp')
            if age is not None:
                data["data_age"]["health_check_hours_ago"] = age
                if age > 36:
                    data["missing_data"].append(
                        f"plant_health: latest result is {age:.1f}h old — may not reflect current condition"
                    )
                    _CUSTOM_PRINT_FUNC(f"[AI Advisor]   WARNING: plant health data is {age:.1f}h old")
        else:
            data["data_age"]["health_check_hours_ago"] = None

        growth_doc = _mongo_db_handler.get_latest_growth_measurement()
        if growth_doc and growth_doc.get('status') == 'success':
            age = _data_age_hours(growth_doc, 'captured_at', 'created_at')
            if age is not None:
                data["data_age"]["growth_measurement_hours_ago"] = age
                if age > 72:
                    data["missing_data"].append(
                        f"growth_metrics: latest measurement is {age:.1f}h old — trend may be unreliable"
                    )
                    _CUSTOM_PRINT_FUNC(f"[AI Advisor]   WARNING: growth data is {age:.1f}h old")
        else:
            data["data_age"]["growth_measurement_hours_ago"] = None
    except Exception as e:
        data["missing_data"].append(f"data_age: {e}")
        _CUSTOM_PRINT_FUNC(f"[AI Advisor]   ERROR computing data age: {e}")

    return data


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_prompt(data: dict) -> str:
    optimal_str = json.dumps(LETTUCE_OPTIMAL, indent=2)

    def _fmt(val, decimals=2):
        if val is None:
            return 'N/A'
        try:
            return f"{float(val):.{decimals}f}"
        except (TypeError, ValueError):
            return str(val)

    def _section(title: str, content: str) -> str:
        return f"=== {title} ===\n{content}"

    sections = []
    age_info = data.get("data_age") or {}

    # ── Section 1: Plant Status ───────────────────────────────────────────────
    health      = data.get("plant_health_latest")
    health_prev = data.get("plant_health_yesterday")
    health_age  = age_info.get("health_check_hours_ago")

    if health:
        age_note = f" (captured {health_age:.1f}h ago)" if health_age is not None else " (age unknown)"
        lines = [
            f"Healthy: {health.get('is_healthy')}  |  "
            f"Health Probability: {_fmt(health.get('health_probability'), 1)}%{age_note}",
        ]
        diseases = health.get("diseases") or []
        if diseases:
            lines.append("Diseases detected:")
            for d in diseases:
                lines.append(f"  - {d.get('name', 'unknown')}: {_fmt(d.get('probability'), 1)}%")
        else:
            lines.append("No diseases detected.")
        if health_prev:
            lines.append(
                f"Previous check: Healthy={health_prev.get('is_healthy')}  "
                f"Probability={_fmt(health_prev.get('health_probability'), 1)}%  "
                f"Date={health_prev.get('date', 'N/A')}"
            )
    else:
        lines = ["No plant health data available."]

    sections.append(_section("SECTION 1: PLANT STATUS", "\n".join(lines)))

    # ── Section 2: Growth Status ──────────────────────────────────────────────
    growth       = data.get("growth_latest")
    growth_prev  = data.get("growth_yesterday")
    growth_trend = data.get("growth_trend")
    growth_age   = age_info.get("growth_measurement_hours_ago")

    if growth:
        age_note = f" (measured {growth_age:.1f}h ago)" if growth_age is not None else " (age unknown)"
        lines = [
            f"Area:    {_fmt(growth.get('area_cm2'))} cm²",
            f"Height:  {_fmt(growth.get('height_cm'))} cm",
            f"Width:   {_fmt(growth.get('width_cm'))} cm",
            f"Volume:  {_fmt(growth.get('volume_cm3'))} cm³",
            f"AGR (Absolute Growth Rate): {_fmt(growth.get('agr'))}",
            f"RGR (Relative Growth Rate): {_fmt(growth.get('rgr'))}",
            f"Growth %: {_fmt(growth.get('growth_pct'), 1)}%{age_note}",
        ]
        if growth_prev:
            lines.append(
                f"Previous: Area={_fmt(growth_prev.get('area_cm2'))} cm²  "
                f"Height={_fmt(growth_prev.get('height_cm'))} cm  "
                f"Date={growth_prev.get('date', 'N/A')}"
            )
        if growth_trend:
            lines.append(
                f"Trend: {growth_trend.get('trend', 'unknown')}  |  "
                f"Area delta: {_fmt(growth_trend.get('area_delta_cm2'))} cm²  |  "
                f"Data points: {growth_trend.get('data_points', 0)}"
            )
        else:
            lines.append("Trend: insufficient data (need ≥3 measurements)")
    else:
        lines = ["No growth measurement data available."]

    sections.append(_section("SECTION 2: GROWTH STATUS", "\n".join(lines)))

    # ── Section 3: Current Environment ───────────────────────────────────────
    sensors = data.get("current_sensors") or {}
    if sensors:
        lines = [
            f"Air Temperature:  {_fmt(sensors.get('air_temperature'))} °C",
            f"Air Humidity:     {_fmt(sensors.get('air_humidity'))} %",
            f"Light Intensity:  {_fmt(sensors.get('light_intensity'))} (sensor units — not calibrated lux)",
            f"Soil pH:          {_fmt(sensors.get('soil_ph'))}",
            f"Soil EC:          {_fmt(sensors.get('soil_ec'))} µS/cm",
            f"Soil Humidity:    {_fmt(sensors.get('soil_humidity'))} %",
            f"Soil Temperature: {_fmt(sensors.get('soil_temperature'))} °C",
            f"Water Flow Rate:  {_fmt(sensors.get('water_flow'))} L/min",
            f"Fertilizer Flow:  {_fmt(sensors.get('fertilizer_flow'))} L/min",
        ]
    else:
        lines = ["No live sensor data available."]

    sections.append(_section("SECTION 3: CURRENT ENVIRONMENT (live readings)", "\n".join(lines)))

    # ── Section 4: 24h Trends ─────────────────────────────────────────────────
    stats = data.get("sensor_stats_24h") or {}
    _STAT_LABELS = {
        "air_temperature":  ("Air Temp",    "°C"),
        "air_humidity":     ("Air Humid",   "%"),
        "light_intensity":  ("Light",       ""),
        "soil_ph":          ("Soil pH",     ""),
        "soil_ec":          ("Soil EC",     "µS/cm"),
        "soil_temperature": ("Soil Temp",   "°C"),
        "soil_humidity":    ("Soil Humid",  "%"),
        "water_flow":       ("Water Flow",  "L/min"),
        "fertilizer_flow":  ("Fert. Flow",  "L/min"),
    }
    lines = []
    for key, (label, unit) in _STAT_LABELS.items():
        s = stats.get(key)
        if s and s.get("count", 0) > 0:
            lines.append(
                f"{label:12s}: avg={_fmt(s.get('avg'))} {unit}  "
                f"min={_fmt(s.get('min'))}  max={_fmt(s.get('max'))}  "
                f"n={s.get('count')}"
            )
    if not lines:
        lines = ["No 24h statistics available."]

    sections.append(_section("SECTION 4: 24h TRENDS", "\n".join(lines)))

    # ── Section 5: Current Setpoints ─────────────────────────────────────────
    sp = data.get("current_setpoints") or {}
    if sp:
        lines = [
            f"Temperature:     {_fmt(sp.get('temperature'))} °C",
            f"Humidity:        {_fmt(sp.get('humidity'))} %",
            f"Light:           {_fmt(sp.get('light'))}",
            f"Soil pH:         {_fmt(sp.get('soil_ph'))}",
            f"Soil EC:         {_fmt(sp.get('soil_ec'))} µS/cm",
            f"Soil Temp:       {_fmt(sp.get('soil_temp'))} °C",
            f"Soil Moisture:   {_fmt(sp.get('soil_moisture'))} %",
            f"Soil Hysteresis: {_fmt(sp.get('soil_hysteresis'))} %",
            f"Water Flow:      {_fmt(sp.get('water_flow'))} L/h  [LOCKED — do not change]",
            f"Fertilizer Flow: {_fmt(sp.get('fertilizer_flow'))} L/h  [LOCKED — do not change]",
            f"Operation Mode:  {sp.get('operation_mode', 'N/A')}  [LOCKED — do not change]",
        ]
    else:
        lines = ["No setpoint data available."]

    sections.append(_section("SECTION 5: CURRENT SETPOINTS", "\n".join(lines)))

    # ── Section 6: Actuator State ─────────────────────────────────────────────
    actuators = data.get("actuators_summary") or {}
    if actuators:
        lines = [
            f"Heater:          {_fmt(actuators.get('heater_pct'), 1)}%",
            f"Light Strip:     {_fmt(actuators.get('light_pct'), 1)}%",
            f"Fan:             {_fmt(actuators.get('fan_pct'), 1)}%",
            f"Water Pump:      {actuators.get('water_pump_state', 'N/A')}",
            f"Fertilizer Pump: {actuators.get('fertilizer_pump_state', 'N/A')}",
        ]
    else:
        lines = ["No actuator state data available."]

    sections.append(_section("SECTION 6: ACTUATOR STATE", "\n".join(lines)))

    # ── Section 7: Pump History & Resource Usage ──────────────────────────────
    pumps     = data.get("pump_history")
    resources = data.get("resource_usage")
    lines = []
    if pumps:
        lines += [
            f"Recent water pump activations (last 20 events): {pumps.get('water_activations_recent', 0)}",
            f"Recent fertilizer pump activations (last 20 events): {pumps.get('fertilizer_activations_recent', 0)}",
            f"Last water pump:      {pumps.get('last_water_pump', 'N/A')}",
            f"Last fertilizer pump: {pumps.get('last_fertilizer_pump', 'N/A')}",
            f"Avg water pulse:      {_fmt(pumps.get('avg_water_pulse_sec'))} s",
            f"Avg fertilizer pulse: {_fmt(pumps.get('avg_fert_pulse_sec'))} s",
        ]
    if resources:
        lines += [
            "",
            "Cumulative resource usage (this plant cycle):",
            f"  Water:      {_fmt(resources.get('total_water_liters'), 3)} L",
            f"  Energy:     {_fmt(resources.get('total_energy_wh'), 1)} Wh",
            f"  Fertilizer: {_fmt(resources.get('total_fertilizer_liters'), 3)} L",
        ]
    if not lines:
        lines = ["No pump history or resource usage data available."]

    sections.append(_section("SECTION 7: PUMP HISTORY & RESOURCE USAGE", "\n".join(lines)))

    # ── Section 8: Data Quality Notes ────────────────────────────────────────
    missing = data.get("missing_data") or []
    lines   = [f"Collection timestamp: {data.get('collection_timestamp', 'N/A')}"]
    if age_info:
        lines.append("Data age:")
        for k, v in age_info.items():
            lines.append(f"  {k}: {v}h ago" if v is not None else f"  {k}: unknown")
    if missing:
        lines.append("Missing or stale data:")
        for m in missing:
            lines.append(f"  - {m}")
    else:
        lines.append("All expected data collected successfully.")

    sections.append(_section("SECTION 8: DATA QUALITY NOTES", "\n".join(lines)))

    # ── Assemble full context ─────────────────────────────────────────────────
    context = "\n\n".join(sections)

    limits_summary = (
        "Temperature:     max ±1.0 °C      (hard reject > ±2.0 °C)\n"
        "Humidity:        max ±5 %         (hard reject > ±10 %)\n"
        "Light:           max ±100 units   (hard reject > ±300) — prefer no change if uncertain\n"
        "Soil pH:         max ±0.2         (hard reject > ±0.3) — NEVER ±1.0 or more\n"
        "Soil EC:         max ±100 µS/cm   (hard reject > ±200)\n"
        "Soil Temp:       max ±1.0 °C      (hard reject > ±2.0 °C)\n"
        "Soil Moisture:   max ±10 %        (hard reject > ±15 %)\n"
        "Soil Hysteresis: max ±2 %         (always requires manual review)\n"
        "Water Flow, Fertilizer Flow, Operation Mode: LOCKED — must not change"
    )

    return f"""You are an expert hydroponic lettuce cultivation AI advisor for PlantMind AI.
Your job: analyze the full plant and system data below, diagnose any issues, \
and recommend the best setpoints for optimal lettuce growth.

=== MANDATORY RULES ===
1. Return ONLY valid JSON — no markdown code blocks, no extra text outside the JSON.
2. DO NOT change Water Flow, Fertilizer Flow, or Operation Mode — always keep current values.
3. Prefer SMALL, GRADUAL changes. Never make aggressive recommendations.
4. If data is missing or stale, lower your confidence score accordingly and be more conservative.
5. If there is no clear reason to change a setpoint, keep the current value and explain in no_change_reason.
6. For Light: sensor values may NOT accurately represent real LED intensity. \
A good LED can read only 20–80 in this system. Prefer no change if uncertain.
7. pH changes must be AT MOST ±0.2. NEVER recommend ±1.0 or more.
8. If the plant is healthy with stable or positive growth, prefer keeping current setpoints \
or making only tiny conservative adjustments.
9. Always populate growth_assessment, environment_issues, warnings, no_change_reason, \
and plant_stability_score — never leave them null.
10. plant_stability_score: 1.0 = fully healthy and growing well, 0.0 = critical condition. \
Compute it from all available data. Lower it if health data or growth data is old or missing.

=== OPTIMAL LETTUCE SETPOINT RANGES ===
{optimal_str}

=== MAXIMUM ALLOWED CHANGES PER RECOMMENDATION ===
{limits_summary}

=== SYSTEM DATA ===
{context}

=== REQUIRED JSON RESPONSE FORMAT ===
{{
  "plant_status": "healthy | slightly_stressed | stressed | unhealthy | unknown",
  "problem_detected": true or false,
  "severity": "none | low | medium | high",
  "main_problem": "string — main issue detected, or 'none' if healthy",
  "growth_assessment": "growing_well | stable | stagnating | declining | insufficient_data",
  "environment_issues": [
    {{
      "parameter": "parameter name",
      "current_value": current numeric value,
      "optimal_range": "min–max string",
      "severity": "low | medium | high",
      "description": "brief explanation of why this is an issue"
    }}
  ],
  "warnings": ["list of warning strings that need human attention — empty array if none"],
  "no_change_reason": "if no setpoint changes are recommended, explain why — otherwise empty string",
  "plant_stability_score": 0.0,
  "data_quality": "good | medium | weak",
  "confidence": 0.0 to 1.0,
  "summary": "2–3 sentence summary of plant condition and what you recommend",
  "detailed_explanation": "detailed explanation of diagnosis and why you recommend or do not recommend changes",
  "recommended_setpoints": {{
    "Temperature": number,
    "Humidity": number,
    "Light": number,
    "Soil pH": number,
    "Soil EC": number,
    "Soil Temp": number,
    "Soil Moisture": number,
    "Soil Hysteresis": number,
    "Water Flow": MUST equal current value,
    "Fertilizer Flow": MUST equal current value,
    "Operation Mode": MUST equal current value
  }},
  "changes": [
    {{
      "parameter": "parameter name",
      "current_value": current numeric or string value,
      "recommended_value": new numeric or string value,
      "difference": numeric difference,
      "reason": "detailed reason for this specific change",
      "risk_level": "low | medium | high"
    }}
  ],
  "apply_mode": "manual_review",
  "telegram_message": "New AI setpoint recommendation is ready. Please open the dashboard and approve or reject it."
}}
Only include a parameter in "changes" if you actually recommend changing it from the current value.
If no changes are recommended, "changes" must be an empty array [].
"""


# ── Safe error classifier (never leaks keys/tokens) ──────────────────────────

def _classify_openai_error(e: Exception) -> str:
    """Return a safe, human-readable reason string from an OpenAI exception."""
    msg = str(e).lower()
    # Empty response from thinking model (token budget exhausted on reasoning)
    if 'empty response' in msg and 'token' in msg:
        return (f"OpenAI model '{OPENAI_MODEL}' returned empty response — "
                "token budget was exhausted on internal reasoning. "
                "max_completion_tokens has been increased; try again.")
    # Parameter errors — checked before generic "invalid" catch-alls
    if 'max_tokens' in msg and 'unsupported' in msg:
        return "OpenAI API parameter error — 'max_tokens' not supported by this model (use max_completion_tokens)"
    if 'temperature' in msg and ('unsupported' in msg or 'not supported' in msg):
        return f"OpenAI model '{OPENAI_MODEL}' does not support custom temperature — change OPENAI_MODEL in .env to gpt-4.1"
    if 'unsupported_parameter' in msg or 'unsupported parameter' in msg:
        return "OpenAI API parameter error — a request parameter is not supported by this model"
    # Auth / quota
    if 'authentication' in msg or 'incorrect api key' in msg or '401' in msg:
        return "OpenAI authentication failed — check OPENAI_API_KEY in .env"
    if 'quota' in msg or 'billing' in msg or 'payment' in msg or 'insufficient_quota' in msg:
        return "OpenAI quota or billing issue — check account credits at platform.openai.com"
    if '429' in msg and 'rate' in msg:
        return "OpenAI rate limit hit — too many requests, try again in a minute"
    # Model errors — checked after parameter errors
    if ('model' in msg or 'model_not_found' in msg) and ('not found' in msg or 'does not exist' in msg or 'model_not_found' in msg):
        return f"OpenAI model '{OPENAI_MODEL}' not found — update OPENAI_MODEL in .env"
    # Context / response content
    if 'context_length' in msg or 'context length' in msg or 'too many tokens' in msg:
        return "OpenAI context length exceeded — prompt too long"
    if ('invalid json' in msg or 'json' in msg) and ('decode' in msg or 'parse' in msg or 'invalid' in msg):
        return "OpenAI returned invalid JSON — model response could not be parsed"
    # Network
    if 'timeout' in msg:
        return "OpenAI request timed out — check network connectivity"
    if 'connection' in msg or 'network' in msg or 'unreachable' in msg:
        return "Network/connection error reaching OpenAI — check internet on Pi"
    return f"OpenAI API call failed ({type(e).__name__}) — check backend logs for details"


# ── OpenAI API call ───────────────────────────────────────────────────────────

def _call_openai(prompt: str) -> tuple:
    """
    Send the prompt to OpenAI and return (parsed_json_dict, raw_response_text).
    Raises RuntimeError on API failure or invalid JSON.
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError(
            "openai package is not installed. Run: pip install openai"
        )

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set in .env")

    client = OpenAI(api_key=OPENAI_API_KEY)

    _CUSTOM_PRINT_FUNC(f"[AI Advisor] Calling OpenAI (model={OPENAI_MODEL}) ...")

    # Models in the gpt-5.x / o-series families do not accept a temperature param
    # and are "thinking" models that require a much higher max_completion_tokens
    # budget — they consume reasoning tokens internally before producing visible
    # output, so a low limit (e.g. 2000) leaves zero tokens for the actual JSON.
    MODELS_NO_TEMPERATURE = {'gpt-5.5', 'gpt-5.5-2026-04-23', 'gpt-5.5-pro',
                              'gpt-5.4', 'gpt-5.4-2026-03-05', 'gpt-5.4-pro',
                              'gpt-5.3-chat-latest', 'gpt-5.2', 'gpt-5.1',
                              'gpt-5', 'o1', 'o1-pro', 'o3', 'o3-mini', 'o4-mini'}
    MODELS_THINKING = {'gpt-5.5', 'gpt-5.5-2026-04-23', 'gpt-5.5-pro',
                       'gpt-5.4', 'gpt-5.4-2026-03-05', 'gpt-5.4-pro',
                       'gpt-5.3-chat-latest', 'gpt-5.2', 'gpt-5.1',
                       'gpt-5', 'o1', 'o1-pro', 'o3', 'o3-mini', 'o4-mini'}

    # Thinking models need a large token budget so reasoning + JSON output fit.
    # Standard models need only ~2000 tokens for this prompt.
    max_tokens = 16000 if OPENAI_MODEL in MODELS_THINKING else 2000

    request_params = dict(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert hydroponic lettuce cultivation AI advisor. "
                    "You ONLY output valid JSON. No markdown fences, no extra text."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        max_completion_tokens=max_tokens,
    )
    temperature_included = OPENAI_MODEL not in MODELS_NO_TEMPERATURE
    if temperature_included:
        request_params['temperature'] = 0.2

    # ── Log exact request parameters before calling OpenAI ────────────────────
    _CUSTOM_PRINT_FUNC(
        f"[AI Advisor] OpenAI request params: "
        f"model={request_params['model']}  "
        f"temperature={'0.2' if temperature_included else 'NOT SENT (excluded for this model)'}  "
        f"max_completion_tokens={request_params['max_completion_tokens']}  "
        f"messages={len(request_params['messages'])}"
    )

    try:
        response = client.chat.completions.create(**request_params)
    except Exception as api_err:
        _CUSTOM_PRINT_FUNC(
            f"[AI Advisor] OpenAI RAW ERROR — type={type(api_err).__name__}  "
            f"message={api_err}"
        )
        raise

    finish_reason = response.choices[0].finish_reason
    raw_content   = response.choices[0].message.content
    _CUSTOM_PRINT_FUNC(
        f"[AI Advisor] Response received — "
        f"finish_reason={finish_reason}  "
        f"content_length={len(raw_content) if raw_content else 0}"
    )

    # Empty content with finish_reason='length' means the thinking model consumed
    # all tokens on internal reasoning and had none left for visible output.
    if not raw_content or not raw_content.strip():
        raise RuntimeError(
            f"OpenAI returned empty response (finish_reason={finish_reason}). "
            "Model likely exhausted its token budget on internal reasoning. "
            "This is an empty response error."
        )

    raw_text = raw_content.strip()

    # Strip markdown code fences if model added them despite instructions
    if raw_text.startswith("```"):
        lines    = raw_text.split("\n")
        lines    = [ln for ln in lines if not ln.strip().startswith("```")]
        raw_text = "\n".join(lines).strip()

    try:
        parsed = json.loads(raw_text)
        return parsed, raw_text
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"AI returned invalid JSON: {e}\nRaw (first 500 chars): {raw_text[:500]}"
        )


# ── Safety validation ─────────────────────────────────────────────────────────

def _validate_recommendation(ai_json: dict, current_setpoints: dict) -> tuple:
    """
    Validate AI-recommended setpoints against safety limits.

    Returns:
        status            : 'pending' | 'invalid' | 'needs_manual_review'
        validation_notes  : list of string messages
        cleaned_recommended: dict of final setpoint values (safe to apply)
        validated_changes : list of change dicts (only params actually changed)
    """
    validation_notes = []
    hard_rejected    = False
    needs_review     = False

    recommended = ai_json.get("recommended_setpoints") or {}
    if not recommended:
        return "invalid", ["AI response missing 'recommended_setpoints'"], {}, []

    # Normalise current setpoints to AI key format
    current_ai = {
        "Temperature":     _safe_float(current_setpoints.get("temperature")),
        "Humidity":        _safe_float(current_setpoints.get("humidity")),
        "Light":           _safe_float(current_setpoints.get("light")),
        "Soil pH":         _safe_float(current_setpoints.get("soil_ph")),
        "Soil EC":         _safe_float(current_setpoints.get("soil_ec")),
        "Soil Temp":       _safe_float(current_setpoints.get("soil_temp")),
        "Soil Moisture":   _safe_float(current_setpoints.get("soil_moisture")),
        "Soil Hysteresis": _safe_float(current_setpoints.get("soil_hysteresis")),
        "Water Flow":      _safe_float(current_setpoints.get("water_flow")),
        "Fertilizer Flow": _safe_float(current_setpoints.get("fertilizer_flow")),
        "Operation Mode":  current_setpoints.get("operation_mode", "autonomous"),
    }

    # Start with all current values; then selectively allow changes
    cleaned = dict(current_ai)
    validated_changes = []

    for param, rec_val in recommended.items():
        limits = SAFETY_LIMITS.get(param)
        if limits is None:
            validation_notes.append(f"{param}: unknown parameter — ignored")
            continue

        # ── Locked parameters — always force to current value ─────────────────
        if limits.get("locked"):
            current_val = current_ai.get(param)
            rec_float   = _safe_float(rec_val) if param not in ("Operation Mode",) else None
            if param == "Operation Mode":
                cleaned[param] = current_ai.get(param)
            else:
                if rec_float is not None and current_val is not None and abs(rec_float - current_val) > 0.001:
                    validation_notes.append(
                        f"{param}: AI recommended {rec_val}, but this parameter is LOCKED "
                        f"(reason: {limits['reason']}). Keeping current value: {current_val}."
                    )
                cleaned[param] = current_val
            continue

        current_val = current_ai.get(param)
        if current_val is None:
            validation_notes.append(f"{param}: current value unknown — cannot validate, skipping change")
            continue

        rec_float = _safe_float(rec_val)
        if rec_float is None:
            validation_notes.append(
                f"{param}: AI returned non-numeric value '{rec_val}' — skipping"
            )
            continue

        change     = rec_float - current_val
        abs_change = abs(change)

        if abs_change < 0.0001:
            cleaned[param] = current_val
            continue  # no meaningful change

        reject_above = limits.get("reject_above", float("inf"))
        absolute_max = limits.get("absolute_max", float("inf"))
        max_change   = limits.get("max_change",   float("inf"))
        notes_hint   = limits.get("notes", "")

        # ── Hard reject: exceeds the absolute maximum ─────────────────────────
        if abs_change > reject_above:
            validation_notes.append(
                f"{param}: AI recommended change of {change:+.4g} "
                f"(current={current_val}, recommended={rec_float}). "
                f"This exceeds the hard safety limit of ±{reject_above} and is REJECTED. "
                f"{notes_hint}"
            )
            hard_rejected = True
            cleaned[param] = current_val
            continue

        # ── Clamp to absolute_max if exceeded ─────────────────────────────────
        if abs_change > absolute_max:
            sign    = 1 if change > 0 else -1
            clamped = round(current_val + sign * absolute_max, 4)
            validation_notes.append(
                f"{param}: AI change of {change:+.4g} exceeds absolute max ±{absolute_max}. "
                f"Clamped to {clamped} (±{absolute_max} from {current_val}). "
                f"Requires manual review. {notes_hint}"
            )
            cleaned[param] = clamped
            needs_review   = True
            ai_reason = _find_ai_reason(ai_json, param)
            validated_changes.append({
                "parameter":         param,
                "current_value":     current_val,
                "recommended_value": clamped,
                "difference":        round(clamped - current_val, 4),
                "reason":            f"[Clamped from {rec_float}] {ai_reason}",
                "risk_level":        "medium",
                "clamped":           True,
            })
            continue

        # ── Normal max exceeded: allowed but needs review ─────────────────────
        if abs_change > max_change:
            validation_notes.append(
                f"{param}: change of {change:+.4g} exceeds normal max ±{max_change} "
                f"(absolute max is ±{absolute_max}). Allowed but requires manual review. "
                f"{notes_hint}"
            )
            needs_review = True

        # ── Soil Hysteresis: always manual review ─────────────────────────────
        if param == "Soil Hysteresis":
            needs_review = True
            if f"{param}" not in " ".join(validation_notes):
                validation_notes.append(
                    f"{param}: any change requires manual review."
                )

        cleaned[param] = round(rec_float, 4)
        ai_reason = _find_ai_reason(ai_json, param)
        ai_risk   = _find_ai_risk(ai_json, param)
        validated_changes.append({
            "parameter":         param,
            "current_value":     current_val,
            "recommended_value": cleaned[param],
            "difference":        round(cleaned[param] - current_val, 4),
            "reason":            ai_reason,
            "risk_level":        ai_risk,
        })

    if hard_rejected:
        if not validated_changes:
            return "invalid", validation_notes, cleaned, []
        validation_notes.insert(
            0,
            "WARNING: Some AI recommendations were rejected for exceeding safety limits. "
            "Only the remaining safe changes are shown below."
        )
        needs_review = True

    if needs_review:
        return "needs_manual_review", validation_notes, cleaned, validated_changes

    return "pending", validation_notes, cleaned, validated_changes


def _find_ai_reason(ai_json: dict, param: str) -> str:
    for chg in (ai_json.get("changes") or []):
        if chg.get("parameter") == param:
            return chg.get("reason", "")
    return ""


def _find_ai_risk(ai_json: dict, param: str) -> str:
    for chg in (ai_json.get("changes") or []):
        if chg.get("parameter") == param:
            return chg.get("risk_level", "low")
    return "low"


# ── DB document builder ───────────────────────────────────────────────────────

def _build_doc(
    ai_json:             dict,
    raw_ai_response:     str,
    current_setpoints:   dict,
    context_data:        dict,
    status:              str,
    validation_notes:    list,
    cleaned_recommended: dict,
    validated_changes:   list,
    triggered_by:        str,
) -> dict:
    now    = datetime.datetime.now()
    rec_id = f"ai_rec_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    return {
        "recommendation_id":     rec_id,
        "created_at":            now,
        "triggered_by":          triggered_by,
        "status":                status,
        "openai_model":          OPENAI_MODEL,
        # ── Core diagnosis ────────────────────────────────────────────────────
        "plant_status":          ai_json.get("plant_status", "unknown"),
        "problem_detected":      ai_json.get("problem_detected", False),
        "severity":              ai_json.get("severity", "none"),
        "main_problem":          ai_json.get("main_problem", ""),
        # ── New Layer-2 enrichment fields ─────────────────────────────────────
        "growth_assessment":     ai_json.get("growth_assessment", "insufficient_data"),
        "environment_issues":    ai_json.get("environment_issues") or [],
        "warnings":              ai_json.get("warnings") or [],
        "no_change_reason":      ai_json.get("no_change_reason", ""),
        "plant_stability_score": _safe_float(ai_json.get("plant_stability_score"), 0.0),
        # ── Quality & narrative ───────────────────────────────────────────────
        "data_quality":          ai_json.get("data_quality", "medium"),
        "confidence":            _safe_float(ai_json.get("confidence"), 0.0),
        "summary":               ai_json.get("summary", ""),
        "detailed_explanation":  ai_json.get("detailed_explanation", ""),
        # ── Setpoints & changes ───────────────────────────────────────────────
        "current_setpoints":     current_setpoints,
        "recommended_setpoints": cleaned_recommended,
        "changes":               validated_changes,
        "validation_notes":      validation_notes,
        "rejection_reason":      None,
        "apply_mode":            AI_APPLY_MODE,
        "applied_at":            None,
        "approved_by":           None,
        "raw_ai_response":       raw_ai_response,
        # ── Context provenance ────────────────────────────────────────────────
        "context_summary": {
            "missing_data":               context_data.get("missing_data", []),
            "health_available":           context_data.get("plant_health_latest") is not None,
            "growth_available":           context_data.get("growth_latest") is not None,
            "sensors_available":          context_data.get("current_sensors") is not None,
            "trend_available":            context_data.get("growth_trend") is not None,
            "pump_history_available":     context_data.get("pump_history") is not None,
            "resource_usage_available":   context_data.get("resource_usage") is not None,
            "data_age":                   context_data.get("data_age", {}),
            "collection_timestamp":       context_data.get("collection_timestamp"),
        },
        "telegram_sent": False,
    }


# ── Main run function ─────────────────────────────────────────────────────────

def run_advisor(triggered_by: str = "scheduler") -> dict:
    """
    Full AI Setpoint Advisor pipeline.
    Raises RuntimeError on rate-limit, concurrent run, or unrecoverable API failure.
    """
    if not _run_lock.acquire(blocking=False):
        raise RuntimeError("AI Advisor is already running — please wait.")

    try:
        if not _check_and_increment_rate_limit():
            raise RuntimeError(
                f"AI Advisor daily rate limit reached "
                f"({AI_MAX_CALLS_PER_DAY} calls/day). Try again tomorrow."
            )

        _CUSTOM_PRINT_FUNC(f"[AI Advisor] Run started (triggered_by={triggered_by})")

        # 1. Collect context
        _CUSTOM_PRINT_FUNC("[AI Advisor] Collecting context data from DB + sensor cache ...")
        context_data = _collect_context_data()
        missing = context_data.get("missing_data", [])
        if missing:
            _CUSTOM_PRINT_FUNC(f"[AI Advisor] Missing data: {missing}")

        current_sp = context_data.get("current_setpoints") or {}

        # 2. Build prompt
        prompt = _build_prompt(context_data)

        # 3. Call OpenAI
        try:
            ai_json, raw_response = _call_openai(prompt)
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[AI Advisor] OpenAI call failed: {e}")
            _decrement_rate_limit()
            safe_reason = _classify_openai_error(e)
            # Save a failed record so the attempt is visible in the dashboard
            failed_doc = {
                "recommendation_id": f"ai_rec_failed_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}",
                "created_at":        datetime.datetime.now(),
                "triggered_by":      triggered_by,
                "status":            "invalid",
                "openai_model":      OPENAI_MODEL,
                "rejection_reason":  safe_reason,
                "raw_ai_response":   "",
                "telegram_sent":     False,
                "validation_notes":  [safe_reason],
                "current_setpoints": current_sp,
                "changes":               [],
                "confidence":            0.0,
                "growth_assessment":     "insufficient_data",
                "environment_issues":    [],
                "warnings":              [],
                "no_change_reason":      "",
                "plant_stability_score": 0.0,
                "summary":               f"API call failed — {safe_reason}",
                "detailed_explanation":  safe_reason,
                # Include context_summary so data chips render correctly even on failure
                "context_summary": {
                    "missing_data":             context_data.get("missing_data", []),
                    "health_available":         context_data.get("plant_health_latest") is not None,
                    "growth_available":         context_data.get("growth_latest") is not None,
                    "sensors_available":        context_data.get("current_sensors") is not None,
                    "trend_available":          context_data.get("growth_trend") is not None,
                    "pump_history_available":   context_data.get("pump_history") is not None,
                    "resource_usage_available": context_data.get("resource_usage") is not None,
                    "data_age":                 context_data.get("data_age", {}),
                    "collection_timestamp":     context_data.get("collection_timestamp"),
                },
            }
            _mongo_db_handler.insert_ai_recommendation(failed_doc)
            raise

        # 4. Validate safety
        _CUSTOM_PRINT_FUNC("[AI Advisor] Validating AI recommendations against safety limits ...")
        status, notes, cleaned, changes = _validate_recommendation(ai_json, current_sp)
        _CUSTOM_PRINT_FUNC(
            f"[AI Advisor] Validation complete: status={status}, "
            f"{len(changes)} change(s), {len(notes)} note(s)"
        )

        # 5. Build + save recommendation doc
        doc = _build_doc(
            ai_json, raw_response, current_sp, context_data,
            status, notes, cleaned, changes, triggered_by,
        )
        _CUSTOM_PRINT_FUNC(
            f"[AI Advisor] Saving recommendation "
            f"(id={doc['recommendation_id']}, status={status}) ..."
        )
        _mongo_db_handler.insert_ai_recommendation(doc)

        # 6a. Trigger Layer 3 review automatically (runs in background, never blocks Layer 2)
        _trigger_layer3_review(doc['recommendation_id'])

        # 6b. Telegram notification
        _send_telegram_notification(doc)

        doc_copy = {k: v for k, v in doc.items() if k != "_id"}
        _CUSTOM_PRINT_FUNC(f"[AI Advisor] Run complete — id={doc['recommendation_id']}")
        return doc_copy

    finally:
        _run_lock.release()


def _trigger_layer3_review(recommendation_id: str) -> None:
    """
    Fire-and-forget: trigger a Layer 3 budget review in a background daemon thread.
    Layer 2 never waits for or depends on Layer 3's result.
    If Layer 3 is not yet initialized or fails for any reason, Layer 2 is unaffected.
    """
    def _run():
        try:
            import layer3_budget_manager
            if layer3_budget_manager._mongo_db is None:
                _CUSTOM_PRINT_FUNC(
                    "[AI Advisor] Layer 3 not initialized — auto-trigger skipped. "
                    "Call layer3_budget_manager.init() at app startup."
                )
                return
            _CUSTOM_PRINT_FUNC(
                f"[AI Advisor] Layer 3 auto-triggered for {recommendation_id}"
            )
            layer3_budget_manager.run(layer2_recommendation_id=recommendation_id)
        except Exception as e:
            _CUSTOM_PRINT_FUNC(
                f"[AI Advisor] Layer 3 auto-trigger failed (non-critical, Layer 2 unaffected): {e}"
            )

    threading.Thread(target=_run, daemon=True, name='Layer3-auto').start()


def _send_telegram_notification(doc: dict):
    try:
        from telegram_alerts import send_telegram_alert
        status        = doc.get("status", "pending")
        n_changes     = len(doc.get("changes") or [])
        plant_status  = doc.get("plant_status", "unknown")
        severity      = doc.get("severity", "none")
        quality       = doc.get("data_quality", "unknown")
        confidence       = doc.get("confidence", 0.0)
        stability_score  = doc.get("plant_stability_score", 0.0)
        growth_assess    = doc.get("growth_assessment", "unknown")
        n_warnings       = len(doc.get("warnings") or [])
        summary          = doc.get("summary", "")[:200]

        if status == "invalid":
            sent = send_telegram_alert(
                title     = "AI Advisor — Recommendation Failed",
                message   = "The AI returned an invalid or unsafe recommendation. Check the dashboard.",
                severity  = "WARNING",
                component = "AI Setpoint Advisor",
                data={"Reason": doc.get("rejection_reason") or "See validation notes"},
            )
        else:
            sent = send_telegram_alert(
                title     = "New AI Setpoint Recommendation Ready",
                message   = "New AI setpoint recommendation is ready. Please open the dashboard and approve or reject it.",
                severity  = "INFO",
                component = "AI Setpoint Advisor",
                data={
                    "Plant Status":     plant_status,
                    "Growth":           growth_assess,
                    "Stability Score":  f"{stability_score:.2f}",
                    "Severity":         severity,
                    "Confidence":       f"{confidence:.0%}",
                    "Changes":          str(n_changes),
                    "Warnings":         str(n_warnings),
                    "Data Quality":     quality,
                    "Rec Status":       status,
                    "Summary":          summary if summary else "N/A",
                },
            )
        if sent:
            try:
                _mongo_db_handler.update_ai_recommendation(
                    doc["recommendation_id"], {"telegram_sent": True}
                )
            except Exception:
                pass
    except Exception as e:
        _CUSTOM_PRINT_FUNC(f"[AI Advisor] Telegram notification error: {e}")


# ── Apply recommendation (called after user Confirm) ─────────────────────────

def apply_recommendation(rec_id: str) -> tuple:
    """
    Apply an approved recommendation to the live setpoints.
    Re-validates all safety limits before touching any setpoint.

    Returns:
        success        : bool
        message        : str
        applied_changes: list of {parameter, new_value}
    """
    doc = _mongo_db_handler.get_ai_recommendation_by_id(rec_id)
    if not doc:
        return False, f"Recommendation '{rec_id}' not found.", []

    status = doc.get("status")
    if status == "applied":
        return False, "This recommendation has already been applied.", []
    if status == "rejected":
        return False, "Cannot apply a rejected recommendation.", []
    if status == "invalid":
        return False, "Cannot apply an invalid recommendation.", []

    # Re-validate against current (possibly changed) setpoints
    current_sp = _setpoints.get_all_setpoints()
    recommended = doc.get("recommended_setpoints") or {}

    # Reconstruct a minimal ai_json structure for the validator
    ai_json_minimal = {
        "recommended_setpoints": recommended,
        "changes": doc.get("changes") or [],
    }
    re_status, re_notes, re_cleaned, re_changes = \
        _validate_recommendation(ai_json_minimal, current_sp)

    if re_status == "invalid" and not re_changes:
        _mongo_db_handler.update_ai_recommendation(rec_id, {
            "status":           "invalid",
            "rejection_reason": "Re-validation on apply failed: " + "; ".join(re_notes),
        })
        return False, "Re-validation failed: " + "; ".join(re_notes), []

    # Apply changes via the setpoints object
    applied = []
    errors  = []

    for change in re_changes:
        param       = change.get("parameter")
        new_val     = change.get("recommended_value")
        setter_name = SETPOINT_KEY_TO_SETTER.get(param)
        if not setter_name:
            _CUSTOM_PRINT_FUNC(
                f"[AI Advisor] No setter found for '{param}' — skipping"
            )
            continue
        try:
            old_val = change.get("current_value")
            getattr(_setpoints, setter_name)(float(new_val))
            applied.append({
                "parameter": param,
                "old_value": old_val,
                "new_value": new_val,
                "unit":      PARAM_UNITS.get(param, ""),
            })
            _CUSTOM_PRINT_FUNC(f"[AI Advisor] Applied: {param} → {new_val}")
        except Exception as e:
            errors.append(f"{param}: {e}")
            _CUSTOM_PRINT_FUNC(f"[AI Advisor] Failed to apply {param}: {e}")

    if errors and not applied:
        _mongo_db_handler.update_ai_recommendation(rec_id, {
            "status":           "invalid",
            "rejection_reason": "Apply failed: " + "; ".join(errors),
        })
        return False, "Apply failed: " + "; ".join(errors), []

    _mongo_db_handler.update_ai_recommendation(rec_id, {
        "status":            "applied",
        "applied_at":        datetime.datetime.now(),
        "approved_by":       "user",
        "validation_notes":  (doc.get("validation_notes") or []) + re_notes,
    })

    _CUSTOM_PRINT_FUNC(
        f"[AI Advisor] Recommendation {rec_id} applied — "
        f"{len(applied)} setpoint(s) updated."
    )
    return True, f"Successfully applied {len(applied)} setpoint change(s).", applied


# ── Daily scheduled task ──────────────────────────────────────────────────────

def daily_advisor_task(hour: int = 15, minute: int = 30):
    """
    Thread target — runs forever, fires the AI advisor once per day at the given time.
    Errors are caught and logged; the thread never crashes.
    """
    _CUSTOM_PRINT_FUNC(
        f"[AI Advisor] Scheduler started — will run daily at {hour:02d}:{minute:02d}:00"
    )
    while True:
        now    = datetime.datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if now >= target:
            target += datetime.timedelta(days=1)

        sleep_secs = (target - now).total_seconds()
        _CUSTOM_PRINT_FUNC(
            f"[AI Advisor] Next scheduled run at "
            f"{target.strftime('%Y-%m-%d %H:%M')} "
            f"(in {sleep_secs / 3600:.1f} h)"
        )
        time.sleep(sleep_secs)

        try:
            run_advisor(triggered_by="scheduler")
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[AI Advisor] Scheduled run failed: {e}")
