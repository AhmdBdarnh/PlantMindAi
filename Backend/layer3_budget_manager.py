"""
layer3_budget_manager.py — Layer 3 Resource / Budget Manager for PlantMind AI.

Layer 3 reviews Layer 2 recommendations and checks them against three gates:
  1. Sensor Safety Gate  — live sensor values vs. hard-coded safety floors
  2. Plant Health Gate   — plant_stability_score and growth_assessment from Layer 2
  3. Budget Gate         — today's costs (Step 1 daily baseline) vs. budget_config

Final decisions:
  APPROVE    — Safe and affordable.  Apply Layer 2 as-is after user approval.
  MODIFY     — Safe but expensive.   Apply modified version after user approval.
  BLOCK      — Unsafe.               Do NOT apply.  Approve button disabled in frontend.
  ALERT_ONLY — No changes.           Only warn the user.

Layer 3 NEVER fires actuators directly.
Layer 3 NEVER changes pump power or pulse durations.
Layer 3 NEVER stops live sensor readings.
All changes require explicit user approval via the frontend.

Approved changes are applied in a later step (Step 5+) via GH_Setpoints setters.
"""

import datetime
import threading
import uuid

from utils.utils import _CUSTOM_PRINT_FUNC

try:
    from config import (
        WATER_PRICE_PER_LITER_NIS,
        ELECTRICITY_PRICE_PER_KWH_NIS,
        FERTILIZER_PRICE_PER_5_LITERS_NIS,
    )
except ImportError:
    # Safe fallback values if config.py is unavailable (e.g. in isolated tests)
    WATER_PRICE_PER_LITER_NIS         = 0.00851
    ELECTRICITY_PRICE_PER_KWH_NIS     = 0.6432
    FERTILIZER_PRICE_PER_5_LITERS_NIS = 1.0

# ── Module-level singletons ───────────────────────────────────────────────────

_mongo_db  = None   # MongoDBHandler instance
_setpoints = None   # GH_Setpoints instance
_run_lock  = threading.Lock()


def init(mongo_db_handler_obj, setpoints_obj):
    """
    Initialize Layer 3 with the shared MongoDBHandler and GH_Setpoints objects.
    Must be called once at startup before any other function in this module.
    """
    global _mongo_db, _setpoints
    _mongo_db  = mongo_db_handler_obj
    _setpoints = setpoints_obj
    _CUSTOM_PRINT_FUNC("[Layer3] Module initialized.")


# ── Decision type constants ───────────────────────────────────────────────────

DECISION_APPROVE    = "APPROVE"
DECISION_MODIFY     = "MODIFY"
DECISION_BLOCK      = "BLOCK"
DECISION_ALERT_ONLY = "ALERT_ONLY"

# ── Gate status constants ─────────────────────────────────────────────────────

GATE_PASS     = "pass"
GATE_WARN     = "warn"
GATE_FAIL     = "fail"
GATE_MARGINAL = "marginal"

# Budget sub-statuses
BUDGET_OK          = "ok"
BUDGET_WARNING     = "warning"
BUDGET_OVER_BUDGET = "over_budget"

# ── Decision document status constants ───────────────────────────────────────

STATUS_PENDING    = "pending_approval"   # APPROVE or MODIFY — user can act
STATUS_APPROVED   = "approved"           # set later when user confirms
STATUS_REJECTED   = "rejected"           # set later when user rejects
STATUS_CANCELLED  = "cancelled"          # replaced by a newer cycle
STATUS_BLOCKED    = "blocked"            # BLOCK — approve button disabled
STATUS_ALERT_ONLY = "alert_only"         # ALERT_ONLY — informational only

# ── Hard-coded sensor safety floors ──────────────────────────────────────────
# Python constants — NOT stored in DB.
# Budget logic can NEVER override these.  They mirror Layer 1 thresholds.
#
# Reference (control_loops.py):
#   MOISTURE_MIN_PLAUSIBLE = 5.0    (sensor-error floor, not safety floor)
#   EC_DANGER              = 2000.0 (root burn — absolute)
#   PH_CRITICAL_LOW        = 4.8    (critical alert)
#   PH_LOW_WARN            = 5.2    (warning alert)
#   PH_HIGH_WARN           = 7.5    (warning alert)
#
# Layer 3 uses slightly wider margins so it catches problems before Layer 1 alerts fire.

SAFETY_FLOOR_SOIL_MOISTURE_MIN = 20.0    # % — below this → BLOCK (dangerously dry)
SAFETY_FLOOR_EC_MAX            = 2500.0  # µS/cm — above this → BLOCK (root burn margin)
SAFETY_FLOOR_PH_MIN            = 4.5    # — below this → BLOCK (below Layer 1 critical)
SAFETY_FLOOR_PH_MAX            = 8.0    # — above this → BLOCK
SAFETY_FLOOR_AIR_TEMP_MAX      = 35.0   # °C — above this → BLOCK

