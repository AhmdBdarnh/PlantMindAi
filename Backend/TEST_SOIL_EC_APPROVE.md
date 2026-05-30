# Test: APPROVE Decision with Soil EC + Soil Moisture Changes

## Your Exact Failing Case
Layer 2 recommends:
- Soil EC: 1000 → 900
- Soil Moisture: 48 → 45

Previously, MongoDB setpoints stayed at:
- soil_ec: 1000 ❌
- soil_moisture: 48 ❌

## After Fix
All three parameters should now be in the approval map:
- ✅ soil_ec_setpoint (NEW - added in routes.py _L3_SETPOINT_MAP)
- ✅ soil_moisture_setpoint (existing)
- ✅ light_setpoint (existing)

## Test Steps

### Step 1: Verify Current Setpoints
```
Open PlantEnvironment page and note:
- Soil EC (current): _____ µS/cm
- Soil Moisture (current): _____ %
```

### Step 2: Create Layer 2 Recommendation with Soil EC + Moisture Changes
```
Run Layer 2 AI Advisor and verify it recommends:
- Soil EC: <current> → 900
- Soil Moisture: <current> → 45
```

### Step 3: Trigger Layer 3 Review
```
Go to Budget Manager page
Click "Run Layer 3 Review"
Wait for completion
```

### Step 4: Verify APPROVE Decision with Empty proposed_modifications
```
Layer 3 should create APPROVE decision with:
- decision: "APPROVE" ✓
- proposed_modifications: [] (EMPTY - this is the critical test case!) ✓
- layer2_recommendation_id: <reference to Layer 2 rec> ✓
```

### Step 5: Approve the Decision
```
Click "Approve" button
Expected response should show:
{
  "success": true,
  "message": "Layer 3 decision approved. 2 change(s) applied.",
  "applied": [
    {
      "parameter": "soil_ec_setpoint",
      "previous": 1000,
      "applied": 900,
      "unit": "µS/cm"
    },
    {
      "parameter": "soil_moisture_setpoint",
      "previous": 48,
      "applied": 45,
      "unit": "%"
    }
  ],
  "skipped": [],
  "setpoints": { ... updated setpoints ... }
}
```

### Step 6: Verify In-Memory Changes (Frontend)
```
PlantEnvironment page should immediately show:
- Soil EC: 1000 → 900 ✓
- Soil Moisture: 48 → 45 ✓
```

### Step 7: Verify MongoDB Persistence
```
Check MongoDB setpoints collection → greenhouse_setpoints document:

Before approval:
{
  "soil_ec": 1000,
  "soil_moisture": 48
}

After approval:
{
  "soil_ec": 900,           ✓ (CHANGED)
  "soil_moisture": 45       ✓ (CHANGED)
}
```

### Step 8: Verify Decision Document Updated
```
Check MongoDB layer3_decisions collection → latest decision:

{
  "decision_id": "...",
  "decision": "APPROVE",
  "status": "approved",
  "user_action": "approved",
  "previous_values": {
    "soil_ec": 1000,        ✓ 
    "soil_moisture": 48     ✓
  },
  "approved_values": {
    "soil_ec": 900,         ✓
    "soil_moisture": 45     ✓
  }
}
```

## Code Changes Made

1. **routes.py - _L3_SETPOINT_MAP** (line ~1046):
   ```python
   _L3_SETPOINT_MAP = {
       'light_setpoint':         ('light', ...),
       'soil_ec_setpoint':       ('soil_ec', ...),           # NEW
       'soil_moisture_setpoint': ('soil_moisture', ...),
       'fan_day_duty':           ('fan_day_duty', ...),
       'fan_night_duty':         ('fan_night_duty', ...),
   }
   ```

2. **routes.py - _L2_TO_L3_PARAM_MAP** (line ~1054):
   ```python
   _L2_TO_L3_PARAM_MAP = {
       'Light':            'light_setpoint',
       'Soil EC':          'soil_ec_setpoint',             # NEW
       'Soil Moisture':    'soil_moisture_setpoint',
   }
   ```

3. **routes.py - APPROVE logic** (line ~1172):
   When APPROVE decision has empty proposed_modifications:
   - Fetch Layer 2 recommendation
   - Extract its 'changes' array
   - Convert using _L2_TO_L3_PARAM_MAP (now includes Soil EC)
   - Apply all changes via GH_Setpoints setters
   - Save previous_values and approved_values

## Success Criteria
✅ Soil EC changes from 1000 → 900
✅ Soil Moisture changes from 48 → 45
✅ Both values persist in MongoDB
✅ Both values show in approved_values document
✅ Both values show in previous_values document
