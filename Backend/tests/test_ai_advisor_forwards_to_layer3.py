"""
test_ai_advisor_forwards_to_layer3.py — route-level regression test.

Proves /api/ai-advisor/<id>/approve forwards to Layer 3 and NEVER applies
setpoints (the Layer 2 bypass must stay closed).

Uses Flask's test client with mocked dependencies — no hardware/DB/OpenAI.

Usage:
    cd Backend
    ./venv/bin/python tests/test_ai_advisor_forwards_to_layer3.py
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

# ── Spy on Layer 3 .run so we can prove forwarding without touching MongoDB ───
run_calls = []
def fake_run(layer2_recommendation_id=None):
    run_calls.append(layer2_recommendation_id)
    return {"success": True, "decision": "APPROVE", "decision_id": "dec_test_123",
            "status": "pending_approval"}
L3.run  = fake_run
L3.init = lambda *a, **k: None     # no-op init

# ── Mock setpoints — record any setter call (there must be NONE) ──────────────
setter_calls = []
class SpySetpoints:
    def __getattr__(self, name):
        def _rec(*a, **k):
            if name.startswith("set_"):
                setter_calls.append((name, a, k))
            return 0
        return _rec

setpoints = SpySetpoints()

# ── Mock mongo — return a recommendation that *would* have had changes ────────
mongo = MagicMock()
mongo.get_ai_recommendation_by_id.return_value = {
    "recommendation_id": "ai_rec_demo",
    "status": "needs_manual_review",
    "changes": [{"parameter": "Light", "recommended_value": 500}],
    "recommended_setpoints": {"Light": 500},
}

app = Flask(__name__)
routes.init_routes(
    app,
    MagicMock(), MagicMock(), setpoints,           # env_sensors, env_actuators, setpoints
    MagicMock(), MagicMock(), mongo,               # camera, s3, mongo
    MagicMock(), MagicMock(), MagicMock(),         # semaphores
    MagicMock(), MagicMock(),
)
client = app.test_client()

# ── Case A: existing recommendation → forwards to Layer 3, applies nothing ────
r = client.post("/api/ai-advisor/ai_rec_demo/approve", json={})
body = r.get_json()
check("approve returns HTTP 200", r.status_code == 200, f"status={r.status_code}")
check("response success=True", body.get("success") is True, str(body))
check("response forwarded_to_layer3=True", body.get("forwarded_to_layer3") is True)
check("response applied_changes is empty", body.get("applied_changes") == [], str(body.get("applied_changes")))
check("message mentions Budget Manager", "budget manager" in (body.get("message", "").lower()))
check("Layer 3 .run was called once", len(run_calls) == 1, f"calls={run_calls}")
check("Layer 3 .run got the rec id", run_calls == ["ai_rec_demo"], f"calls={run_calls}")
check("NO setpoint setter was called (no bypass)", setter_calls == [], f"setters={setter_calls}")

# ── Case B: unknown recommendation → 404, still no setters, no extra forward ──
mongo.get_ai_recommendation_by_id.return_value = None
r2 = client.post("/api/ai-advisor/does_not_exist/approve", json={})
check("unknown rec → HTTP 404", r2.status_code == 404, f"status={r2.status_code}")
check("unknown rec → no extra Layer 3 run", len(run_calls) == 1, f"calls={run_calls}")
check("unknown rec → still no setters", setter_calls == [], f"setters={setter_calls}")

print("\n" + "=" * 52)
print(f"RESULT: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
print("ALL ROUTE TESTS PASSED")