# ── Plant Health Gate thresholds ──────────────────────────────────────────────

HEALTH_SCORE_STABLE_MIN   = 0.70  # stability_score >= 0.7 → PASS (budget gate runs)
HEALTH_SCORE_MARGINAL_MIN = 0.40  # stability_score >= 0.4 → MARGINAL (no MODIFY)
#                                   stability_score <  0.4 → FAIL → BLOCK

LAYER2_MAX_AGE_HOURS = 48   # Layer 2 data older than this is too stale to act on

# ── Modification safety floors ────────────────────────────────────────────────
# Layer 3 never proposes values outside these bounds.

MOISTURE_SETPOINT_FLOOR = 35.0          # % — minimum allowed soil moisture target
LED_POWER_MIN_PCT       = 40            # % — never propose LED below 40% of current setpoint
FAN_DAY_DUTY_MIN        = int(4095 * 0.60)   # 60% of max
FAN_NIGHT_DUTY_MIN      = int(4095 * 0.15)   # 15% of max


# ── Internal helpers ──────────────────────────────────────────────────────────

def _doc_age_hours(doc: dict) -> float | None:
    """Return age of a document in hours based on created_at or timestamp field."""
    for field in ('created_at', 'timestamp'):
        ts = doc.get(field)
        if ts is not None:
            try:
                if hasattr(ts, 'timestamp'):   # datetime object
                    delta = (datetime.datetime.now() - ts).total_seconds()
                    return round(delta / 3600, 1)
            except Exception:
                pass
    return None


def _get_sensor_snapshot() -> dict:
    """
    Return live sensor values as a normalised dict.

    Strategy:
      1. Try app_loop._sensor_cache — always fresh (updated every 5 s) when app is running.
         Importing app_loop has no side effects; no threads start on import.
      2. Fallback: query MongoDB sensors_data for the latest reading of each sensor.
         Used when Layer 3 is called from a test script or before the sensor loop starts.

    Returns a dict with keys:
      soil_moisture, soil_ec, soil_ph, air_temperature, air_humidity, soil_temperature
      source: 'sensor_cache' | 'mongodb' | 'unavailable'
    """
    # ── Try app_loop sensor cache ──────────────────────────────────────────
    try:
        import app_loop
        with app_loop._sensor_cache_lock:
            cache = dict(app_loop._sensor_cache)
        if cache and cache.get('soil_humidity') is not None:
            return {
                'soil_moisture':    cache.get('soil_humidity'),
                'soil_ec':          cache.get('soil_ec'),
                'soil_ph':          cache.get('soil_ph'),
                'air_temperature':  cache.get('air_temperature'),
                'air_humidity':     cache.get('air_humidity'),
                'soil_temperature': cache.get('soil_temperature'),
                'source':           'sensor_cache',
            }
    except Exception as e:
        _CUSTOM_PRINT_FUNC(f"[Layer3] sensor_cache unavailable ({e}) — falling back to MongoDB")

    # ── Fallback: MongoDB latest readings ──────────────────────────────────
    if _mongo_db is None:
        return {'source': 'unavailable'}

    # Sensor IDs match what app.py registers via create_collection()
    # (confirmed from ai_setpoint_advisor.py get_sensor_stats calls)
    sensor_id_map = {
        'air_temperature':  'dht22.temperature',
        'air_humidity':     'dht22.humidity',
        'soil_ph':          'soil_ph',
        'soil_ec':          'soil_ec',
        'soil_moisture':    'soil_humidity',
        'soil_temperature': 'soil_temp',
    }
    snapshot = {'source': 'mongodb'}
    for field, sid in sensor_id_map.items():
        try:
            doc = _mongo_db.get_latest_doc_where('sensors_data', {'sensor_id': sid})
            if doc:
                snapshot[field] = doc.get('sensor_value')
        except Exception:
            pass
    return snapshot


def _get_latest_layer2_doc() -> dict | None:
    """Return the latest Layer 2 recommendation document from MongoDB, or None."""
    if _mongo_db is None:
        return None
    try:
        return _mongo_db.get_latest_ai_recommendation()
    except Exception as e:
        _CUSTOM_PRINT_FUNC(f"[Layer3] Error fetching Layer 2 doc: {e}")
        return None


# ── Gate 1: Sensor Safety Gate ────────────────────────────────────────────────

