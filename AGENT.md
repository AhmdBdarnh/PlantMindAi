# PlantMind AI — Agent Guide

## What This Project Is

A fully autonomous IoT greenhouse system for growing lettuce. A Raspberry Pi 5 runs the backend (Flask + Python), controls hardware through an ESP32 over I2C, reads sensors, and serves a React frontend dashboard. The system keeps temperature, light, soil moisture, EC, and pH within research-based optimal ranges through a three-layer AI decision architecture.

---

## How to Run

```bash
# Backend (Terminal 1)
cd Backend
./venv/bin/python app.py

# Frontend (Terminal 2)
cd Frontend
npm start
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:5000

---

## Three-Layer AI Architecture

```
Layer 1 — Control Loops (real-time, automatic)
  │  PID + hysteresis loops in control_loops.py
  │  Temperature, light, soil moisture, fertilizer, fan schedule
  ▼
Layer 2 — AI Setpoint Advisor (daily, human-approved)
  │  ai_setpoint_advisor.py  ←  GPT model (OPENAI_MODEL env var)
  │  Fires daily at 15:30, collects sensor/health/growth data → GPT → saves to DB
  │  Status: pending / needs_manual_review / invalid
  │  Auto-triggers Layer 3 immediately after
  ▼
Layer 3 — Budget Manager (automatic, human-approved)
     layer3_budget_manager.py
     Budget gate only: compares today's water/electricity/fertilizer costs vs budget_config
     BLOCK preconditions: no Layer 2 rec / rec invalid / rec older than 48h (LAYER2_MAX_AGE_HOURS)
     Decisions: APPROVE / MODIFY / BLOCK / ALERT_ONLY
     Decision engine: AI-powered when LAYER3_USE_AI=true (default), else rule-based
     All changes require explicit user approval via frontend
```

**Critical rule**: Layer 3 NEVER fires actuators. Layer 3 NEVER changes pump power or pulse durations. It only writes a decision document to MongoDB. All setpoint changes require human "Approve" in the dashboard.

---

## Architecture Diagram

```
React Frontend (port 3000)
        │  HTTP REST
        ▼
Flask Backend (port 5000)  ──►  MongoDB Atlas  (sensor history, setpoints, resources, AI recs)
        │                   ──►  HiveMQ MQTT    (telemetry publish/subscribe)
        │                   ──►  AWS S3         (plant images, growth outputs)
        │                   ──►  OpenAI API     (Layer 2 AI advisor)
        │                   ──►  Telegram       (alerts and notifications)
        │
   I2C (0x30)
        │
      ESP32  ──► PWM actuators (heater, fans, lights, pumps)
        │
   Sensors (GPIO / I2C / UART / ADS1115)
