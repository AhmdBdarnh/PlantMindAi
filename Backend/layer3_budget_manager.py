"""
layer3_budget_manager.py — Layer 3 AI Budget Manager for PlantMind AI.

Layer 3 is the budget governance layer. It evaluates resource costs vs. the
configured budgets and, when LAYER3_USE_AI is enabled (default), sends the
Layer 2 recommendation + today's resource costs + the budget configuration to
GPT, which returns the management decision and any cost-saving setpoint
modifications. A deterministic budget gate is still computed for the facts the
AI reasons over, and a rule-based path (`_make_decision`) is kept as a
fail-safe / test-mode fallback.

Layer 3 does NOT check plant health   — Layer 2 already does this.
Layer 3 does NOT check sensor safety  — Layer 1 handles real-time safety.

Decisions (made by the AI when enabled):
  APPROVE    — All costs within budget. Apply Layer 2 recommendation as-is.
  MODIFY     — One or more costs near / over budget. Propose cost reductions.
  ALERT_ONLY — Budget pressure detected but no safe modifications available.
  BLOCK      — Layer 2 recommendation is missing, invalid, or too stale to act on.

Safety guarantees that remain enforced in code regardless of the AI output:
  * If the OpenAI call fails or returns invalid JSON → decision fails safe to BLOCK.
  * Any AI-proposed numeric setpoint is clamped to the safety floors below
    (moisture ≥ 35 %, LED ≥ 40 % of current, night-fan ≥ 15 %) before it can
    ever be applied.
  * Layer 3 NEVER fires actuators directly and NEVER changes pump power/pulses.
  * All changes still require explicit user approval via the frontend.
"""

import os
import json
import datetime
import threading
import uuid

from utils.utils import _CUSTOM_PRINT_FUNC

# AI decision mode — when true (default) the management decision is produced by
# GPT (see _ai_make_decision). Set LAYER3_USE_AI=false in .env to fall back to
# the deterministic rule engine (_make_decision).
LAYER3_USE_AI = os.getenv('LAYER3_USE_AI', 'true').lower() == 'true'

try:
    from config import (
        WATER_PRICE_PER_LITER_NIS,
        ELECTRICITY_PRICE_PER_KWH_NIS,
        FERTILIZER_PRICE_PER_5_LITERS_NIS,
    )
except ImportError:
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

# ── Budget status constants ───────────────────────────────────────────────────

BUDGET_OK          = "ok"
BUDGET_WARNING     = "warning"
BUDGET_OVER_BUDGET = "over_budget"

# ── Decision document status constants ───────────────────────────────────────

STATUS_PENDING    = "pending_approval"   # APPROVE or MODIFY — user can act
STATUS_APPROVED   = "approved"           # set when user confirms
STATUS_REJECTED   = "rejected"           # set when user rejects
STATUS_CANCELLED  = "cancelled"          # replaced by a newer cycle
STATUS_BLOCKED    = "blocked"            # BLOCK — approve button disabled
STATUS_ALERT_ONLY = "alert_only"         # ALERT_ONLY — informational only

# ── Modification safety floors ────────────────────────────────────────────────
# Layer 3 never proposes values outside these bounds.

MOISTURE_SETPOINT_FLOOR = 35.0         # % — minimum allowed soil moisture target
LED_POWER_MIN_PCT       = 40           # % — never propose LED below 40% of current
FAN_NIGHT_DUTY_MIN      = int(4095 * 0.15)  # 15% of max PWM

# ── Layer 2 staleness limit ───────────────────────────────────────────────────

LAYER2_MAX_AGE_HOURS = 48   # Layer 2 data older than this → BLOCK (run Layer 2 again)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _doc_age_hours(doc: dict) -> float | None:
    """Return age of a document in hours based on created_at or timestamp field."""
    for field in ('created_at', 'timestamp'):
        ts = doc.get(field)
        if ts is not None:
            try:
                if hasattr(ts, 'timestamp'):
                    delta = (datetime.datetime.now() - ts).total_seconds()
                    return round(delta / 3600, 1)
            except Exception:
                pass
    return None


def _get_latest_layer2_doc() -> dict | None:
    """Return the latest Layer 2 recommendation document from MongoDB, or None."""
    if _mongo_db is None:
        return None
    try:
        return _mongo_db.get_latest_ai_recommendation()
    except Exception as e:
        _CUSTOM_PRINT_FUNC(f"[Layer3] Error fetching Layer 2 doc: {e}")
        return None




# ── Budget Evaluation ─────────────────────────────────────────────────────────