def _run_sensor_safety_gate(sensor_snapshot: dict) -> dict:
    """
    Gate 1 — Sensor Safety Gate.

    Checks live sensor values against hard-coded SAFETY_FLOOR_* constants.
    This gate always runs FIRST. Budget logic never runs if this gate fails.

    Thresholds are conservative extensions of the Layer 1 alert values:
      soil_moisture < 20%        → FAIL  (dangerously dry, pump emergency imminent)
      soil_ec       > 2500 µS/cm → FAIL  (above EC_DANGER=2000 in Layer 1)
      soil_ph       < 4.5        → FAIL  (below PH_CRITICAL_LOW=4.8 in Layer 1)
      soil_ph       > 8.0        → FAIL
      air_temp      > 35°C       → FAIL  (heat stress threshold)
      soil_moisture or soil_ec missing → FAIL (cannot make safe decisions without them)

    Air humidity and soil temperature are checked but their absence is not a hard block.

    Returns:
      {"status": "pass"|"fail", "reason": str, "failed_sensors": list}
    """
    # No data at all
    if not sensor_snapshot or sensor_snapshot.get('source') == 'unavailable':
        return {
            "status":         GATE_FAIL,
            "reason":         "No sensor data available — cannot verify plant safety.",
            "failed_sensors": [{"sensor": "all", "value": None, "issue": "no data source"}],
        }

    source  = sensor_snapshot.get('source', 'unknown')
    failed  = []

    def _check(field, label, low=None, high=None, critical=False):
        val = sensor_snapshot.get(field)
        if val is None:
            if critical:
                failed.append({"sensor": label, "value": None, "issue": "missing — required for safety check"})
            return
        try:
            v = float(val)
        except (TypeError, ValueError):
            failed.append({"sensor": label, "value": val, "issue": "not a numeric value"})
            return
        if low  is not None and v < low:
            failed.append({"sensor": label, "value": round(v, 2),
                           "issue": f"{v:.2f} below safety floor {low}"})
        if high is not None and v > high:
            failed.append({"sensor": label, "value": round(v, 2),
                           "issue": f"{v:.2f} above safety ceiling {high}"})

    _check('soil_moisture',   "Soil Moisture",   low=SAFETY_FLOOR_SOIL_MOISTURE_MIN,
           critical=True)
    _check('soil_ec',         "Soil EC",          high=SAFETY_FLOOR_EC_MAX,
           critical=True)
    _check('soil_ph',         "Soil pH",          low=SAFETY_FLOOR_PH_MIN,
           high=SAFETY_FLOOR_PH_MAX)
    _check('air_temperature', "Air Temperature",  high=SAFETY_FLOOR_AIR_TEMP_MAX)
    # air_humidity and soil_temperature are informational — not a hard block if missing

    if failed:
        reasons = "; ".join(f"{f['sensor']}: {f['issue']}" for f in failed)
        return {
            "status":         GATE_FAIL,
            "reason":         f"Sensor safety check failed — {reasons}",
            "failed_sensors": failed,
        }

    return {
        "status":         GATE_PASS,
        "reason":         f"All sensors within safe ranges (source={source})",
        "failed_sensors": [],
    }


# ── Gate 2: Plant Health Gate ─────────────────────────────────────────────────

def _run_plant_health_gate(layer2_doc: dict | None) -> dict:
    """
    Gate 2 — Plant Health Gate.

    Reads plant_stability_score, growth_assessment, and data age from the
    latest Layer 2 recommendation document.

    Scoring rules:
      No Layer 2 doc                            → FAIL
      Data age > LAYER2_MAX_AGE_HOURS (48h)     → FAIL (too stale)
      plant_stability_score < 0.40              → FAIL (poor condition)
      plant_stability_score in [0.40, 0.70)     → MARGINAL (no MODIFY allowed)
      plant_stability_score >= 0.70             → PASS
      growth_assessment == 'declining'          → demote one level:
                                                   PASS → MARGINAL
                                                   MARGINAL → FAIL
      growth_assessment == 'stagnating'         → demote only if already MARGINAL → FAIL

    Returns:
      {"status": "pass"|"marginal"|"fail", "reason": str,
       "stability_score": float|None, "growth_trend": str|None, "data_age_hours": float|None}
    """
    if layer2_doc is None:
        return {
            "status":          GATE_FAIL,
            "reason":          "No Layer 2 recommendation found — cannot assess plant health.",
            "stability_score": None,
            "growth_trend":    None,
            "data_age_hours":  None,
        }

    age_h  = _doc_age_hours(layer2_doc)
    growth = layer2_doc.get('growth_assessment', 'insufficient_data')
    score  = layer2_doc.get('plant_stability_score')

    # Stale data check
    if age_h is not None and age_h > LAYER2_MAX_AGE_HOURS:
        return {
            "status":          GATE_FAIL,
            "reason":          (f"Layer 2 data is {age_h:.1f}h old (limit: {LAYER2_MAX_AGE_HOURS}h). "
                                "Run AI Advisor again to get fresh plant assessment."),
            "stability_score": float(score) if score is not None else None,
            "growth_trend":    growth,
            "data_age_hours":  age_h,
        }

    # Score-based status
    if score is None:
        # No score — conservative: treat as marginal
        base_status = GATE_MARGINAL
        base_reason = "plant_stability_score not present — treating as marginal (conservative)"
    else:
        s = float(score)
        if s < HEALTH_SCORE_MARGINAL_MIN:
            base_status = GATE_FAIL
            base_reason = f"plant_stability_score={s:.2f} — poor condition (threshold: {HEALTH_SCORE_MARGINAL_MIN})"
        elif s < HEALTH_SCORE_STABLE_MIN:
            base_status = GATE_MARGINAL
            base_reason = f"plant_stability_score={s:.2f} — marginal (stable threshold: {HEALTH_SCORE_STABLE_MIN})"
        else:
            base_status = GATE_PASS
            base_reason = f"plant_stability_score={s:.2f} — plant is stable"

    # Growth trend modifier
    demote_reason = None
    final_status  = base_status

    if growth == 'declining':
        if base_status == GATE_PASS:
            final_status = GATE_MARGINAL
            demote_reason = "declining growth trend — demoted from PASS to MARGINAL"
        elif base_status == GATE_MARGINAL:
            final_status = GATE_FAIL
            demote_reason = "declining growth trend while health already marginal — demoted to FAIL"
    elif growth == 'stagnating' and base_status == GATE_MARGINAL:
        final_status = GATE_FAIL
        demote_reason = "stagnating growth trend while health is already marginal — demoted to FAIL"

    reason_parts = [base_reason, f"growth_assessment={growth}"]
    if demote_reason:
        reason_parts.append(demote_reason)
    if age_h is not None:
        reason_parts.append(f"data age={age_h:.1f}h")

    return {
        "status":          final_status,
        "reason":          " | ".join(reason_parts),
        "stability_score": float(score) if score is not None else None,
        "growth_trend":    growth,
        "data_age_hours":  age_h,
    }