```

---

## Key Files

| File | Purpose |
|---|---|
| `Backend/app.py` | Entry point — wires all modules, starts threads |
| `Backend/config.py` | All constants: pins, credentials, price constants |
| `Backend/control_loops.py` | Layer 1: PID and hysteresis control loops + fan schedule |
| `Backend/setpoints.py` | Setpoint storage, MongoDB persistence, operation mode |
| `Backend/app_loop.py` | 5s sensor polling, 1s actuator logging, resource accumulation |
| `Backend/routes.py` | All Flask REST API routes (Blueprint) |
| `Backend/actuator_helpers.py` | Manual-mode actuator apply helper |
| `Backend/mongo_db_handler.py` | MongoDB wrapper for all collections |
| `Backend/mqtt_handler.py` | MQTT publish/subscribe wrapper |
| `Backend/serial_logger.py` | Terminal display of live sensor/actuator data |
| `Backend/capture_manager.py` | Camera capture, S3 upload, Plant.id health check |
| `Backend/rpi_camera.py` | GH_Camera — 3 persistent USB grabbers + MJPEG streams |
| `Backend/plant_health.py` | PlantHealthChecker — Plant.id v3 API |
| `Backend/growth_metrics.py` | Layer: wraps plant-growth-calculator, S3 images → metrics → DB |
| `Backend/ai_setpoint_advisor.py` | Layer 2: GPT-powered setpoint recommendation engine |
| `Backend/layer3_budget_manager.py` | Layer 3: Sensor Safety + Plant Health + Budget gates |
| `Backend/telegram_alerts.py` | Telegram alert helper (sensor errors, EC danger, pH warnings) |
| `Backend/Sensors/sensors.py` | Sensor facade — delegates to sub-drivers |
| `Backend/Actuators/actuators.py` | ESP32 I2C actuator commands (PWM frames) |
| `plant-growth-calculator/` | Teammate's repo — segmentation + measurement pipeline |

---

## Hardware

### Raspberry Pi 5 GPIO
| Pin | Device |
|---|---|
| GPIO 26 | DHT22 (air temp + humidity) |
| GPIO 12 | Water flow sensor (YF-S201) |
| GPIO 16 | Fertilizer flow sensor (YF-S201) |
| I2C (SDA/SCL) | ADS1115 (light + soil moisture), ESP32 (0x30) |
| UART /dev/ttyAMA0 | RS485 7-in-1 soil sensor (pH, EC, moisture, temp, NPK) |
| UART /dev/ttyAMA1 | PZEM-004T power meter |

### Cameras
| Device | ID used in code |
|---|---|
| /dev/video2 — 2K USB | camera_id=1 |
| /dev/video4 — 4K USB | camera_id=2 |
| /dev/video0 — integrated | camera_id=4 |

### ESP32 PWM Channels (I2C address 0x30)
| Actuator | Pin | Channel | Frequency |
|---|---|---|---|
| Light strip 1 | 16 | 0 | 5000 Hz |
| Light strip 2 | 15 | 5 | 5000 Hz |
| Heater | 17 | 1 | 50 Hz |
| Heater fan | 18 | 2 | 5000 Hz |
| Cooling fan | 19 | 3 | 5000 Hz |
| Water pump | 33 | 4 | 1000 Hz |
| Fertilizer pump | 25 | 6 | 1000 Hz |

Duty cycle range: **0–4095** for all actuators (12-bit PWM).

---

## Operation Modes

### Manual
- Control loops are paused (`threading.Event.clear()`)
- All actuators stopped immediately on switch
- Frontend sliders/buttons directly command actuators via REST API
- `actuator_helpers.set_actuators_manual_values()` applies MQTT-commanded values every 1s
- Fan schedule also pauses in manual mode — fan is NOT touched

### Autonomous
- All four control loop threads are unpaused (`threading.Event.set()`)
- PID and hysteresis loops run continuously
- Manual REST commands are overridden by the loops within one cycle
- **Startup: operation mode is RESTORED from MongoDB** (not forced to manual)

---

## Control Loops (Layer 1)

### Temperature (`temperature_sp_adjustment_task`)
- PID: KP=1034.05, KI=1.52, KD=0.0, deadband=1.0°C
- Positive output → heater + heater_fan ON
- Negative output → cooling fan ON (skipped if `FAN_SCHEDULE_ENABLED`)
- Zero (within deadband) → all OFF
- Sample time: 10s

### Light (`light_sp_adjustment_task`)
- PID: KP=20, KI=7.5, KD=0.1
- Controls both LED strips together
- Resets PID on setpoint change; strips off if setpoint=0
- Sample time: 1.0s
- In manual mode: wakes up but does nothing (returns immediately)

### Fan Schedule (`fan_schedule_task`)
- `FAN_SCHEDULE_ENABLED = False` — **currently DISABLED**. The cooling fan is controlled
  by the temperature PID. The schedule thread only starts when this flag is True.
- When enabled: Day (06:00–20:00) duty from `setpoints.get_fan_day_duty()`, fallback 4095 (100%);
  Night (20:00–06:00) duty from `setpoints.get_fan_night_duty()`, fallback 1024 (25%); 60s check interval;
  overrides the temperature PID fan control; paused in manual mode.
- ⚠️ Because the schedule is disabled, Layer 3 fan modifications are also disabled
  (`LAYER3_ALLOW_FAN_MODS = False`) so no inert fan changes can be proposed or approved.

### Soil Moisture (`set_soil_moisture_setpoint_task`)
- Graduated pulse irrigation based on live setpoints
- Bands (computed from `moisture_target` and `hysteresis` every cycle):
  - `moisture >= target` → OFF
  - `target-H <= moisture < target` → OFF (acceptable)
  - `target-H-5 <= moisture < target-H` → 1s pulse
  - `target-H-10 <= moisture < target-H-5` → 1.5s pulse
  - `moisture < target-H-10` → 2s pulse + Telegram CRITICAL alert
- High-moisture alert at absolute 75% (always active)
- After any pulse: `ABSORB_WAIT_SEC = 10800` (3h)
- Check interval: 30s
- Hard cap: `MAX_PUMP_SEC = 3` — a single pulse can never exceed 3s
- Settle guard: after a manual→auto switch, 2 valid reads required before the pump may fire
- Safety: RS485 None/NaN/0/≤5% = sensor error → pump blocked
- Safety: 3 consecutive bad reads → 1h pump lock + Telegram alert
- Pauses light loop before firing (I2C bus contention fix)
- Pump blocked until first valid sensor read after mode switch

### Fertilizer (`fertilizer_pump_control_task`)
- EC-based graduated pulses from live EC setpoint
- EC bands (computed each cycle from `ec_target = setpoints.get_soil_ec_setpoint()`):
  - `EC >= 2000` → DANGER: pump OFF, water dilution pulse, Telegram DANGER
  - `EC >= 1600` → Too high: pump OFF, Telegram WARNING
  - `EC > 1000` → Above safe range: pump OFF, Telegram WARNING
  - `EC >= ec_target` → At/above target: pump OFF
  - `ec_target-200 <= EC < ec_target` → Acceptable: pump OFF
  - `ec_target-400 <= EC < ec_target-200` → Low: 1s pulse
  - `EC < ec_target-400` → Very low: 1.5s pulse
  - `EC < 550` → Telegram WARNING "EC low" (fires alongside pump)
- After any pulse: `SETTLE_WAIT_SEC = 18000` (5h)
- Check interval: 3600s (1h)
- Hard cap: `MAX_PULSE_SEC = 2` — a single fertilizer pulse can never exceed 2s
- pH: warning-only — does NOT block fertilization
- pH thresholds: PH_CRITICAL_LOW=4.8, PH_LOW_WARN=5.2, PH_HIGH_WARN=7.5
- EC validity range: 50–9000 µS/cm; invalid EC → pump locked
- Absolute EC thresholds (2000/1600/1000/550) are independent of the setpoint — they always apply
- Safety: same 3-failure lock + manual→auto settle guard as moisture loop

---

## Setpoints (lettuce defaults)

| Parameter | Default | MongoDB key |
|---|---|---|
| Air temperature | 21.0°C | temperature |
| Air humidity | 68% | humidity |
| Light intensity | 600 | light |
| Soil pH | 6.3 | soil_ph |
| Soil EC | 850 µS/cm | soil_ec |
| Soil temperature | 21.0°C | soil_temp |
| Soil moisture | 50% | soil_moisture |
| Soil hysteresis | 10% | soil_hysteresis |
| Water flow | 2.0 L/h | water_flow |
| Fertilizer flow | 0.5 L/h | fertilizer_flow |
| Fan day duty | 4095 (100%) | fan_day_duty |
| Fan night duty | 1024 (25%) | fan_night_duty |

Setpoints are loaded from MongoDB on startup and saved immediately when changed.

**AI-locked setpoints** (Layer 2 can never change): Water Flow, Fertilizer Flow, Operation Mode.

---

## Layer 2 — AI Setpoint Advisor

**Daily schedule**: fires at 15:30 via `daily_ai_advisor_thread`.

**Pipeline**:
1. Collect context: current setpoints, sensor cache, 24h sensor stats from MongoDB, latest two plant-health records, latest + previous growth measurement + trend, actuator states, pump history, resource totals, and data-age notes
2. Build structured text prompt with 8 sections
3. Call GPT (model from `OPENAI_MODEL` env var, default `gpt-4o`)
4. Validate response against `SAFETY_LIMITS` (max change per parameter, hard reject limits)
5. Save `ai_setpoint_recommendations` document (status: `pending` / `needs_manual_review` / `invalid`)
6. Auto-trigger Layer 3 in background thread
7. Send Telegram notification

**Safety limits** (`SAFETY_LIMITS`, per recommendation). `max_change` exceeded → needs manual review;
`reject_above` exceeded → hard rejected; values between trigger a clamp + review:
| Parameter | Max change | Hard reject above |
|---|---|---|
| Temperature | *(no per-recommendation limit — AI may set any value)* | — |
| Humidity | ±5% | ±10% |
| Light | ±100 units | ±300 units |
| Soil pH | ±0.2 | ±0.3 |
| Soil EC | ±100 µS/cm | ±200 µS/cm |
| Soil Temp | ±1.0°C | ±2.0°C |
| Soil Moisture | ±10% | ±15% |
| Soil Hysteresis | ±2% (always needs review) | ±5% |

**Rate limit**: `AI_MAX_CALLS_PER_DAY` (default 3) — resets at midnight.

**Human actions**: Send to Budget Manager (frontend → `POST /api/layer3/run`) or Reject (`POST /api/ai-advisor/<rec_id>/reject`, marks the recommendation rejected — no setpoint change). Layer 2 has **no apply action** — approval and the live setpoint update happen only in Layer 3. `POST /api/ai-advisor/<rec_id>/approve` is kept for backward compatibility but now only forwards to Layer 3.

---

## Layer 3 — Budget Manager

**Auto-triggered** by Layer 2 immediately after saving a recommendation (fire-and-forget background thread — Layer 2 never waits on it). Also triggerable manually via `POST /api/layer3/run`.

**This is a budget gate only** — there is no separate sensor-safety or plant-health gate in the decision engine. `gate_results` contains only `budget`. Sensor safety is enforced entirely by Layer 1; plant health/growth is consumed by Layer 2.

**Budget evaluation** (`_run_budget_gate`): compares today's costs (water + electricity + fertilizer, from `get_today_costs`) against `budget_config`. Status = worst of the total check and each per-resource check:
- `usage_pct < warning_threshold_pct` → **ok**
- `warning_threshold_pct ≤ usage_pct ≤ 100` → **warning**
- `usage_pct > 100` → **over_budget**

**Decision flow** (`_make_decision`, rule-based; `_ai_make_decision` when `LAYER3_USE_AI=true`):
1. No Layer 2 recommendation found → **BLOCK**
2. Layer 2 recommendation `status == invalid` → **BLOCK**
3. Layer 2 recommendation older than `LAYER2_MAX_AGE_HOURS` (48h) → **BLOCK**
4. Budget **ok** → **APPROVE** (apply Layer 2 as-is)
5. Budget **warning** / **over_budget** → **MODIFY** (propose cost-saving cuts)
6. Budget pressure but no safe modifications available → **ALERT_ONLY**

**Proposed modifications** (`_build_proposed_modifications`, cost-saving only, never pump power/pulse):
- LED setpoint reduction (electricity driver) — never below `LED_POWER_MIN_PCT` (40%) of current
- Soil moisture target reduction (water driver) — never below `MOISTURE_SETPOINT_FLOOR` (35%)
- Reduction scale: WARNING → 15%, OVER_BUDGET → 25%
- ⚠️ Night-fan-duty reduction is **disabled** via `LAYER3_ALLOW_FAN_MODS = False` (the fan is PID-controlled,
  so a Layer 3 fan change has no runtime effect). Re-enable only together with the fan schedule.

**Final decisions**:
| Decision | Meaning | Approve button |
|---|---|---|
| APPROVE | Within budget — apply Layer 2 recommendation as-is | Enabled |
| MODIFY | Budget pressure — apply Layer 2 plus cost-saving cuts | Enabled |
| BLOCK | No / invalid / stale (>48h) Layer 2 recommendation — nothing to apply | **Disabled** |
| ALERT_ONLY | Budget pressure but no safe cuts possible — informational only | Enabled (acknowledge only) |

**Human actions**: `POST /api/layer3/approve` or `POST /api/layer3/reject`. Approve applies the supported setpoint changes via `GH_Setpoints` setters and saves `runtime_constraints`; it also syncs the linked Layer 2 recommendation to `approved`.

---

## Plant Growth Analysis

**Teammate's code**: `plant-growth-calculator/` — computer-vision pipeline.
**CAM_CALIBRATION in `plant-growth-calculator/functions.py` must NEVER be changed.**

**Camera mapping** (project cam_id → growth calc name):
- camera_id=1 → cam1 (side view)
- camera_id=2 → cam2 (front view)
- camera_id=4 → cam3 (top-down)

**Daily schedule**:
- 14:10 — `daily_growth_capture_task` captures photos → `s3://growth_capture_input/`
- 14:15 — `_daily_growth_task` runs `growth_metrics.run_from_s3(prefix='growth_capture_input/')`