def _run_budget_gate(today_costs: dict, budget_config: dict) -> dict:
    """
    Compare today's resource costs against configured daily budget limits.

    Checks two levels:
      1. Total:        total_cost_nis vs daily_budget
      2. Per-resource: water vs water_budget, electricity vs electricity_budget,
                       fertilizer vs fertilizer_budget

    Effective status = worst of total + per-resource checks.

    Budget states:
      usage_pct < warning_threshold_pct  → ok
      warning_threshold_pct <= usage_pct <= 100  → warning
      usage_pct > 100                    → over_budget

    Returns:
      {"status": "ok"|"warning"|"over_budget", "reason": str,
       "usage_pct": float, "main_cost_driver": str|None,
       "today_costs": dict, "daily_budget": float,
       "resource_breakdown": list}
    """
    daily_budget = float(budget_config.get('daily_budget', 10.0))
    warn_pct     = float(budget_config.get('warning_threshold_pct', 80))

    total_cost = float(today_costs.get('total_cost_nis',        0.0))
    water_cost = float(today_costs.get('water_cost_nis',        0.0))
    elec_cost  = float(today_costs.get('electricity_cost_nis',  0.0))
    fert_cost  = float(today_costs.get('fertilizer_cost_nis',   0.0))

    if daily_budget <= 0:
        return {
            "status":             BUDGET_OK,
            "reason":             "Daily budget not configured (value <= 0) — budget evaluation skipped.",
            "usage_pct":          0.0,
            "main_cost_driver":   None,
            "today_costs":        today_costs,
            "daily_budget":       daily_budget,
            "resource_breakdown": [],
        }

    usage_pct   = round((total_cost / daily_budget) * 100.0, 1)
    costs       = {'electricity': elec_cost, 'water': water_cost, 'fertilizer': fert_cost}
    main_driver = max(costs, key=costs.get) if any(v > 0 for v in costs.values()) else None

    _status_rank = {BUDGET_OK: 0, BUDGET_WARNING: 1, BUDGET_OVER_BUDGET: 2}

    def _resource_status(cost: float, sub_budget: float):
        if sub_budget <= 0:
            return None, None
        pct = round((cost / sub_budget) * 100.0, 1)
        if pct > 100.0:
            return BUDGET_OVER_BUDGET, pct
        elif pct >= warn_pct:
            return BUDGET_WARNING, pct
        return BUDGET_OK, pct

    resource_checks = [
        ('water',       water_cost, float(budget_config.get('water_budget',       0.0))),
        ('electricity', elec_cost,  float(budget_config.get('electricity_budget', 0.0))),
        ('fertilizer',  fert_cost,  float(budget_config.get('fertilizer_budget',  0.0))),
    ]

    resource_breakdown  = []
    per_resource_worst  = BUDGET_OK
    triggered_resources = []

    for res_name, res_cost, res_budget in resource_checks:
        res_status, res_pct = _resource_status(res_cost, res_budget)
        resource_breakdown.append({
            'resource':         res_name,
            'daily_budget_nis': res_budget,
            'current_cost_nis': res_cost,
            'usage_pct':        res_pct,
            'threshold_pct':    warn_pct,
            'status':           res_status if res_status is not None else 'no_budget_set',
        })
        if res_status is not None:
            if _status_rank.get(res_status, 0) > _status_rank.get(per_resource_worst, 0):
                per_resource_worst = res_status
            if res_status in (BUDGET_WARNING, BUDGET_OVER_BUDGET):
                triggered_resources.append(f"{res_name}={res_pct:.0f}% of sub-budget")

    total_rank     = _status_rank.get(
        BUDGET_OVER_BUDGET if usage_pct > 100.0
        else (BUDGET_WARNING if usage_pct >= warn_pct else BUDGET_OK), 0
    )
    effective_rank = max(total_rank, _status_rank.get(per_resource_worst, 0))
    status         = [BUDGET_OK, BUDGET_WARNING, BUDGET_OVER_BUDGET][effective_rank]

    if status == BUDGET_OVER_BUDGET:
        reason = (f"OVER BUDGET: total {usage_pct:.1f}% used "
                  f"({total_cost:.4f} ₪ / {daily_budget:.2f} ₪). "
                  f"Main driver: {main_driver}.")
    elif status == BUDGET_WARNING:
        parts = [f"Budget WARNING: total {usage_pct:.1f}% used "
                 f"({total_cost:.4f} ₪ / {daily_budget:.2f} ₪). "
                 f"Main driver: {main_driver}."]
        if triggered_resources:
            parts.append(
                "Per-resource threshold reached — " + ", ".join(triggered_resources) + "."
            )
        reason = " ".join(parts)
    else:
        reason = f"Budget OK: total {usage_pct:.1f}% used ({total_cost:.4f} ₪ / {daily_budget:.2f} ₪)."

    return {
        "status":             status,
        "reason":             reason,
        "usage_pct":          usage_pct,
        "main_cost_driver":   main_driver,
        "today_costs":        today_costs,
        "daily_budget":       daily_budget,
        "resource_breakdown": resource_breakdown,
    }


