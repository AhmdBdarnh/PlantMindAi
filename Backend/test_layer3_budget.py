#!/usr/bin/env python3
"""
test_layer3_budget.py — Standalone Layer 3 budget-gate test.

Does NOT require MongoDB, sensors, or the full backend to be running.
Injects test data directly into the budget gate and prints structured decisions.

Usage:
    cd /home/mohamadaboria/Desktop/PlantMind\ AI/NewProject/Backend
    python test_layer3_budget.py

Test 1 — Water at 80% sub-budget (0.4 ₪ / 0.5 ₪ limit)
Test 2 — LED/electricity decision
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

# ── Silence the custom print function so we see clean JSON output ──────────────
import utils.utils as _utils
_utils._CUSTOM_PRINT_FUNC = print   # route [Layer3] logs to stdout

import layer3_budget_manager as _l3

# ── Mock setpoints so _build_proposed_modifications can propose LED changes ───
class _MockSetpoints:
    """Minimal stub — returns realistic setpoint values for test."""
    def get_light_setpoint(self):      return 750   # example light sensor units
    def get_soil_humidity_setpoint(self): return 65.0  # 65% soil moisture target

_l3._setpoints = _MockSetpoints()

# ─────────────────────────────────────────────────────────────────────────────
# TEST DATA
# ─────────────────────────────────────────────────────────────────────────────

TEST_TODAY_COSTS = {
    'date':                    '2026-06-02',
    # Water: 47 L × 0.00851 ₪/L ≈ 0.40 ₪
    'water_liters_today':      47.0,
    # Electricity: 1200 Wh (LED + fan usage through the day)
    'energy_wh_today':         1200.0,
    'fertilizer_liters_today': 0.05,
    # Cost fields (the ones Layer 3 actually reads)
    'water_cost_nis':          0.40,
    'electricity_cost_nis':    0.77,
    'fertilizer_cost_nis':     0.01,
    'total_cost_nis':          1.18,
}

TEST_BUDGET_CONFIG = {
    'daily_budget':          5.0,   # total NIS/day
    'water_budget':          0.5,   # ← 0.40 / 0.50 = 80%  (TEST 1)
    'electricity_budget':    1.0,   # ← 0.77 / 1.00 = 77%  (TEST 2 — just below threshold)
    'fertilizer_budget':     0.5,
    'warning_threshold_pct': 80,    # 80% triggers WARNING
}

# Safe sensor snapshot — plant is healthy, so health gate would PASS
SAFE_SENSORS = {
    'soil_moisture':    62.0,
    'soil_ec':          850.0,
    'soil_ph':          6.2,
    'air_temperature':  24.0,
    'air_humidity':     68.0,
    'soil_temperature': 23.0,
    'source':           'test_injection',
}

# ─────────────────────────────────────────────────────────────────────────────
# RUN THE GATES
# ─────────────────────────────────────────────────────────────────────────────

print()
print("═" * 72)
print("  LAYER 3 BUDGET GATE — TEST RUN")
print(f"  Scenario: water 0.40 ₪ / 0.50 ₪ budget  |  threshold 80%")
print("═" * 72)

budget_gate = _l3._run_budget_gate(TEST_TODAY_COSTS, TEST_BUDGET_CONFIG)
# _build_proposed_modifications(budget_gate, layer2_doc) — current 2-arg signature
mods, constraints = _l3._build_proposed_modifications(budget_gate, None)

# ─────────────────────────────────────────────────────────────────────────────
# PRINT GATE SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

print(f"\n[Gate 3 — Budget]  status={budget_gate['status'].upper()}")
print(f"  total usage : {budget_gate['usage_pct']:.1f}% of {budget_gate['daily_budget']:.2f} ₪ daily budget")
print(f"  reason      : {budget_gate['reason']}")
print(f"  main driver : {budget_gate['main_cost_driver']}")

# ─────────────────────────────────────────────────────────────────────────────
# PER-RESOURCE BREAKDOWN TABLE
# ─────────────────────────────────────────────────────────────────────────────

breakdown = budget_gate.get('resource_breakdown', [])
if breakdown:
    print()
    print(f"  {'RESOURCE':<13}  {'BUDGET (₪)':<12}  {'COST (₪)':<11}  {'USAGE %':<9}  {'THRESHOLD':<10}  STATUS")
    print(f"  {'-'*13}  {'-'*12}  {'-'*11}  {'-'*9}  {'-'*10}  {'-'*15}")
    for r in breakdown:
        if r.get('usage_pct') is not None:
            flag = " ⚠" if r['status'] in ('warning', 'over_budget') else ""
            print(
                f"  {r['resource']:<13}  {r['daily_budget_nis']:<12.2f}  "
                f"{r['current_cost_nis']:<11.4f}  {r['usage_pct']:<9.1f}  "
                f"{r['threshold_pct']:<10.0f}  {r['status'].upper()}{flag}"
            )
        else:
            print(f"  {r['resource']:<13}  (no sub-budget set)")

# ─────────────────────────────────────────────────────────────────────────────
# TEST 1 — WATER DECISION JSON
# ─────────────────────────────────────────────────────────────────────────────

water_r = next((r for r in breakdown if r['resource'] == 'water'), None)
if water_r:
    status_str = water_r['status']
    if status_str == 'warning':
        decision_str = "reduce_watering_frequency_or_send_warning"
        reason_str   = (
            f"Water cost reached {water_r['usage_pct']:.0f}% of the daily water budget "
            f"({water_r['current_cost_nis']:.2f} ₪ / {water_r['daily_budget_nis']:.2f} ₪). "
            "Recommend reducing irrigation frequency or waiting time to stay within budget."
        )
    elif status_str == 'over_budget':
        decision_str = "block_non_critical_watering_or_send_alert"
        reason_str   = (
            f"Water cost exceeded the daily water budget "
            f"({water_r['current_cost_nis']:.2f} ₪ > {water_r['daily_budget_nis']:.2f} ₪). "
            "Non-critical irrigation should be deferred."
        )
    else:
        decision_str = "no_action_needed"
        reason_str   = "Water cost is within budget."

    water_decision = {
        "layer":               3,
        "resource":            "water",
        "daily_budget_shekel": water_r['daily_budget_nis'],
        "current_cost_shekel": water_r['current_cost_nis'],
        "usage_percent":       water_r['usage_pct'],
        "threshold_percent":   water_r['threshold_pct'],
        "status":              status_str,
        "decision":            decision_str,
        "reason":              reason_str,
        "safety":              (
            "Do not stop or block watering if plant health or soil moisture requires water. "
            "Layer 3 only recommends frequency / cooldown reduction — "
            "pump power and pulse durations remain unchanged."
        ),
    }

    print()
    print("─" * 72)
    print("  TEST 1 — WATER DECISION")
    print("─" * 72)
    print(json.dumps(water_decision, indent=2, ensure_ascii=False))

# ─────────────────────────────────────────────────────────────────────────────
# TEST 2 — LED DECISION JSON
# ─────────────────────────────────────────────────────────────────────────────

elec_r  = next((r for r in breakdown if r['resource'] == 'electricity'), None)
led_mod = next((m for m in mods if m['type'] == 'led_power_reduction'), None)

if elec_r:
    elec_status = elec_r['status']
    if led_mod:
        led_decision_str = "reduce_led_intensity"
        led_reason       = (
            f"Electricity cost at {elec_r['usage_pct']:.0f}% of daily budget "
            f"({elec_r['current_cost_nis']:.4f} ₪ / {elec_r['daily_budget_nis']:.2f} ₪). "
            f"{led_mod['reason']}"
        )
        proposed_str = (
            f"{led_mod['current_value']} → {led_mod['proposed_value']} ({led_mod['unit']})"
        )
    elif elec_status in ('warning', 'over_budget'):
        led_decision_str = "send_warning"
        led_reason       = (
            f"Electricity cost at {elec_r['usage_pct']:.0f}% of daily budget. "
            "No LED setpoint available to reduce — warning only."
        )
        proposed_str = None
    else:
        led_decision_str = "no_action_needed"
        led_reason       = "Electricity cost is within budget."
        proposed_str     = None

    note = (
        "Electricity budget covers LED + fans combined. "
        "There is no separate LED watt meter — all loads share the electricity_budget."
    )

    led_decision = {
        "layer":                   3,
        "resource":                "led",
        "note":                    note,
        "daily_electricity_budget_shekel": elec_r['daily_budget_nis'],
        "current_electricity_cost_shekel": elec_r['current_cost_nis'],
        "usage_percent":           elec_r['usage_pct'],
        "threshold_percent":       elec_r['threshold_pct'],
        "status":                  elec_status,
        "decision":                led_decision_str,
        "proposed_light_setpoint": proposed_str,
        "reason":                  led_reason,
        "safety":                  (
            "Do not reduce light aggressively if plant growth or health needs light. "
            f"Layer 3 minimum LED floor is {_l3.LED_POWER_MIN_PCT}% of current setpoint. "
            "All changes require explicit user approval in the frontend."
        ),
    }

    print()
    print("─" * 72)
    print("  TEST 2 — LED / ELECTRICITY DECISION")
    print("─" * 72)
    print(json.dumps(led_decision, indent=2, ensure_ascii=False))

# ─────────────────────────────────────────────────────────────────────────────
# PROPOSED MODIFICATIONS SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

print()
print("─" * 72)
print(f"  PROPOSED MODIFICATIONS ({len(mods)} total)")
print("─" * 72)
if mods:
    for i, m in enumerate(mods, 1):
        print(f"\n  [{i}] type={m['type']}  parameter={m['parameter']}")
        print(f"      current={m['current_value']}  proposed={m['proposed_value']}  unit={m.get('unit','')}")
        print(f"      reason: {m['reason']}")
        if m.get('safety'):
            print(f"      safety: {m['safety']}")
else:
    print("  No modifications proposed (budget gate status may be OK).")

print()
print("═" * 72)
print("  WHERE IS THIS SAVED IN PRODUCTION?")
print("═" * 72)
print("""
  When running normally (not this test):
  • POST /api/layer3/run        → triggers _l3.run() → saves to MongoDB
  • GET  /api/layer3/latest     → frontend reads the decision
  • MongoDB collection          → layer3_decisions
  • Frontend page               → Layer3Decision (/layer3-decision)

  To save the test decision to MongoDB manually:
    POST http://<pi-ip>:5000/api/layer3/budget-config
    Body: {"water_budget": 0.5, "electricity_budget": 1.0, "warning_threshold_pct": 80}

    Then:
    POST http://<pi-ip>:5000/api/layer3/run
    GET  http://<pi-ip>:5000/api/layer3/latest
""")