**Metrics saved** per measurement: area_cm2, height_cm, width_cm, depth_cm, canopy_area_cm2, volume_cm3, AGR, RGR, growth%, vol_growth%, growth_chart_s3_key, detection images.

**S3 prefix**: `AWS_S3_GROWTH_PREFIX` env var (default: `growth_capture_input/`). Health-check captures go to `captures/` — separate prefixes, never mixed.

---

## Daily Capture Schedule

| Time | Thread | What happens |
|---|---|---|
| 14:00 | `daily_capture_thread` | Full capture → `s3://captures/` + PlantID health check |
| 14:10 | `daily_growth_capture_thread` | Capture → `s3://growth_capture_input/` (no health check) |
| 14:15 | `daily_growth_thread` | Growth analysis from `growth_capture_input/` |
| 15:30 | `daily_ai_advisor_thread` | AI Setpoint Advisor → Layer 3 auto-trigger |

---

## Resource Tracking

Water and fertilizer volumes tracked via two `WaterFlowSensor` instances (YF-S201, 7.5 Hz per L/min).

`app_loop.py` accumulates delta-based totals in `_total_water_liters`, `_total_fertilizer_liters`, `_total_energy_wh` — **these are never reset** on hardware sensor resets.

`routes.py` reads these accumulated totals (not raw counters) for `/api/sensors`.