# ── Gate 3: Budget Gate ───────────────────────────────────────────────────────

def _run_budget_gate(today_costs: dict, budget_config: dict) -> dict:
    """
    Gate 3 — Budget Gate.

    Compares today's costs (from get_today_costs() daily baseline) against
    the configured daily budget limits from budget_config.

    Budget states:
      usage_pct < warning_threshold_pct%  → BUDGET_OK
      warning_threshold_pct% <= usage_pct <= 100%  → BUDGET_WARNING
      usage_pct > 100%                    → BUDGET_OVER_BUDGET

    Main cost driver: whichever resource (water / electricity / fertilizer)
    has the highest daily cost in NIS.

    Returns:
      {"status": "ok"|"warning"|"over_budget",
       "reason": str, "usage_pct": float,
       "main_cost_driver": str|None,
       "today_costs": dict, "daily_budget": float}
    """
    daily_budget = float(budget_config.get('daily_budget', 10.0))
    warn_pct     = float(budget_config.get('warning_threshold_pct', 80))

    total_cost = float(today_costs.get('total_cost_nis',        0.0))
    water_cost = float(today_costs.get('water_cost_nis',        0.0))
    elec_cost  = float(today_costs.get('electricity_cost_nis',  0.0))
    fert_cost  = float(today_costs.get('fertilizer_cost_nis',   0.0))

    # Guard: unconfigured budget
    if daily_budget <= 0:
        return {
            "status":           BUDGET_OK,
            "reason":           "Daily budget not configured (value <= 0) — budget gate skipped.",
            "usage_pct":        0.0,
            "main_cost_driver": None,
            "today_costs":      today_costs,
            "daily_budget":     daily_budget,
        }

    usage_pct = round((total_cost / daily_budget) * 100.0, 1)

    # Identify main cost driver (highest absolute cost today)
    costs = {'electricity': elec_cost, 'water': water_cost, 'fertilizer': fert_cost}
    main_driver = max(costs, key=costs.get) if any(v > 0 for v in costs.values()) else None

    if usage_pct > 100.0:
        status = BUDGET_OVER_BUDGET
        reason = (f"OVER BUDGET: {usage_pct:.1f}% of daily budget used "
                  f"({total_cost:.4f} ₪ / {daily_budget:.2f} ₪). "
                  f"Main driver: {main_driver}.")
    elif usage_pct >= warn_pct:
        status = BUDGET_WARNING
        reason = (f"Budget WARNING: {usage_pct:.1f}% used "
                  f"({total_cost:.4f} ₪ / {daily_budget:.2f} ₪). "
                  f"Main driver: {main_driver}.")
    else:
        status = BUDGET_OK
        reason = (f"Budget OK: {usage_pct:.1f}% used "
                  f"({total_cost:.4f} ₪ / {daily_budget:.2f} ₪).")

    return {
        "status":           status,
        "reason":           reason,
        "usage_pct":        usage_pct,
        "main_cost_driver": main_driver,
        "today_costs":      today_costs,
        "daily_budget":     daily_budget,
    }