# ── Proposed modifications builder ────────────────────────────────────────────

def _build_proposed_modifications(
    budget_gate: dict,
    layer2_doc:  dict | None,
) -> tuple:
    """
    Build cost-saving setpoint modifications based on budget evaluation.

    Rules:
      - Never change pump power or pulse durations.
      - Never propose soil moisture target below MOISTURE_SETPOINT_FLOOR (35%).
      - Never propose LED below LED_POWER_MIN_PCT (40%) of current setpoint.
      - Scale: WARNING → 15% reduction, OVER_BUDGET → 25% reduction.

    Returns:
      (modifications_list, runtime_constraints_dict)
    """
    modifications = []
    constraints   = {}

    budget_status = budget_gate.get('status', BUDGET_OK)
    main_driver   = budget_gate.get('main_cost_driver')
    usage_pct     = budget_gate.get('usage_pct', 0.0)
    reduction     = 0.25 if budget_status == BUDGET_OVER_BUDGET else 0.15

    # ── LED power reduction (electricity driver) ──────────────────────────────
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

    # ── Night fan duty reduction (electricity driver) ─────────────────────────
    if main_driver in ('electricity', None) or budget_status == BUDGET_OVER_BUDGET:
        try:
            import control_loops
            current_night_duty = control_loops.FAN_NIGHT_DUTY
        except Exception:
            current_night_duty = 1024   # fallback: 25% of 4095
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
                "reason":         (f"Night fan reduction conserves electricity. "
                                   f"Proposed: {current_pct:.0f}% → {proposed_pct:.0f}%. "
                                   f"Budget at {usage_pct:.1f}%."),
                "savings_impact": "low",
            })
            constraints['fan_night_duty'] = proposed_night_duty

    # ── Soil moisture target reduction (water driver) ─────────────────────────
    if main_driver == 'water' or budget_status == BUDGET_OVER_BUDGET:
        current_moisture = None
        if _setpoints is not None:
            try:
                current_moisture = _setpoints.get_soil_humidity_setpoint()
            except Exception:
                pass
        if current_moisture is not None and current_moisture > MOISTURE_SETPOINT_FLOOR + 5.0:
            reduce_by         = 5.0 if budget_status == BUDGET_OVER_BUDGET else 3.0
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
                    "safety":         ("Pump power and pulse durations are unchanged. "
                                       "Layer 1 will still water when needed — only frequency changes."),
                    "savings_impact": "medium",
                })
                constraints['moisture_target'] = proposed_moisture

    return modifications, constraints


# ── Decision document assembler ───────────────────────────────────────────────

def _assemble_doc(
    decision_id:  str,
    layer2_doc:   dict | None,
    budget_gate:  dict,
    decision:     str,
    status:       str,
    reason:       str,
    mods:         list,
    constraints:  dict,
) -> dict:
    """Build the complete layer3_decisions document."""
    rec_id       = layer2_doc.get('recommendation_id', '') if layer2_doc else ''
    plant_status = layer2_doc.get('plant_status', 'unknown') if layer2_doc else 'unknown'

    return {
        "decision_id":              decision_id,
        "timestamp":                datetime.datetime.now(),
        "layer2_recommendation_id": rec_id,
        "gate_results": {
            "budget": budget_gate,
        },
        "decision":               decision,
        "reason":                 reason,
        "proposed_modifications": mods,
        "runtime_constraints":    constraints,
        "budget_usage_pct":       budget_gate.get("usage_pct", 0.0),
        "main_cost_driver":       budget_gate.get("main_cost_driver"),
        "plant_status":           plant_status,
        "status":                 status,
        "user_action":            None,
        "user_action_timestamp":  None,
        "previous_values":        {},
        "approved_values":        {},
    }


# ── Decision engine (budget-only) ─────────────────────────────────────────────