### New Plant Cycle Reset
Two endpoints:
- `POST /api/new-plant-cycle` — **safe reset**: zeros counters only, preserves ALL historical data. Cancels pending Layer 3 decisions. Resets daily cost baseline.
- `POST /api/reset_resources` — **hard reset**: zeros counters + wipes `sensors_data`, `actuators_data`, `resources`, `pump_logs`, `plant_images`. Cancels Layer 3. Use with caution.

---

## MongoDB Collections

| Collection | Contents |
|---|---|
| `sensors_data` | Time-series sensor readings (inserted every ~5s) |
| `actuators_data` | Actuator state changes (upserted on change) |
| `actuator_events` | Discrete actuator on/off events |
| `resources` | Live resource totals (upserted every ~5s) |
| `setpoints` | Single document `_id: "greenhouse_setpoints"` |
| `system_state` | Key-value store for persisting totals across restarts |
| `pump_logs` | Every pump pulse (type, duration, DC, flow rate) |
| `plant_images` / `capture_sessions` | Capture session metadata with S3 keys |
| `plant_health_results` | Plant.id v3 health check results |
| `growth_measurements` | Growth analysis outputs (area, height, AGR, RGR…) |
| `ai_setpoint_recommendations` | Layer 2 AI recommendations |
| `layer3_decisions` | Layer 3 decisions (budget gate result + final decision) |
| `layer3_status` | Latest Layer 3 run status for the dashboard |
| `budget_config` | Budget limits (daily, monthly, per-resource) |
| `daily_costs` | Daily baseline costs for budget gate |
| `runtime_constraints` | Active constraints from approved Layer 3 MODIFY decisions |
| `notifications` | In-app bell/toast notifications (workflow + alerts) |

