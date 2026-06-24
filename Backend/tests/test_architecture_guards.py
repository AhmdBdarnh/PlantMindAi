"""
test_architecture_guards.py — 3-layer architecture regression tests.

Guards the core invariant of the project:
  * Layer 2 (AI Advisor) can NEVER apply setpoints directly.
  * Layer 3 (Budget Manager) never proposes fan-duty changes while the fan is
    PID-controlled (LAYER3_ALLOW_FAN_MODS = False).

Pure logic — no hardware, MongoDB, or OpenAI required.

Usage:
    cd Backend
    ./venv/bin/python tests/test_architecture_guards.py
"""
import os
import sys

# Make Backend/ importable when run from anywhere
_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BACKEND)

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))

import ai_setpoint_advisor as A
import layer3_budget_manager as L3


# ── 1. Layer 2 can NOT apply setpoints directly (function guard) ──────────────
ok, msg, applied = A.apply_recommendation("ai_rec_anything")
check("apply_recommendation refuses (success=False)", ok is False, f"success={ok}")
check("apply_recommendation applies nothing", applied == [], f"applied={applied}")
check("apply_recommendation explains Layer 3 required",
      "layer 3" in msg.lower() and "disabled" in msg.lower(), msg)


# ── 2. Fan flag is OFF ────────────────────────────────────────────────────────
check("LAYER3_ALLOW_FAN_MODS is False", L3.LAYER3_ALLOW_FAN_MODS is False)


# ── 3. Rule-based modifications never include fan; do include LED + moisture ──
class FakeSetpoints:
    def get_light_setpoint(self):         return 600.0
    def get_soil_humidity_setpoint(self): return 60.0

L3._setpoints = FakeSetpoints()   # inject a stand-in setpoints singleton

budget_gate = {"status": L3.BUDGET_OVER_BUDGET, "main_cost_driver": "electricity", "usage_pct": 140.0}
mods, constraints = L3._build_proposed_modifications(budget_gate, layer2_doc=None)
params = {m["parameter"] for m in mods}
check("rule-based: no fan_night_duty proposed", "fan_night_duty" not in params, f"params={params}")
check("rule-based: LED reduction proposed", "light_setpoint" in params, f"params={params}")
check("rule-based: moisture reduction proposed", "soil_moisture_setpoint" in params, f"params={params}")
check("rule-based: constraints carry no fan_night_duty", "fan_night_duty" not in constraints, f"constraints={constraints}")

mods2, _ = L3._build_proposed_modifications(
    {"status": L3.BUDGET_WARNING, "main_cost_driver": "water", "usage_pct": 90.0}, None)
check("rule-based (water): no fan mod", "fan_night_duty" not in {m["parameter"] for m in mods2})


# ── 4. AI-path sanitizer DROPS fan mods, keeps LED + moisture ─────────────────
current_sp = {"light": 600.0, "soil_moisture": 60.0, "fan_night_duty": 1024}
ai_mods = [
    {"parameter": "light_setpoint",         "proposed_value": 480.0},
    {"parameter": "fan_night_duty",         "proposed_value": 800},     # must be dropped
    {"parameter": "soil_moisture_setpoint", "proposed_value": 55.0},
    {"parameter": "temperature_setpoint",   "proposed_value": 25.0},    # not allowed → dropped
]
clean, cons = L3._sanitize_ai_mods(ai_mods, current_sp)
clean_params = {m["parameter"] for m in clean}
check("AI-path: fan_night_duty dropped", "fan_night_duty" not in clean_params, f"clean={clean_params}")
check("AI-path: temperature dropped (Layer 3 may not change it)", "temperature_setpoint" not in clean_params)
check("AI-path: LED kept", "light_setpoint" in clean_params, f"clean={clean_params}")
check("AI-path: moisture kept", "soil_moisture_setpoint" in clean_params, f"clean={clean_params}")
check("AI-path: constraints carry no fan_night_duty", "fan_night_duty" not in cons, f"cons={cons}")


# ── 5. Re-enabling the flag brings fan mods back (proves it is genuinely gated)
L3.LAYER3_ALLOW_FAN_MODS = True
clean_on, _ = L3._sanitize_ai_mods(ai_mods, current_sp)
check("flag ON re-enables fan mod (gate works both ways)",
      "fan_night_duty" in {m["parameter"] for m in clean_on})
L3.LAYER3_ALLOW_FAN_MODS = False   # restore


print("\n" + "=" * 52)
print(f"RESULT: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
print("ALL ARCHITECTURE TESTS PASSED")