def _make_decision(layer2_doc: dict | None, budget_gate: dict) -> dict:
    """
    Make a Layer 3 decision based solely on budget evaluation.

    Decision logic:
      1. No Layer 2 doc found            → BLOCK (nothing to evaluate)
      2. Layer 2 status == 'invalid'     → BLOCK (invalid recommendation)
      3. Layer 2 age > LAYER2_MAX_AGE_HOURS → BLOCK (too stale, run Layer 2 again)
      4. Budget OK                        → APPROVE
      5. Budget WARNING or OVER_BUDGET    → MODIFY (propose cost reductions)
      6. Budget pressure but no safe mods → ALERT_ONLY
    """
    did = str(uuid.uuid4())
    bg  = budget_gate.get('status', BUDGET_OK)

    # ── 1. No Layer 2 recommendation ─────────────────────────────────────────
    if layer2_doc is None:
        return _assemble_doc(
            did, layer2_doc, budget_gate,
            decision    = DECISION_BLOCK,
            status      = STATUS_BLOCKED,
            reason      = "BLOCK — No Layer 2 recommendation found. Run the AI Advisor first.",
            mods        = [],
            constraints = {},
        )

    # ── 2. Invalid Layer 2 recommendation ────────────────────────────────────
    if layer2_doc.get('status') == 'invalid':
        return _assemble_doc(
            did, layer2_doc, budget_gate,
            decision    = DECISION_BLOCK,
            status      = STATUS_BLOCKED,
            reason      = ("BLOCK — Layer 2 recommendation is marked invalid. "
                           "Run the AI Advisor again to get a valid recommendation."),
            mods        = [],
            constraints = {},
        )

    # ── 3. Stale Layer 2 recommendation ──────────────────────────────────────
    age_h = _doc_age_hours(layer2_doc)
    if age_h is not None and age_h > LAYER2_MAX_AGE_HOURS:
        return _assemble_doc(
            did, layer2_doc, budget_gate,
            decision    = DECISION_BLOCK,
            status      = STATUS_BLOCKED,
            reason      = (f"BLOCK — Layer 2 recommendation is {age_h:.1f}h old "
                           f"(limit: {LAYER2_MAX_AGE_HOURS}h). "
                           "Run the AI Advisor again to get a fresh recommendation."),
            mods        = [],
            constraints = {},
        )

    # ── 4. Budget OK → APPROVE ────────────────────────────────────────────────
    if bg == BUDGET_OK:
        return _assemble_doc(
            did, layer2_doc, budget_gate,
            decision    = DECISION_APPROVE,
            status      = STATUS_PENDING,
            reason      = (f"APPROVE — All resource costs are within budget "
                           f"({budget_gate.get('usage_pct', 0):.1f}% of daily budget used). "
                           "Layer 2 recommendation approved as-is."),
            mods        = [],
            constraints = {},
        )

    # ── 5. Budget WARNING or OVER_BUDGET → try MODIFY ────────────────────────
    mods, constraints = _build_proposed_modifications(budget_gate, layer2_doc)

    if not mods:
        return _assemble_doc(
            did, layer2_doc, budget_gate,
            decision    = DECISION_ALERT_ONLY,
            status      = STATUS_ALERT_ONLY,
            reason      = (f"ALERT_ONLY — Budget is {bg} at {budget_gate.get('usage_pct', 0):.1f}% "
                           "but no safe cost-saving modifications are available given current setpoints. "
                           "Review your budget configuration or current setpoints manually."),
            mods        = [],
            constraints = {},
        )

    return _assemble_doc(
        did, layer2_doc, budget_gate,
        decision    = DECISION_MODIFY,
        status      = STATUS_PENDING,
        reason      = (f"MODIFY — Budget is {bg} at {budget_gate.get('usage_pct', 0):.1f}%. "
                       f"{len(mods)} cost-saving modification(s) proposed. "
                       "Review and approve if acceptable."),
        mods        = mods,
        constraints = constraints,
    )


# ── AI-powered decision engine ────────────────────────────────────────────────

def _current_setpoints() -> dict:
    """Return the live setpoints dict, or {} if unavailable."""
    try:
        return _setpoints.get_all_setpoints() if _setpoints is not None else {}
    except Exception:
        return {}


