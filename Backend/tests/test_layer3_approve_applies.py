"""
test_layer3_approve_applies.py — positive-path regression test.

Proves /api/layer3/approve IS allowed to apply setpoints, so closing the
Layer 2 bypass did not break the single legitimate approval path.

Uses Flask's test client with mocked dependencies — no hardware/DB/OpenAI.

Usage:
    cd Backend
    ./venv/bin/python tests/test_layer3_approve_applies.py
"""
import os
import sys
from unittest.mock import MagicMock

from flask import Flask

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BACKEND)

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))

import routes
import layer3_budget_manager as L3
L3.init = lambda *a, **k: None

# Spy setpoints: getters return a number, setters are recorded
setter_calls = []
class SpySetpoints:
    def __getattr__(self, name):
        def _rec(*a, **k):
            if name.startswith("set_"):
                setter_calls.append((name, a))
            return 600.0
        return _rec

setpoints = SpySetpoints()

mongo = MagicMock()
# APPROVE decision with no proposed_modifications → handler pulls Layer 2 changes
mongo.get_latest_layer3_decision.return_value = {
    "decision_id": "d1", "decision": "APPROVE", "status": "pending_approval",
    "layer2_recommendation_id": "r1", "proposed_modifications": [],
    "runtime_constraints": {},
}
mongo.get_ai_recommendation_by_id.return_value = {
    "recommendation_id": "r1",
    "changes": [{"parameter": "Light", "recommended_value": 480}],
}

app = Flask(__name__)
routes.init_routes(app, MagicMock(), MagicMock(), setpoints,
                   MagicMock(), MagicMock(), mongo,
                   MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
client = app.test_client()

r = client.post("/api/layer3/approve", json={})
body = r.get_json()
check("layer3 approve → HTTP 200", r.status_code == 200, f"status={r.status_code}")
check("layer3 approve success=True", body.get("success") is True, str(body))
check("a setpoint setter WAS called (single approval path works)",
      any(n == "set_light_setpoint" for n, _ in setter_calls), f"setters={setter_calls}")
check("applied list reports the change",
      any(a.get("parameter") == "light_setpoint" for a in body.get("applied", [])), str(body.get("applied")))

print("\n" + "=" * 52)
print(f"RESULT: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
print("LAYER 3 APPROVE PATH WORKS")