# ── Proposed modifications builder ────────────────────────────────────────────

def _build_proposed_modifications(
    budget_gate:     dict,
    sensor_snapshot: dict,
    layer2_doc:      dict | None,
) -> tuple:
    """
    Build a list of proposed_modifications and a runtime_constraints dict
    based on budget gate result, current sensor values, and active setpoints.

    Rules:
      - Never change pump power or pulse durations.
      - Never propose soil moisture target below MOISTURE_SETPOINT_FLOOR (35%).
      - Never propose LED below LED_POWER_MIN_PCT (40%) of current setpoint.
      - Never fire actuators.
      - Never stop sensor readings.
      - Scale aggressiveness: WARNING → 15% reduction, OVER_BUDGET → 25%.

    Returns:
      (modifications_list, runtime_constraints_dict)
    """
    modifications = []
    constraints   = {}

    budget_status = budget_gate.get('status', BUDGET_OK)
    main_driver   = budget_gate.get('main_cost_driver')
    usage_pct     = budget_gate.get('usage_pct', 0.0)

    # Scale: WARNING = conservative, OVER_BUDGET = stronger
    reduction = 0.25 if budget_status == BUDGET_OVER_BUDGET else 0.15

    # ── LED power reduction (electricity driver) ───────────────────────────
    if main_driver in ('electricity', None) or budget_status == BUDGET_OVER_BUDGET:
        current_light = None
        if _setpoints is not None:
            try:
                current_light = _setpoints.get_light_setpoint()
            except Exception:
                pass
        if current_light is not None and current_light > 0:
            proposed_light = round(max(
                current_light * (LED_POWER_MIN_PCT / 100.0),
                current_light * (1.0 - reduction),
            ), 1)
            if proposed_light < current_light:
                modifications.append({
                    "type":           "led_power_reduction",
                    "parameter":      "light_setpoint",
                    "current_value":  current_light,
                    "proposed_value": proposed_light,
                    "unit":           "sensor units",
                    "reason":         (f"Electricity is main cost driver at {usage_pct:.1f}% of daily budget. "
                                       f"Reducing LED setpoint by {int(reduction * 100)}% for energy saving."),
                    "savings_impact": "medium",
                })
                constraints['led_power_cap'] = round((proposed_light / current_light) * 100.0, 1)

    # ── Night fan duty reduction (electricity driver) ──────────────────────
    if main_driver in ('electricity', None) or budget_status == BUDGET_OVER_BUDGET:
        try:
            import control_loops
            current_night_duty = control_loops.FAN_NIGHT_DUTY
        except Exception:
            current_night_duty = 1024   # fallback: 25% of 4095 (default value)

        proposed_night_duty = max(FAN_NIGHT_DUTY_MIN, int(current_night_duty * (1.0 - reduction)))
        if proposed_night_duty < current_night_duty:
            current_pct  = round((current_night_duty  / 4095) * 100, 1)
            proposed_pct = round((proposed_night_duty / 4095) * 100, 1)
            modifications.append({
                "type":           "fan_night_reduction",
                "parameter":      "fan_night_duty",
                "current_value":  current_night_duty,
                "proposed_value": proposed_night_duty,
                "unit":           "PWM duty (0–4095)",
                "reason":         (f"Night fan reduction is safe and conserves electricity. "
                                   f"Proposed: {current_pct:.0f}% → {proposed_pct:.0f}%. "
                                   f"Budget at {usage_pct:.1f}%."),
                "savings_impact": "low",
            })
            constraints['fan_night_duty'] = proposed_night_duty

    # ── Soil moisture target reduction (water driver) ──────────────────────
    if main_driver == 'water' or budget_status == BUDGET_OVER_BUDGET:
        current_moisture = None
        if _setpoints is not None:
            try:
                current_moisture = _setpoints.get_soil_humidity_setpoint()
            except Exception:
                pass
        # Only reduce if well above the floor (at least 5% buffer)
        if current_moisture is not None and current_moisture > MOISTURE_SETPOINT_FLOOR + 5.0:
            reduce_by = 5.0 if budget_status == BUDGET_OVER_BUDGET else 3.0
            proposed_moisture = max(MOISTURE_SETPOINT_FLOOR, round(current_moisture - reduce_by, 1))
            if proposed_moisture < current_moisture:
                modifications.append({
                    "type":           "moisture_target_reduction",
                    "parameter":      "soil_moisture_setpoint",
                    "current_value":  current_moisture,
                    "proposed_value": proposed_moisture,
                    "unit":           "%",
                    "reason":         (f"Water is main cost driver at {usage_pct:.1f}% of daily budget. "
                                       f"Lowering moisture target by {reduce_by:.0f}% reduces irrigation frequency. "
                                       f"Safety floor: {MOISTURE_SETPOINT_FLOOR}%."),
                    "savings_impact": "medium",
                })
                constraints['moisture_target'] = proposed_moisture

    # ── Fertilizer delay (fertilizer driver, only if EC is already sufficient) ──
    if main_driver == 'fertilizer':
        soil_ec = sensor_snapshot.get('soil_ec')
        if soil_ec is not None:
            try:
                ec_val = float(soil_ec)
                # EC >= 700 means the plant has adequate nutrition — safe to delay
                if ec_val >= 700:
                    modifications.append({
                        "type":           "fertilizer_delay",
                        "parameter":      "fertilizer_pump_action",
                        "current_value":  "active",
                        "proposed_value": "delayed_non_critical",
                        "unit":           None,
                        "reason":         (f"Fertilizer is main cost driver. Current EC={ec_val:.0f} µS/cm "
                                           f"is sufficient — delay non-critical fertilization until EC drops below 700."),
                        "savings_impact": "low",
                    })
                    constraints['fertilizer_delay'] = True
            except (TypeError, ValueError):
                pass

    return modifications, constraints