def _build_layer3_prompt(
    layer2_doc:    dict | None,
    budget_gate:   dict,
    today_costs:   dict,
    budget_config: dict,
    current_sp:    dict,
) -> str:
    """Build the JSON-only prompt sent to GPT for the Layer 3 budget decision."""
    age_h = _doc_age_hours(layer2_doc) if layer2_doc else None

    layer2_summary = {
        "exists":        layer2_doc is not None,
        "status":        layer2_doc.get("status") if layer2_doc else None,
        "plant_status":  layer2_doc.get("plant_status") if layer2_doc else None,
        "age_hours":     age_h,
        "max_age_hours": LAYER2_MAX_AGE_HOURS,
        "changes":       (layer2_doc.get("changes") or []) if layer2_doc else [],
    }

    facts = {
        "layer2_recommendation": layer2_summary,
        "today_costs_nis": {
            "water":       today_costs.get("water_cost_nis", 0.0),
            "electricity": today_costs.get("electricity_cost_nis", 0.0),
            "fertilizer":  today_costs.get("fertilizer_cost_nis", 0.0),
            "total":       today_costs.get("total_cost_nis", 0.0),
        },
        "budget_config": {
            "daily_budget":          budget_config.get("daily_budget"),
            "water_budget":          budget_config.get("water_budget"),
            "electricity_budget":    budget_config.get("electricity_budget"),
            "fertilizer_budget":     budget_config.get("fertilizer_budget"),
            "warning_threshold_pct": budget_config.get("warning_threshold_pct", 80),
        },
        "computed_budget_status": {
            "status":           budget_gate.get("status"),
            "usage_pct":        budget_gate.get("usage_pct"),
            "main_cost_driver": budget_gate.get("main_cost_driver"),
            "resource_breakdown": budget_gate.get("resource_breakdown", []),
        },
        "current_setpoints_for_cost_saving": {
            "light_setpoint":         current_sp.get("light"),
            "soil_moisture_setpoint": current_sp.get("soil_moisture"),
            "fan_night_duty":         current_sp.get("fan_night_duty"),
        },
        "safety_floors": {
            "soil_moisture_setpoint_min": MOISTURE_SETPOINT_FLOOR,
            "light_setpoint_min_pct_of_current": LED_POWER_MIN_PCT,
            "fan_night_duty_min": FAN_NIGHT_DUTY_MIN,
        },
    }

    return f"""You are the Budget Manager (Layer 3) of the PlantMind AI greenhouse system.
A separate AI advisor (Layer 2) has already produced a plant-care setpoint recommendation.
Your ONLY job is the MANAGEMENT / BUDGET decision: decide whether that recommendation may
proceed to the user for approval, given the resource costs and the configured budget.

You do NOT evaluate plant health and you do NOT change pump power or pump pulse durations.
You may only ever propose lowering these three cost-saving setpoints (never raise them):
light_setpoint, fan_night_duty, soil_moisture_setpoint — and never below the safety floors.

=== DECISION RULES ===
- BLOCK      if the Layer 2 recommendation is missing, its status is "invalid", or it is
             older than max_age_hours. Nothing can be approved in this case.
- APPROVE    if total cost is within the daily budget (no budget pressure).
- MODIFY     if budget usage is at/over the warning threshold or over budget AND you can
             propose at least one safe cost-saving reduction. Reduce the main cost driver:
             electricity → lower light_setpoint and/or fan_night_duty;
             water → lower soil_moisture_setpoint. Use ~15% reductions for a warning and
             ~25% for over-budget, but NEVER below the safety floors.
- ALERT_ONLY if there is budget pressure but no safe modification is available.

=== DATA (JSON) ===
{json.dumps(facts, indent=2, default=str)}

=== REQUIRED RESPONSE — return ONLY this JSON object, no markdown, no extra text ===
{{
  "decision": "APPROVE | MODIFY | ALERT_ONLY | BLOCK",
  "reason": "one or two short sentences explaining the decision using the numbers above",
  "proposed_modifications": [
    {{
      "type": "led_power_reduction | fan_night_reduction | moisture_target_reduction",
      "parameter": "light_setpoint | fan_night_duty | soil_moisture_setpoint",
      "current_value": number,
      "proposed_value": number,
      "unit": "sensor units | PWM duty (0-4095) | %",
      "reason": "why this reduction saves cost",
      "savings_impact": "low | medium | high"
    }}
  ]
}}
If decision is not MODIFY, "proposed_modifications" MUST be an empty array [].
"""


