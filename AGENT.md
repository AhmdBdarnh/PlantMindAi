# PlantMind AI — Agent Guide

## What This Project Is

A fully autonomous IoT greenhouse system for growing lettuce. A Raspberry Pi 5 runs the backend (Flask + Python), controls hardware through an ESP32 over I2C, reads sensors, and serves a React frontend dashboard. The system keeps temperature, light, soil moisture, EC, and pH within research-based optimal ranges — either autonomously via PID/hysteresis loops or manually from the dashboard.

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

## Architecture

```
React Frontend (port 3000)
        │  HTTP REST
        ▼
Flask Backend (port 5000)  ──►  MongoDB Atlas  (sensor history, setpoints, resources)
        │                   ──►  HiveMQ MQTT    (telemetry publish/subscribe)
        │                   ──►  AWS S3         (plant images)
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
| `Backend/control_loops.py` | PID and hysteresis control loop thread functions |
| `Backend/setpoints.py` | Setpoint storage, MongoDB persistence, operation mode |
| `Backend/app_loop.py` | 10s sensor polling, 1s actuator logging, resource accumulation |
| `Backend/routes.py` | All Flask REST API routes |
| `Backend/actuator_helpers.py` | Manual-mode actuator apply helper |
| `Backend/mongo_db_handler.py` | MongoDB wrapper |
| `Backend/mqtt_handler.py` | MQTT publish/subscribe wrapper |
| `Backend/serial_logger.py` | Terminal display of live sensor/actuator data |
| `Backend/Sensors/sensors.py` | Sensor facade — delegates to sub-drivers |
| `Backend/Sensors/water.py` | YF-S201 flow sensor, pulse counting, volume accumulation |
| `Backend/Actuators/actuators.py` | ESP32 I2C actuator commands |

---

## Hardware

### Raspberry Pi 5 GPIO
| Pin | Device |
|---|---|
| GPIO 26 | DHT22 (air temp + humidity) |
| GPIO 12 | Water flow sensor (YF-S201) |
| GPIO 16 | Fertilizer flow sensor (YF-S201) |
| I2C (SDA/SCL) | ADS1115, ESP32 (0x30), VEML7700 |
| UART /dev/ttyAMA0 | RS485 7-in-1 soil sensor (pH, EC, moisture, temp, NPK) |
| UART /dev/ttyAMA1 | PZEM-004T power meter |

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

Duty cycle range: **0–4095** for all actuators.

---

## Operation Modes

### Manual
- Control loops are paused (`threading.Event.clear()`)
- All actuators stopped immediately
- Frontend sliders/buttons directly command actuators via REST API
- `actuator_helpers.set_actuators_manual_values()` applies MQTT-commanded values every 1s

### Autonomous
- All four control loop threads are unpaused (`threading.Event.set()`)
- PID and hysteresis loops run continuously
- Manual REST commands are overridden by the loops within one cycle
- **Always starts in manual mode on boot** regardless of what was saved in MongoDB

---

## Control Loops

### Temperature (`control_loops.py: temperature_sp_adjustment_task`)
- PID: KP=1034.05, KI=1.52, KD=0.0, deadband=1.0°C
- Positive output → heater ON
- Negative output → cooling fan ON
- Zero (within deadband) → all OFF
- Sample time: 10s

### Light (`control_loops.py: light_sp_adjustment_task`)
- PID: KP=20, KI=7.5, KD=0.1
- Controls both LED strips together
- Sample time: 0.1s — **holds I2C bus constantly**

### Soil Moisture (`control_loops.py: set_soil_moisture_setpoint_task`)
- Hysteresis control: fires when moisture ≤ (setpoint − hysteresis)
- Water pump: DC=1800, pulse=1s, then waits 10 minutes to absorb
- **Pauses light loop** before firing (I2C bus contention fix)
- Check interval: 30s

### Fertilizer (`control_loops.py: fertilizer_pump_control_task`)
- EC-based control, checks every 60s
- EC < 1200 µS/cm → fire 1s pulse at DC=2662, wait 6 min to mix
- EC 1200–1800 → OK, no action; if pH > 6.8 → log warning
- EC ≥ 1800 → pump OFF, fire 2s water pulse to dilute
- EC ≥ 2000 → DANGER, pump LOCKED OFF, fire 2s water pulse
- pH is a warning only — does NOT block fertilization

---

## Setpoints (lettuce defaults)

| Parameter | Default | MongoDB key |
|---|---|---|
| Air temperature | 21.0°C | temperature |
| Air humidity | 68% | humidity |
| Light intensity | 600 lux | light |
| Soil pH | 6.3 | soil_ph |
| Soil EC | 1300 µS/cm | soil_ec |
| Soil temperature | 21.0°C | soil_temp |
| Soil moisture | 70% | soil_moisture |
| Soil hysteresis | 10% | soil_hysteresis |
| Water flow | 2.0 L/h | water_flow |
| Fertilizer flow | 0.5 L/h | fertilizer_flow |

Setpoints are loaded from MongoDB on startup and saved immediately when changed.

---

## Resource Tracking

Water and fertilizer volumes are tracked via two independent `WaterFlowSensor` instances:
- Water sensor → MongoDB key `"water_amount"`
- Fertilizer sensor → MongoDB key `"fertilizer_amount"`
- Both save every **1 second** to MongoDB

`app_loop.py` accumulates delta-based totals in `_total_water_liters`, `_total_fertilizer_liters`, `_total_energy_wh` — these survive periodic sensor resets and restarts. `routes.py` reads from these accumulated totals (not raw sensor counters) for the `/api/sensors` response.

Resource costs are computed from these totals using price constants in `config.py`.

---

## MongoDB Collections

| Collection | Contents |
|---|---|
| `sensors_data` | Time-series sensor readings (inserted every 10s) |
| `actuators_data` | Actuator state changes (upserted on change) |
| `resources` | Live resource totals (upserted every 10s) |
| `setpoints` | Single document `_id: "greenhouse_setpoints"` |
| `system_state` | Key-value store for persisting totals across restarts |
| `pump_logs` | Log of every pump activation (type, duration, DC, flow rate) |
| `plant_images` | Metadata for plant photos stored in AWS S3 |

---

## REST API

### Sensors
- `GET /api/sensors` — all sensor readings + resource totals + costs

### Actuators
- `GET /api/actuators` — current duty cycles for all actuators
- `POST /api/actuators/heater` — `{"duty_cycle": 0-4095}` or `{"state": "on"/"off"}`
- `POST /api/actuators/light` — same
- `POST /api/actuators/fan` — same
- `POST /api/actuators/water_pump` — same
- `POST /api/actuators/fertilizer_pump` — same

### Operation Mode
- `GET /api/operation_mode` — `{"mode": "manual"/"autonomous"}`
- `POST /api/operation_mode` — `{"mode": "manual"/"autonomous"}`

### Setpoints
- `GET /api/setpoints` — all current setpoints
- `POST /api/setpoints` — update one or more setpoints

### Camera / Plant
- `GET /api/sessions` — list of captured plant image sessions
- `POST /api/capture` — trigger manual photo capture
- `GET /api/plant_health` — latest plant health assessment

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

All threads are daemons except the main control threads which are joined at the end of `app.py`.

| Thread | Function | Interval |
|---|---|---|
| flask_thread | HTTP server | event-driven |
| serial_logger_thread | Terminal display | 1s |
| temperature_thread | Temp PID loop | 10s |
| light_thread | Light PID loop | 0.1s |
| soil_thread | Moisture hysteresis | 30s / 600s |
| fertilizer_thread | EC-based fertilization | 60s / 360s |
| app_thread | Sensor polling + MQTT + DB | 10s sensors / 1s actuators |
| daily_capture_thread | Plant photo at 14:00 | daily |

### Semaphores and Events
- `temperature_semaphore` — protects DHT22 reads
- `light_semaphore` — protects ADS1115 light channel reads
- `soil_semaphore` — protects RS485 soil sensor reads
- `electricity_semaphore` — protects PZEM-004T reads
- `water_flow_semaphore` — protects flow sensor reads
- `temperature_pause_event` — pauses/resumes temperature loop
- `light_pause_event` — pauses/resumes light loop (also paused when pump fires)
- `soil_pause_event` — pauses/resumes moisture loop
- `fertilizer_pause_event` — pauses/resumes fertilizer loop

---

## Important Behaviours to Know

**I2C bus contention**: The light PID loop runs every 100ms and holds the I2C bus. Before any pump fires, `light_pause_event.clear()` must be called with a 0.2s sleep, then `light_pause_event.set()` after. The soil moisture loop already does this. The fertilizer dilution water pulse also does this.

**Startup sequence**: ESP32 is reset first, then 10s wait for it to boot, then all PWM channels are configured with 1-5s delays between each. Do not shorten these delays.

**Manual mode on startup**: `setpoints.py` always forces `operation_mode = 'manual'` after loading from MongoDB, preventing actuators from firing immediately on restart.

**Sensor resets**: `app_loop.py` resets the hardware sensor counters every N hours (config: `RESOURCES_CONSUMPTION_LOG_AND_RESET_INTERVAL`). The delta accumulation logic handles this — running totals in `_total_*` are never reset.

**Flow sensor pulse counting**: YF-S201 generates pulses at 7.5 Hz per L/min. Volume is computed as `flow_rate / 60.0` added every second. If the GPIO pin fails to initialize (OSError), the sensor thread never starts — volume stays at whatever was last saved in MongoDB.