# ── Decision document assembler ───────────────────────────────────────────────

def _assemble_doc(
    decision_id:     str,
    layer2_doc:      dict | None,
    sensor_gate:     dict,
    health_gate:     dict,
    budget_gate:     dict,
    sensor_snapshot: dict,
    decision:        str,
    status:          str,
    reason:          str,
    mods:            list,
    constraints:     dict,
) -> dict:
    """Build the complete layer3_decisions document."""
    rec_id = layer2_doc.get('recommendation_id', '') if layer2_doc else ''
    plant_status = layer2_doc.get('plant_status', 'unknown') if layer2_doc else 'unknown'
    clean_snapshot = {k: v for k, v in sensor_snapshot.items() if k != 'source'}

    return {
        "decision_id":              decision_id,
        "timestamp":                datetime.datetime.now(),
        "layer2_recommendation_id": rec_id,
        "gate_results": {
            "sensor_safety": sensor_gate,
            "plant_health":  health_gate,
            "budget":        budget_gate,
        },
        "decision":                 decision,
        "reason":                   reason,
        "proposed_modifications":   mods,
        "runtime_constraints":      constraints,
        "budget_usage_pct":         budget_gate.get("usage_pct", 0.0),
        "main_cost_driver":         budget_gate.get("main_cost_driver"),
        "plant_status":             plant_status,
        "sensor_snapshot":          clean_snapshot,
        "status":                   status,
        "user_action":              None,
        "user_action_timestamp":    None,
        "previous_values":          {},
        "approved_values":          {},
    }


# ── Decision engine ───────────────────────────────────────────────────────────