---

## REST API

### Core
- `GET /api/health` — backend + sensor-loop health status (ok / warning / error)
- `GET /api/sensors` — sensor readings + resource totals + costs (from cache)
- `GET /api/actuators` — current duty cycles + fan schedule info
- `POST /api/actuators/heater` — `{"duty_cycle": 0-4095}` or `{"state": "on"/"off"}`
- `POST /api/actuators/light` — same
- `POST /api/actuators/fan` — same
- `POST /api/actuators/water_pump` — same
- `POST /api/actuators/fertilizer_pump` — same
- `GET/POST /api/operation_mode` — get or set `{"mode": "manual"/"autonomous"}`
- `GET/POST /api/setpoints` — get or update setpoints

### Plant Cycles
- `POST /api/new-plant-cycle` — safe counter reset (preserves history)
- `POST /api/reset_resources` — hard reset (wipes sensor collections)

### Camera / Health
- `GET /api/plant_health` — last scheduled health result (in-memory)
- `POST /api/plant_health` — trigger immediate capture + health check
- `GET /api/plant-health/latest` — latest health result from DB
- `GET /api/plant-health/history?limit=20` — health history from DB
- `GET /api/camera/status` — capture lock state
- `POST /api/capture/unlock` — force-release stuck capture lock
- `GET/POST /api/capture_sessions` — list sessions / trigger manual capture (async 202)
- `POST /api/capture_local` — save JPEG frames locally
- `POST /api/capture_local/<cam_id>` — save single camera frame locally
- `GET /api/s3/files?prefix=...` — list S3 bucket objects
- `GET /api/pump-logs?limit=50` — recent pump pulse events
- `GET /api/frame/<cam_id>` — single JPEG for polling (cam_id: 1, 2, 4)
- `GET /video_c1`, `/video_c2`, `/video_c4` — MJPEG streams

