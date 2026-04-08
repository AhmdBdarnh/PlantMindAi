# PlantMind AI — Backend Structure

## How to run

```bash
venv/bin/python3 app.py
```

> **Always use `venv`** (not `envGreenHouse`). `venv` has gpiod v2 which the code requires.

---

## File map

```
Backend/
├── app.py                  # Entry point — init only, no business logic
├── config.py               # All constants (pins, intervals, credentials)
├── actuator_helpers.py     # set_all_light_strip_dc / set_all_heater_dc / set_actuators_manual_values
├── control_loops.py        # PID & hysteresis thread functions (temperature, light, soil)
├── capture_manager.py      # Camera capture cycles + Plant.id health checks
├── app_loop.py             # Main sensor-poll / actuator-log background loop
├── routes.py               # All Flask routes (Blueprint factory)
│
├── Sensors/                # Hardware sensor drivers
│   ├── sensors.py          # GH_Sensors — aggregates all sensors
│   └── water.py            # WaterFlowSensor (gpiod v2)
│
├── Actuators/
│   └── actuators.py        # GH_Actuators — ESP32 PWM over I2C
│
├── mqtt_handler.py         # HiveMQ cloud MQTT client
├── mongo_db_handler.py     # MongoDB Atlas helper
├── aws_s3_handler.py       # AWS S3 upload / presigned URL
├── rpi_camera.py           # Multi-camera capture & live-frame grabber
├── setpoints.py            # GH_Setpoints — thread-safe setpoint store
├── plant_health.py         # Plant.id v3 API wrapper
├── serial_logger.py        # Serial log thread (prints sensor state periodically)
├── ph_pump_handler.py      # PHPumpHandler — GPIO relay for pH dosing pump
│
├── utils/
│   └── utils.py            # _CUSTOM_PRINT_FUNC, set_serial_log_enabled
│
└── tests/                  # Standalone hardware test scripts
    ├── test_water_sensor.py           # Test water flow sensor on GPIO 12
    ├── test_water_pump_and_sensor.py  # Pump ON via I2C + sensor read
    └── ...                            # Other test scripts
```

---

## Module responsibilities

### `app.py`
- Loads `.env`, instantiates all hardware objects and services.
- Calls `module.init(...)` for each module that needs shared state.
- Creates and starts all background threads.
- Registers Flask routes via `routes.init_routes(...)`.
- **No business logic lives here.**

### `config.py`
- Single source of truth for every constant: timing intervals, GPIO pins,
  ADS1115 calibration, ESP32 address, MQTT credentials, MongoDB URI, S3 bucket.
- Change a value here and it takes effect everywhere.

### `actuator_helpers.py`
- `init(env_actuators)` — call once at startup.
- `set_all_light_strip_dc(duty_cycle)` — sets both light strips atomically.
- `set_all_heater_dc(duty_cycle)` — sets heater + heater fan atomically.
- `set_actuators_manual_values()` — detects MQTT-commanded changes and pushes
  them to hardware (delta-based, runs every second in `app_loop`).

### `control_loops.py`
- `temperature_sp_adjustment_task(...)` — bidirectional PID (heating / cooling).
- `light_sp_adjustment_task(...)` — PID to maintain target lux.
- `set_soil_moisture_setpoint_task(...)` — hysteresis irrigation controller.
- All three are pure functions; dependencies are passed as arguments.
- Each function loops forever and is meant to run in its own thread.

### `capture_manager.py`
- `init(camera, s3_handler, mongo_db_handler, plant_health_checker, env_actuators, setpoints, light_pause_event)` — call once.
- `run_full_capture_cycle(triggered_by, run_health_check)` — flash lights,
  capture from all cameras, upload to S3 in parallel, save session to MongoDB,
  kick off Plant.id health check in a background thread.
- `camera_capture_task(capture_interval, health_check_interval)` — scheduler thread target.
- `last_health_result` — module-level variable; updated after each health check.
  Read by `/api/plant_health GET`.
- `_capture_running_lock` — exported so routes can peek without acquiring.

### `app_loop.py`
- `init(...)` — call once.
- `app_task()` — the main background loop (runs in its own thread):
  - Reads all sensors every 10 s, publishes to MQTT and MongoDB.
  - Logs and resets resource counters (energy, water) every N hours.
  - Calls `actuator_helpers.set_actuators_manual_values()` every 1 s.
  - Publishes actuator state changes to MQTT and MongoDB.
- `get_last_sensor_update()` — returns last update timestamp string.
- `_sensor_cache` / `_sensor_cache_lock` — populated each sensor cycle.

### `routes.py`
- `init_routes(app, ...)` — registers a Flask Blueprint with all routes and
  returns it. All dependencies injected; no module-level hardware imports.
- **Sensor routes:** `GET /api/sensors`, `GET /api/actuators`
- **Control routes:** `POST /api/actuators/{heater,light,fan,water_pump,ph_pump}`
- **Mode / setpoints:** `GET|POST /api/operation_mode`, `GET|POST /api/setpoints`
- **Health:** `GET|POST /api/plant_health`
- **Capture:** `GET|POST /api/capture_sessions`, `GET|POST /api/capture_images` (legacy)
- **Camera streams:** `/video_c1`, `/video_c2`, `/video_c3`, `/api/frame/<id>`

---

## Threading model

| Thread | Target | Purpose |
|---|---|---|
| `flask_thread` | `run_flask()` | Flask HTTP server (daemon) |
| `temperature_thread` | `control_loops.temperature_sp_adjustment_task` | Temp PID |
| `light_thread` | `control_loops.light_sp_adjustment_task` | Light PID |
| `soil_thread` *(disabled)* | `control_loops.set_soil_moisture_setpoint_task` | Irrigation |
| `app_thread` | `app_loop.app_task` | Sensor polling & MQTT/DB logging |
| `capture_thread` | `capture_manager.camera_capture_task` | Scheduled photo + health (daemon) |
| `serial_logger_thread` | `serial_logger_task` | Console status logger |

---

## Dependency injection pattern

1. Hardware objects are created in `app.py` and passed down — no circular imports.
2. Modules that need many shared objects use a module-level `init()` function
   (actuator_helpers, capture_manager, app_loop).
3. Control loop functions take all deps as arguments (pure functions, easy to test).
4. Routes receive deps through the `init_routes()` factory closure.

---

## Standalone test scripts

| Script | What it tests | How to run |
|---|---|---|
| `tests/test_water_sensor.py` | Water flow sensor pulses on GPIO 12 | `venv/bin/python3 tests/test_water_sensor.py` |
| `tests/test_water_pump_and_sensor.py` | ESP32 pump init + flow sensor read together | `venv/bin/python3 tests/test_water_pump_and_sensor.py` |

> Stop the backend before running standalone tests (both need GPIO 12 and I2C).