def _make_decision(
    layer2_doc:      dict | None,
    sensor_gate:     dict,
    health_gate:     dict,
    budget_gate:     dict,
    sensor_snapshot: dict,
) -> dict:
    """
    Combine the three gate results into a final Layer 3 decision document.

    Decision logic (in priority order):
      1. sensor_gate FAIL                          → BLOCK
      2. health_gate FAIL                          → BLOCK
      3. health_gate MARGINAL + budget not OK      → ALERT_ONLY (protect stressed plant)
      4. health_gate MARGINAL + budget OK          → APPROVE   (as-is, no modifications)
      5. health_gate PASS + budget OK              → APPROVE
      6. health_gate PASS + budget WARNING         → MODIFY (conservative modifications)
      7. health_gate PASS + budget OVER_BUDGET     → MODIFY (stronger modifications)

    Status assigned:
      APPROVE / MODIFY  → pending_approval  (user can act)
      BLOCK             → blocked           (user cannot approve)
      ALERT_ONLY        → alert_only        (informational only)
    """
    did   = str(uuid.uuid4())
    sg    = sensor_gate.get('status')
    hg    = health_gate.get('status')
    bg    = budget_gate.get('status', BUDGET_OK)
    score = health_gate.get('stability_score')

    # ── 1. Sensor safety failure → BLOCK ──────────────────────────────────
    if sg == GATE_FAIL:
        return _assemble_doc(
            did, layer2_doc, sensor_gate, health_gate, budget_gate, sensor_snapshot,
            decision    = DECISION_BLOCK,
            status      = STATUS_BLOCKED,
            reason      = f"BLOCK — Sensor Safety Gate failed: {sensor_gate.get('reason', '')}",
            mods        = [],
            constraints = {},
        )

    # ── 2. Plant health failure → BLOCK ───────────────────────────────────
    if hg == GATE_FAIL:
        return _assemble_doc(
            did, layer2_doc, sensor_gate, health_gate, budget_gate, sensor_snapshot,
            decision    = DECISION_BLOCK,
            status      = STATUS_BLOCKED,
            reason      = f"BLOCK — Plant Health Gate failed: {health_gate.get('reason', '')}",
            mods        = [],
            constraints = {},
        )

    # ── 3. Marginal health + budget pressure → ALERT_ONLY ─────────────────
    if hg == GATE_MARGINAL and bg != BUDGET_OK:
        return _assemble_doc(
            did, layer2_doc, sensor_gate, health_gate, budget_gate, sensor_snapshot,
            decision    = DECISION_ALERT_ONLY,
            status      = STATUS_ALERT_ONLY,
            reason      = (f"ALERT_ONLY — Plant health is marginal (score={score}) "
                           f"and budget status is {bg}. "
                           "No modifications applied to an already-stressed plant. "
                           "Review budget and plant health before taking action."),
            mods        = [],
            constraints = {},
        )

    # ── 4. Marginal health + budget OK → APPROVE (no modifications) ───────
    if hg == GATE_MARGINAL and bg == BUDGET_OK:
        return _assemble_doc(
            did, layer2_doc, sensor_gate, health_gate, budget_gate, sensor_snapshot,
            decision    = DECISION_APPROVE,
            status      = STATUS_PENDING,
            reason      = (f"APPROVE — Plant health is marginal (score={score}) "
                           "but budget is OK. Layer 2 recommendation approved as-is "
                           "with no budget modifications. Monitor plant closely."),
            mods        = [],
            constraints = {},
        )

    # ── 5. All gates pass + budget OK → APPROVE ───────────────────────────
    if bg == BUDGET_OK:
        return _assemble_doc(
            did, layer2_doc, sensor_gate, health_gate, budget_gate, sensor_snapshot,
            decision    = DECISION_APPROVE,
            status      = STATUS_PENDING,
            reason      = (f"APPROVE — All gates passed. Sensors safe, plant stable (score={score}), "
                           f"budget at {budget_gate.get('usage_pct', 0):.1f}% (OK). "
                           "Layer 2 recommendation approved as-is."),
            mods        = [],
            constraints = {},
        )

    # ── 6–7. All gates pass + budget under pressure → MODIFY ──────────────
    mods, constraints = _build_proposed_modifications(budget_gate, sensor_snapshot, layer2_doc)

    if not mods:
        # No actionable modifications available → fall back to ALERT_ONLY
        return _assemble_doc(
            did, layer2_doc, sensor_gate, health_gate, budget_gate, sensor_snapshot,
            decision    = DECISION_ALERT_ONLY,
            status      = STATUS_ALERT_ONLY,
            reason      = (f"ALERT_ONLY — Budget is {bg} at {budget_gate.get('usage_pct', 0):.1f}% "
                           "but no safe modifications are available given current setpoints. "
                           "Manual review recommended."),
            mods        = [],
            constraints = {},
        )

    return _assemble_doc(
        did, layer2_doc, sensor_gate, health_gate, budget_gate, sensor_snapshot,
        decision    = DECISION_MODIFY,
        status      = STATUS_PENDING,
        reason      = (f"MODIFY — Budget is {bg} at {budget_gate.get('usage_pct', 0):.1f}%. "
                       f"Sensors safe, plant stable (score={score}). "
                       f"{len(mods)} budget modification(s) proposed. "
                       "Review and approve if acceptable."),
        mods        = mods,
        constraints = constraints,
    )


# ── Main entry point ──────────────────────────────────────────────────────────