### Growth
- `GET /api/growth/latest` — most recent growth measurement
- `GET /api/growth/history?limit=50` — all growth measurements
- `POST /api/growth/run-latest-s3` — trigger analysis from latest S3 images
- `POST /api/growth/capture-and-analyze` — capture then analyze

### Layer 2 AI Advisor
- `GET /api/ai-advisor/latest` — latest recommendation + rate limit info
- `GET /api/ai-advisor/history?limit=10` — recent recommendations
- `POST /api/ai-advisor/run` — manually trigger (async, respects rate limit)
- `POST /api/ai-advisor/<rec_id>/approve` — apply recommendation
- `POST /api/ai-advisor/<rec_id>/reject` — reject with optional `{"reason": "..."}`

### Layer 3 Budget Manager
- `POST /api/layer3/run` — manually trigger Layer 3 review
- `GET /api/layer3/latest` — latest decision + current status
- `POST /api/layer3/approve` — approve (applies MODIFY changes, acknowledges ALERT_ONLY)
- `POST /api/layer3/reject` — reject
- `GET /api/layer3/history?limit=10` — recent decisions
- `GET/POST /api/layer3/budget-config` — get or update budget limits

---

## MQTT Topics

### Published (sensor data)
```
env_monitoring_system/sensors/air_temperature_C
env_monitoring_system/sensors/air_humidity
env_monitoring_system/sensors/light_intensity
env_monitoring_system/sensors/soil_ph
env_monitoring_system/sensors/soil_ec
env_monitoring_system/sensors/soil_temp
env_monitoring_system/sensors/soil_humidity
env_monitoring_system/sensors/water_flow
env_monitoring_system/sensors/fertilizer_flow
env_monitoring_system/sensors/voltage
env_monitoring_system/sensors/current
env_monitoring_system/resources/energy
env_monitoring_system/resources/water_amount
env_monitoring_system/resources/fertilizer_amount
env_monitoring_system/actuators/*/state
```

### Subscribed (commands)
```
env_monitoring_system/actuators/heater/dc
env_monitoring_system/actuators/light/dc
env_monitoring_system/actuators/water_pump/dc
env_monitoring_system/actuators/fan/dc
env_monitoring_system/actuators/fertilizer_pump/dc
loops/setpoints/temperature
loops/setpoints/light_intensity
loops/setpoints/soil_moisture
loops/setpoints/water_flow
loops/setpoints/fertilizer_flow
loops/setpoints/operation_mode
```

---

## Threading Model

| Thread | Function | Interval |
|---|---|---|
| flask_thread | HTTP server | event-driven |
| serial_logger_thread | Terminal display | 1s |
| temperature_thread | Temp PID loop | 10s |
| light_thread | Light PID loop | 1s |
| soil_thread | Moisture hysteresis | 30s / 10800s absorb |
| fertilizer_thread | EC-based fertilization | 3600s / 18000s settle |
| app_thread | Sensor polling + MQTT + DB | 5s sensors / 1s actuators |
| fan_schedule_thread | Day/night fan schedule | 60s — **only if `FAN_SCHEDULE_ENABLED` (currently False)** |
| daily_capture_thread | Plant photo at 14:00 | daily |
| daily_growth_capture_thread | Growth photos at 14:10 | daily |
| daily_growth_thread | Growth analysis at 14:15 | daily |
| daily_ai_advisor_thread | AI Advisor at 15:30 | daily |