def _sanitize_ai_mods(mods: list, current_sp: dict) -> tuple:
    """
    Clamp AI-proposed modifications to the safety floors and drop anything that
    is not a recognised cost-saving reduction. Returns (clean_mods, constraints).

    This is a hard safety guardrail: even a "full AI" decision can never push an
    actuator-affecting setpoint below its floor or above its current value.
    """
    clean: list = []
    constraints: dict = {}
    if not isinstance(mods, list):
        return clean, constraints

    cur_light    = _safe_num(current_sp.get("light"))
    cur_moisture = _safe_num(current_sp.get("soil_moisture"))
    cur_fan_night = _safe_num(current_sp.get("fan_night_duty"))

    for m in mods:
        if not isinstance(m, dict):
            continue
        param    = m.get("parameter")
        proposed = _safe_num(m.get("proposed_value"))
        if proposed is None:
            continue

        if param == "light_setpoint" and cur_light and cur_light > 0:
            floor = cur_light * (LED_POWER_MIN_PCT / 100.0)
            proposed = round(max(floor, min(proposed, cur_light)), 1)
            if proposed >= cur_light:
                continue
            constraints["led_power_cap"] = round((proposed / cur_light) * 100.0, 1)
            clean.append({**m, "parameter": param, "current_value": cur_light,
                          "proposed_value": proposed, "unit": m.get("unit", "sensor units")})

        elif param == "fan_night_duty" and cur_fan_night and cur_fan_night > 0:
            proposed = int(max(FAN_NIGHT_DUTY_MIN, min(proposed, cur_fan_night)))
            if proposed >= cur_fan_night:
                continue
            constraints["fan_night_duty"] = proposed
            clean.append({**m, "parameter": param, "current_value": cur_fan_night,
                          "proposed_value": proposed, "unit": m.get("unit", "PWM duty (0-4095)")})

        elif param == "soil_moisture_setpoint" and cur_moisture and cur_moisture > 0:
            proposed = round(max(MOISTURE_SETPOINT_FLOOR, min(proposed, cur_moisture)), 1)
            if proposed >= cur_moisture:
                continue
            constraints["moisture_target"] = proposed
            clean.append({**m, "parameter": param, "current_value": cur_moisture,
                          "proposed_value": proposed, "unit": m.get("unit", "%")})
        # any other parameter is silently dropped — Layer 3 may not change it

    return clean, constraints