def run(layer2_recommendation_id: str = None) -> dict:
    """
    Entry point for a Layer 3 review cycle.
    Called automatically after Layer 2 saves a recommendation (wired in Step 4+).
    Can also be triggered manually via the API.

    Steps:
      1. Cancel stale pending Layer 3 decisions
      2. Update layer3_status → running
      3. Load latest Layer 2 recommendation from MongoDB
      4. Collect live sensor snapshot (cache → MongoDB fallback)
      5. Run Gate 1 — Sensor Safety Gate
      6. Run Gate 2 — Plant Health Gate
      7. Run Gate 3 — Budget Gate (always runs for data — decision logic gates it)
      8. Build final decision document
      9. Insert into layer3_decisions collection
      10. Update layer3_status
      11. Return summary dict

    Does NOT apply any changes to setpoints, actuators, or MongoDB setpoints.
    All changes require user approval (Step 5+).
    """
    if _mongo_db is None:
        return {"success": False, "error": "Layer 3 not initialized — call init() first."}

    with _run_lock:
        _CUSTOM_PRINT_FUNC("[Layer3] ── Starting review cycle ──────────────────────")

        # ── Step 1: Cancel stale pending decisions ─────────────────────────
        cancelled = _mongo_db.cancel_pending_layer3_decisions()
        if cancelled:
            _CUSTOM_PRINT_FUNC(f"[Layer3] Cancelled {cancelled} stale pending decision(s).")

        # ── Step 2: Mark running ───────────────────────────────────────────
        _mongo_db.update_layer3_status({
            'current_status': 'running',
            'last_run_at':    datetime.datetime.now(),
        })

        try:
            # ── Step 3: Load Layer 2 doc ───────────────────────────────────
            layer2_doc = _get_latest_layer2_doc()
            if layer2_doc:
                score = layer2_doc.get('plant_stability_score')
                _CUSTOM_PRINT_FUNC(
                    f"[Layer3] Layer 2: status={layer2_doc.get('status')}  "
                    f"plant={layer2_doc.get('plant_status')}  "
                    f"score={score}  "
                    f"growth={layer2_doc.get('growth_assessment')}"
                )
            else:
                _CUSTOM_PRINT_FUNC("[Layer3] No Layer 2 recommendation found in MongoDB.")

            # ── Step 4: Sensor snapshot ────────────────────────────────────
            sensor_snapshot = _get_sensor_snapshot()
            _CUSTOM_PRINT_FUNC(
                f"[Layer3] Sensors (source={sensor_snapshot.get('source')}): "
                f"moisture={sensor_snapshot.get('soil_moisture')}%  "
                f"EC={sensor_snapshot.get('soil_ec')} µS/cm  "
                f"pH={sensor_snapshot.get('soil_ph')}  "
                f"airTemp={sensor_snapshot.get('air_temperature')}°C"
            )

            # ── Step 5: Gate 1 — Sensor Safety ────────────────────────────
            sensor_gate = _run_sensor_safety_gate(sensor_snapshot)
            _CUSTOM_PRINT_FUNC(
                f"[Layer3] Gate 1 Sensor Safety  → {sensor_gate['status'].upper()}  "
                f"| {sensor_gate['reason']}"
            )

            # ── Step 6: Gate 2 — Plant Health ─────────────────────────────
            health_gate = _run_plant_health_gate(layer2_doc)
            _CUSTOM_PRINT_FUNC(
                f"[Layer3] Gate 2 Plant Health    → {health_gate['status'].upper()}  "
                f"| {health_gate['reason']}"
            )

            # ── Step 7: Gate 3 — Budget ───────────────────────────────────
            # Always collect budget data (even if earlier gates blocked)
            # so the decision document always has full cost information.
            today_costs   = _mongo_db.get_today_costs(
                WATER_PRICE_PER_LITER_NIS,
                ELECTRICITY_PRICE_PER_KWH_NIS,
                FERTILIZER_PRICE_PER_5_LITERS_NIS,
            )
            budget_config = _mongo_db.get_budget_config()
            budget_gate   = _run_budget_gate(today_costs, budget_config)
            _CUSTOM_PRINT_FUNC(
                f"[Layer3] Gate 3 Budget          → {budget_gate['status'].upper()}  "
                f"| {budget_gate['reason']}"
            )

            # ── Step 8: Decision engine ────────────────────────────────────
            decision_doc = _make_decision(
                layer2_doc, sensor_gate, health_gate, budget_gate, sensor_snapshot
            )
            _CUSTOM_PRINT_FUNC(
                f"[Layer3] Decision: {decision_doc['decision']}  "
                f"status={decision_doc['status']}  "
                f"mods={len(decision_doc.get('proposed_modifications', []))}"
            )

            # ── Step 9: Save to MongoDB ────────────────────────────────────
            _mongo_db.insert_layer3_decision(decision_doc)

            # ── Step 10: Update layer3_status ──────────────────────────────
            ui_status = (
                'waiting_approval' if decision_doc['status'] == STATUS_PENDING
                else decision_doc['status']
            )
            _mongo_db.update_layer3_status({
                'current_status':       ui_status,
                'last_run_at':          decision_doc['timestamp'],
                'latest_decision_id':   decision_doc['decision_id'],
                'budget_status':        budget_gate.get('status', 'unknown'),
                'sensor_safety_status': sensor_gate.get('status', 'unknown'),
                'plant_health_status':  health_gate.get('status', 'unknown'),
                'blocked_reason': (
                    decision_doc.get('reason')
                    if decision_doc['decision'] == DECISION_BLOCK else None
                ),
            })

            _CUSTOM_PRINT_FUNC(
                f"[Layer3] ── Cycle complete: {decision_doc['decision']}  "
                f"id={decision_doc['decision_id'][:8]} ──────────────────"
            )

            return {
                "success":     True,
                "decision_id": decision_doc['decision_id'],
                "decision":    decision_doc['decision'],
                "status":      decision_doc['status'],
                "reason":      decision_doc['reason'],
                "mods_count":  len(decision_doc.get('proposed_modifications', [])),
                "budget_pct":  decision_doc.get('budget_usage_pct'),
                "main_driver": decision_doc.get('main_cost_driver'),
            }

        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[Layer3] ERROR in review cycle: {e}")
            _mongo_db.update_layer3_status({
                'current_status': 'error',
                'blocked_reason': str(e),
            })
            return {"success": False, "error": str(e)}