### Semaphores and Events
- `temperature_semaphore` — protects DHT22 reads
- `light_semaphore` — protects ADS1115 light channel reads
- `soil_semaphore` — protects RS485 soil sensor reads
- `electricity_semaphore` — protects PZEM-004T reads
- `water_flow_semaphore` — protects flow sensor reads
- `temperature_pause_event` — pauses/resumes temperature loop
- `light_pause_event` — pauses/resumes light loop (also paused when any pump fires)
- `soil_pause_event` — pauses/resumes moisture loop
- `fertilizer_pause_event` — pauses/resumes fertilizer loop

---

## Important Behaviours to Know

**I2C bus contention**: The light PID loop runs every 1s and frequently uses the I2C bus. Before any pump fires, `light_pause_event.clear()` + 0.2s sleep, then `light_pause_event.set()` after. Both soil and fertilizer loops do this. Never send I2C commands without this guard.

**Control-loop supervisor**: Each Layer 1 loop runs inside `_supervised()` ([app.py](Backend/app.py)). If a loop raises an unhandled exception it forces `stop_all_actuators()` (so a crash can never leave a pump running), logs the traceback, and restarts the loop after 5s. A loop thread can never die silently.

**Startup sequence**: ESP32 restart → 10s boot wait → PWM channel init with 1–5s delays between each. Do not shorten. Pumps are explicitly set to OFF after init as a safety guarantee.

**Startup operation mode**: `app.py` restores the saved mode from MongoDB at startup. If nothing was saved, it defaults to `autonomous`.

**Process lockfile**: `/tmp/plantmind_ai.lock` prevents two instances. If a previous crash left a stale lock, it's auto-cleared if the old PID is dead.

**Sensor resets**: `app_loop.py` resets hardware sensor counters every N hours (`RESOURCES_CONSUMPTION_LOG_AND_RESET_INTERVAL`). The `_total_*` accumulators in memory are never reset — they survive this.

**Pump safety**: Each pump has a first-valid-read gate — it won't fire until at least one good sensor reading has been confirmed after mode switch to autonomous. This prevents false-dry triggers on startup.

**Fan schedule overrides temperature PID**: `FAN_SCHEDULE_ENABLED` is currently **False**, so the temperature PID owns the cooling fan. When the flag is True, the fan schedule thread owns the fan and the temperature loop never touches it.

**CAM_CALIBRATION**: The `CAM_CALIBRATION` dict in `plant-growth-calculator/functions.py` is calibrated for real camera positions. Never change it.

**S3 prefixes are separate**: Health captures → `captures/`, Growth captures → `growth_capture_input/`, Growth outputs → `growth_outputs/`. Never mix these prefixes.

**Layer 3 setpoint map**: `_L3_SETPOINT_MAP` in [routes.py](Backend/routes.py) now maps **all** setpoints — temperature, humidity, light, soil_ph, soil_ec, soil_temp, soil_moisture, soil_hysteresis, fan_day_duty, fan_night_duty — to their `GH_Setpoints` setters. On an APPROVE with no proposed modifications, the Layer 2 `changes` are converted via `_L2_TO_L3_PARAM_MAP` and applied.

**Single approval path**: `/api/layer3/approve` is the **only** path that writes live setpoints. Layer 2 cannot apply setpoints directly — `/api/ai-advisor/<rec_id>/approve` now just **forwards** the recommendation to Layer 3 (it never changes setpoints), and `apply_recommendation()` has a hard guard that always refuses. The frontend Layer 2 page reflects this: it only offers "Run Now" and "Send to Budget Manager".

**Sensor cache**: `/api/sensors` reads from `app_loop._sensor_cache` (updated every ~5s), never from hardware directly. Returns 503 if cache is empty (sensor loop still initializing).

**Serial log**: `utils/utils.py` `_CUSTOM_PRINT_FUNC` can be silenced per module. `set_serial_log_enabled(False)` suppresses output before the serial logger starts. Set `DEBUG_VERBOSE=true` in `.env` to see all werkzeug GET logs.