def _safe_num(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _ai_make_decision(
    layer2_doc:    dict | None,
    budget_gate:   dict,
    today_costs:   dict,
    budget_config: dict,
) -> dict:
    """
    Produce the Layer 3 decision using GPT.

    Fail-safe: any OpenAI error, missing key, or unparseable response yields a
    BLOCK decision so that an AI/network problem can never silently approve or
    apply a change. All proposed numeric values are clamped to the safety floors.
    """
    did        = str(uuid.uuid4())
    current_sp = _current_setpoints()
    prompt     = _build_layer3_prompt(layer2_doc, budget_gate, today_costs, budget_config, current_sp)

    try:
        import ai_setpoint_advisor
        parsed, raw = ai_setpoint_advisor._call_openai(prompt)
    except Exception as e:
        _CUSTOM_PRINT_FUNC(f"[Layer3] AI decision failed ({e}) — failing safe to BLOCK.")
        doc = _assemble_doc(
            did, layer2_doc, budget_gate,
            decision    = DECISION_BLOCK,
            status      = STATUS_BLOCKED,
            reason      = ("BLOCK — the AI Budget Manager could not be reached "
                           f"({type(e).__name__}). No changes were applied. Try again."),
            mods        = [],
            constraints = {},
        )
        doc["ai_powered"] = True
        doc["ai_error"]   = str(e)
        return doc

    decision = str(parsed.get("decision", "")).strip().upper()
    reason   = parsed.get("reason") or ""

    if decision not in (DECISION_APPROVE, DECISION_MODIFY, DECISION_ALERT_ONLY, DECISION_BLOCK):
        _CUSTOM_PRINT_FUNC(f"[Layer3] AI returned unknown decision '{decision}' — failing safe to BLOCK.")
        doc = _assemble_doc(
            did, layer2_doc, budget_gate,
            decision    = DECISION_BLOCK,
            status      = STATUS_BLOCKED,
            reason      = "BLOCK — AI returned an unrecognised decision. No changes applied.",
            mods        = [],
            constraints = {},
        )
        doc["ai_powered"]      = True
        doc["ai_raw_response"] = raw
        return doc

    mods, constraints = _sanitize_ai_mods(parsed.get("proposed_modifications", []), current_sp)

    # MODIFY with no surviving safe modification degrades to ALERT_ONLY.
    if decision == DECISION_MODIFY and not mods:
        decision = DECISION_ALERT_ONLY
        reason   = (reason + " (No proposed change passed the safety floors, "
                             "so this is informational only.)").strip()

    status_map = {
        DECISION_APPROVE:    STATUS_PENDING,
        DECISION_MODIFY:     STATUS_PENDING,
        DECISION_ALERT_ONLY: STATUS_ALERT_ONLY,
        DECISION_BLOCK:      STATUS_BLOCKED,
    }

    doc = _assemble_doc(
        did, layer2_doc, budget_gate,
        decision    = decision,
        status      = status_map[decision],
        reason      = reason or f"{decision} — decided by the AI Budget Manager.",
        mods        = mods if decision == DECISION_MODIFY else [],
        constraints = constraints if decision == DECISION_MODIFY else {},
    )
    doc["ai_powered"]      = True
    doc["ai_raw_response"] = raw
    return doc


# ── Main entry point ──────────────────────────────────────────────────────────

def run(layer2_recommendation_id: str = None) -> dict:
    """
    Entry point for a Layer 3 budget evaluation cycle.
    Called automatically after Layer 2 saves a recommendation.
    Can also be triggered manually via POST /api/layer3/run.

    Steps:
      1. Cancel stale pending Layer 3 decisions
      2. Update layer3_status → running
      3. Load latest Layer 2 recommendation from MongoDB
      4. Get today's costs and budget config
      5. Run budget evaluation
      6. Make decision
      7. Save decision to layer3_decisions collection
      8. Update layer3_status
      9. Return summary

    Does NOT fire actuators. Does NOT apply setpoints.
    All changes require explicit user approval via the frontend.
    """
    if _mongo_db is None:
        return {"success": False, "error": "Layer 3 not initialized — call init() first."}

    with _run_lock:
        _CUSTOM_PRINT_FUNC("[Layer3] ── Starting budget evaluation ──────────────────")

        # ── Step 1: Cancel stale pending decisions ────────────────────────
        cancelled = _mongo_db.cancel_pending_layer3_decisions()
        if cancelled:
            _CUSTOM_PRINT_FUNC(f"[Layer3] Cancelled {cancelled} stale pending decision(s).")

        # ── Step 2: Mark running ──────────────────────────────────────────
        _mongo_db.update_layer3_status({
            'current_status': 'running',
            'last_run_at':    datetime.datetime.now(),
        })

        try:
            # ── Step 3: Load Layer 2 recommendation ───────────────────────
            layer2_doc = _get_latest_layer2_doc()
            if layer2_doc:
                _CUSTOM_PRINT_FUNC(
                    f"[Layer3] Layer 2 doc: status={layer2_doc.get('status')}  "
                    f"plant={layer2_doc.get('plant_status')}  "
                    f"age={_doc_age_hours(layer2_doc)}h"
                )
            else:
                _CUSTOM_PRINT_FUNC("[Layer3] No Layer 2 recommendation found in MongoDB.")

            # ── Step 4 & 5: Budget evaluation ─────────────────────────────
            today_costs   = _mongo_db.get_today_costs(
                WATER_PRICE_PER_LITER_NIS,
                ELECTRICITY_PRICE_PER_KWH_NIS,
                FERTILIZER_PRICE_PER_5_LITERS_NIS,
            )
            budget_config = _mongo_db.get_budget_config()
            budget_gate   = _run_budget_gate(today_costs, budget_config)
            _CUSTOM_PRINT_FUNC(
                f"[Layer3] Budget → {budget_gate['status'].upper()}  "
                f"| {budget_gate['reason']}"
            )

            # ── Step 6: Decision (AI-powered when LAYER3_USE_AI, else rules) ─
            if LAYER3_USE_AI:
                _CUSTOM_PRINT_FUNC("[Layer3] Asking the AI Budget Manager for a decision ...")
                decision_doc = _ai_make_decision(
                    layer2_doc, budget_gate, today_costs, budget_config
                )
            else:
                decision_doc = _make_decision(layer2_doc, budget_gate)
            _CUSTOM_PRINT_FUNC(
                f"[Layer3] Decision: {decision_doc['decision']}  "
                f"status={decision_doc['status']}  "
                f"ai={decision_doc.get('ai_powered', False)}  "
                f"mods={len(decision_doc.get('proposed_modifications', []))}"
            )

            # ── Step 7: Save to MongoDB ────────────────────────────────────
            _mongo_db.insert_layer3_decision(decision_doc)

            # ── Step 8: Update layer3_status ──────────────────────────────
            ui_status = (
                'waiting_approval' if decision_doc['status'] == STATUS_PENDING
                else decision_doc['status']
            )
            _mongo_db.update_layer3_status({
                'current_status':     ui_status,
                'last_run_at':        decision_doc['timestamp'],
                'latest_decision_id': decision_doc['decision_id'],
                'budget_status':      budget_gate.get('status', 'unknown'),
                'blocked_reason': (
                    decision_doc.get('reason')
                    if decision_doc['decision'] == DECISION_BLOCK else None
                ),
            })

            # ── Step 8b: UI notification (bell/toast) — UI only, never email ──
            try:
                import notifications
                _dec = decision_doc['decision']
                _did = decision_doc['decision_id']
                if decision_doc['status'] == STATUS_PENDING:
                    notifications.create_notification(
                        'approval_required', 'warning',
                        'Approval required',
                        f"Budget Manager decision '{_dec}' is waiting for your approval.",
                        category='workflow', link='layer3',
                        meta={'decision_id': _did, 'decision': _dec},
                        dedup_key=f"layer3_approval:{_did}", dedup_window_sec=86400,
                    )
                else:
                    notifications.create_notification(
                        'budget_review_ready', 'info',
                        'Budget review ready',
                        f"Budget Manager completed its review: {_dec}.",
                        category='workflow', link='layer3',
                        meta={'decision_id': _did, 'decision': _dec},
                        dedup_key=f"layer3_decision:{_did}", dedup_window_sec=86400,
                    )
            except Exception as _ntf_err:
                _CUSTOM_PRINT_FUNC(f"[Notifications] layer3 decision skipped: {_ntf_err}")

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
            _CUSTOM_PRINT_FUNC(f"[Layer3] ERROR in budget evaluation: {e}")
            _mongo_db.update_layer3_status({
                'current_status': 'error',
                'blocked_reason': str(e),
            })
            # Single user-facing notification for a failed review — the workflow
            # could not finish, so the user should know. Deduped per recommendation
            # so one broken run can't spam the bell on retries.
            try:
                import notifications
                _wf_key = layer2_recommendation_id or 'unknown'
                notifications.create_notification(
                    'workflow_failed', 'critical',
                    'Budget review failed',
                    'The Budget Manager could not finish reviewing the AI recommendation. '
                    'No changes were applied.',
                    category='workflow', link='layer3',
                    meta={'recommendation_id': layer2_recommendation_id, 'error': str(e)},
                    dedup_key=f"workflow_failed:{_wf_key}", dedup_window_sec=86400,
                )
            except Exception as _ntf_err:
                _CUSTOM_PRINT_FUNC(f"[Notifications] workflow_failed skipped: {_ntf_err}")
            return {"success": False, "error": str(e)}


# ── Test-mode entry point ─────────────────────────────────────────────────────

def run_test(injected_sensors: dict = None, injected_costs: dict = None) -> dict:
    """
    Test-mode Layer 3 budget evaluation.
    Does NOT write to MongoDB. Does NOT cancel pending decisions.
    Inject cost values to test budget decisions without affecting the live system.

    Parameters:
      injected_costs   — override today_costs dict (water_cost_nis, electricity_cost_nis,
                         fertilizer_cost_nis, total_cost_nis).
                         If None, uses zero costs (budget OK).
      injected_sensors — unused by decision logic; accepted for API compatibility.
    """
    _CUSTOM_PRINT_FUNC("[Layer3-TEST] ── Starting test cycle (no DB writes) ──────")

    default_costs = {
        'date':                    'test',
        'water_liters_today':      0.0,
        'energy_wh_today':         0.0,
        'fertilizer_liters_today': 0.0,
        'water_cost_nis':          0.0,
        'electricity_cost_nis':    0.0,
        'fertilizer_cost_nis':     0.0,
        'total_cost_nis':          0.0,
    }
    today_costs = {**default_costs, **(injected_costs or {})}
    if injected_costs and 'total_cost_nis' not in injected_costs:
        today_costs['total_cost_nis'] = round(
            today_costs['water_cost_nis'] +
            today_costs['electricity_cost_nis'] +
            today_costs['fertilizer_cost_nis'], 4
        )

    # Minimal fake Layer 2 doc — budget evaluation only needs status and age
    fake_layer2 = {
        'recommendation_id': 'test_layer2',
        'plant_status':      'healthy',
        'created_at':        datetime.datetime.now(),
        'status':            'pending',
    }

    budget_config = {}
    if _mongo_db is not None:
        try:
            budget_config = _mongo_db.get_budget_config()
        except Exception:
            pass

    budget_gate = _run_budget_gate(today_costs, budget_config)
    _CUSTOM_PRINT_FUNC(
        f"[Layer3-TEST] Budget → {budget_gate['status'].upper()} | {budget_gate['reason']}"
    )

    decision_doc = _make_decision(fake_layer2, budget_gate)
    decision_doc['test_mode']           = True
    decision_doc['test_injected_costs'] = today_costs

    _CUSTOM_PRINT_FUNC(
        f"[Layer3-TEST] Decision: {decision_doc['decision']}  "
        f"mods={len(decision_doc.get('proposed_modifications', []))}"
    )

    return {
        "success":                True,
        "test_mode":              True,
        "decision":               decision_doc['decision'],
        "status":                 decision_doc['status'],
        "reason":                 decision_doc['reason'],
        "budget_pct":             decision_doc.get('budget_usage_pct'),
        "main_driver":            decision_doc.get('main_cost_driver'),
        "resource_breakdown":     budget_gate.get('resource_breakdown', []),
        "proposed_modifications": decision_doc.get('proposed_modifications', []),
        "gate_results":           decision_doc.get('gate_results'),
        "today_costs":            today_costs,
    }
