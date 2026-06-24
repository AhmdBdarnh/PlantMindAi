"""
routes.py — All Flask API routes and web endpoints.

Use init_routes() to create and register a Blueprint.
The function receives every dependency the routes need so there are no
module-level imports of hardware objects.
"""
import os
import threading

import capture_manager
import actuator_helpers
import app_loop
import growth_metrics
from flask import Blueprint, Response, jsonify, render_template, request
from utils.utils import _CUSTOM_PRINT_FUNC
from config import (
    WATER_PRICE_PER_LITER_NIS,
    ELECTRICITY_PRICE_PER_KWH_NIS,
    FERTILIZER_PRICE_PER_5_LITERS_NIS,
)


def init_routes(
    app,
    env_sensors,
    env_actuators,
    setpoints,
    camera,
    s3_handler,
    mongo_db_handler,
    temperature_semaphore,
    light_semaphore,
    soil_semaphore,
    electricity_semaphore,
    water_flow_semaphore,
):
    """Register all routes on *app* and return the Blueprint."""

    bp = Blueprint('api', __name__)

    # ── Layer 3 init (runs once when routes are registered at startup) ────────
    try:
        import layer3_budget_manager
        layer3_budget_manager.init(mongo_db_handler, setpoints)
    except Exception as _l3_init_err:
        _CUSTOM_PRINT_FUNC(f"[Layer3] WARNING: init failed at startup: {_l3_init_err}")

    # ── Notifications init (UI-only; never sends email) ───────────────────────
    try:
        import notifications
        notifications.init(mongo_db_handler)
    except Exception as _ntf_init_err:
        _CUSTOM_PRINT_FUNC(f"[Notifications] WARNING: init failed at startup: {_ntf_init_err}")

    # ── Growth cycle backfill (one-time, idempotent) ──────────────────────────
    try:
        mongo_db_handler.backfill_growth_cycle_ids()
    except Exception as _bf_err:
        _CUSTOM_PRINT_FUNC(f"[Growth] WARNING: cycle backfill failed at startup: {_bf_err}")

    # ── Sensor endpoints ──────────────────────────────────────────────────────

    @bp.route('/api/sensors', methods=['GET'])
    def get_sensors():
        """
        Return sensor data from the background cache (updated every 10s by app_loop).
        Never does live hardware reads — avoids semaphore contention and hardware hangs.
        """
        try:
            with app_loop._sensor_cache_lock:
                data = dict(app_loop._sensor_cache)

            if not data:
                _CUSTOM_PRINT_FUNC("[/api/sensors] Cache empty — sensor loop still initializing")
                return jsonify({
                    'success': False,
                    'error': 'Sensor loop is initializing — please wait a few seconds',
                }), 503

            last_update = app_loop.get_last_sensor_update()

            resp = jsonify({
                'success': True,
                'last_sensor_update': last_update,
                'data': {
                    'air_temperature':       round(data.get('air_temperature', 0.0), 2),
                    'air_humidity':          round(data.get('air_humidity', 0.0), 2),
                    'light_intensity':       round(data.get('light_intensity', 0.0), 2),
                    'soil_ph':               round(data.get('soil_ph', 0.0), 2),
                    'soil_ec':               round(data.get('soil_ec', 0.0), 2),
                    'soil_humidity':         round(data.get('soil_humidity', 0.0), 2),
                    'soil_temperature':      round(data.get('soil_temperature', 0.0), 2),
                    'water_flow':            round(data.get('water_flow', 0.0), 2),
                    'water_amount':          round(data.get('water_amount', 0.0), 2),
                    'fertilizer_flow':       round(data.get('fertilizer_flow', 0.0), 2),
                    'fertilizer_amount':     round(data.get('fertilizer_amount', 0.0), 2),
                    'voltage':               round(data.get('voltage', 0.0), 2),
                    'current':               round(data.get('current', 0.0), 2),
                    'power':                 round(data.get('power', 0.0), 2),
                    'energy':                round(data.get('energy', 0.0), 2),
                    'frequency':             round(data.get('frequency', 0.0), 2),
                    'power_factor':          round(data.get('power_factor', 0.0), 2),
                    'water_cost_nis':        data.get('water_cost_nis', 0.0),
                    'electricity_cost_nis':  data.get('electricity_cost_nis', 0.0),
                    'fertilizer_cost_nis':   data.get('fertilizer_cost_nis', 0.0),
                    'total_cost_nis':        data.get('total_cost_nis', 0.0),
                },
            })
            resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
            resp.headers['Pragma']        = 'no-cache'
            resp.headers['Expires']       = '0'
            return resp
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[/api/sensors] ERROR: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    # ── Daily resource costs + cycle start date ──────────────────────────────

    @bp.route('/api/resources/daily', methods=['GET'])
    def get_resources_daily():
        """
        Return today's resource usage/costs (baseline-delta approach) and
        the timestamp of the last plant cycle reset (for 'Counting from' label).
        """
        import datetime as _dt
        try:
            daily = mongo_db_handler.get_today_costs(
                water_price_per_liter     = WATER_PRICE_PER_LITER_NIS,
                electricity_price_per_kwh = ELECTRICITY_PRICE_PER_KWH_NIS,
                fertilizer_price_per_5l   = FERTILIZER_PRICE_PER_5_LITERS_NIS,
            )
            # Serialize datetime inside daily dict
            for k, v in daily.items():
                if hasattr(v, 'isoformat'):
                    daily[k] = v.isoformat()

            cycle_raw = mongo_db_handler.get_state('cycle_started_at')

            resp = jsonify({
                'success':          True,
                'daily':            daily,
                'cycle_started_at': cycle_raw,
            })
            resp.headers['Cache-Control'] = 'no-store'
            return resp
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[/api/resources/daily] ERROR: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    # ── Resource price constants ──────────────────────────────────────────────

    @bp.route('/api/resource-prices', methods=['GET'])
    def get_resource_prices():
        """Return per-unit resource cost constants (₪) for frontend calculations."""
        return jsonify({
            'success': True,
            'prices': {
                'water_per_liter_nis':        WATER_PRICE_PER_LITER_NIS,
                'electricity_per_kwh_nis':    ELECTRICITY_PRICE_PER_KWH_NIS,
                'fertilizer_per_liter_nis':   FERTILIZER_PRICE_PER_5_LITERS_NIS / 5,
                'fertilizer_per_5liters_nis': FERTILIZER_PRICE_PER_5_LITERS_NIS,
            },
        })

    # ── Daily cost history (per-day expense graph) ────────────────────────────

    @bp.route('/api/resources/daily-history', methods=['GET'])
    def get_resources_daily_history():
        """
        Return per-day resource costs for the last N days (default 14, max 60),
        derived from the daily_costs baseline documents. Used by the Dashboard
        Expenses section's daily graph and the 'yesterday vs today' delta.

        Response shape:
          {success: true, days: 14,
           history: [{date, water_cost_nis, electricity_cost_nis,
                      fertilizer_cost_nis, total_cost_nis}, ...]}  (newest last)
        """
        try:
            days = min(int(request.args.get('days', 14)), 60)
            history = mongo_db_handler.get_daily_cost_history(
                water_price_per_liter     = WATER_PRICE_PER_LITER_NIS,
                electricity_price_per_kwh = ELECTRICITY_PRICE_PER_KWH_NIS,
                fertilizer_price_per_5l   = FERTILIZER_PRICE_PER_5_LITERS_NIS,
                days                      = days,
            )
            resp = jsonify({'success': True, 'days': days, 'history': history})
            resp.headers['Cache-Control'] = 'no-store'
            return resp
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[/api/resources/daily-history] ERROR: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    # ── Health endpoint ───────────────────────────────────────────────────────

    @bp.route('/api/health', methods=['GET'])
    def get_health():
        """Return backend + sensor-loop health status."""
        import datetime as _dt
        try:
            with app_loop._sensor_cache_lock:
                has_data = bool(app_loop._sensor_cache)
                snap     = dict(app_loop._sensor_cache) if has_data else {}

            last_update_str = app_loop.get_last_sensor_update()
            last_update     = _dt.datetime.strptime(last_update_str, '%Y-%m-%d %H:%M:%S')
            seconds_since   = round(((_dt.datetime.now() - last_update).total_seconds()))

            if not has_data or seconds_since > 600:
                status = 'error'
            elif seconds_since > 300:
                status = 'warning'
            else:
                status = 'ok'

            return jsonify({
                'status':                          status,
                'backend_alive':                   True,
                'sensor_loop_alive':               seconds_since < 90,
                'last_sensor_update':              last_update_str,
                'seconds_since_last_sensor_update': seconds_since,
                'latest_sensor_data': {
                    'temperature':  snap.get('air_temperature'),
                    'humidity':     snap.get('air_humidity'),
                    'soil_moisture': snap.get('soil_humidity'),
                    'ec':           snap.get('soil_ec'),
                    'ph':           snap.get('soil_ph'),
                },
            }), 200
        except Exception as e:
            return jsonify({
                'status':        'error',
                'backend_alive': True,
                'sensor_loop_alive': False,
                'last_error':    str(e),
            }), 200

    # ── Actuator endpoints ────────────────────────────────────────────────────

    @bp.route('/api/actuators', methods=['GET'])
    def get_actuators():
        """Get all actuator states."""
        try:
            import control_loops
            heater_dc = env_actuators.get_heater_duty_cycle()
            light_dc  = env_actuators.get_light_strip_1_duty_cycle()
            fan_dc    = env_actuators.get_fan_duty_cycle()
            pump_dc   = env_actuators.get_water_pump_duty_cycle()
            fert_dc   = env_actuators.get_fertilizer_pump_duty_cycle()

            # Fan schedule info
            now        = __import__('datetime').datetime.now()
            hour       = now.hour
            sched_on   = control_loops.FAN_SCHEDULE_TEST_ENABLED
            is_day     = control_loops.FAN_DAY_START_HOUR <= hour < control_loops.FAN_NIGHT_START_HOUR
            fan_mode   = ('Day' if is_day else 'Night') if sched_on else 'PID'

            return jsonify({
                'success': True,
                'data': {
                    'heater': {
                        'duty_cycle': heater_dc,
                        'percentage': round((heater_dc / 4095) * 100, 2),
                        'state':      'on' if heater_dc > 0 else 'off',
                    },
                    'light': {
                        'duty_cycle': light_dc,
                        'percentage': round((light_dc / 4095) * 100, 2),
                        'state':      'on' if light_dc > 0 else 'off',
                    },
                    'fan': {
                        'duty_cycle':       fan_dc,
                        'percentage':       round((fan_dc / 4095) * 100, 2),
                        'state':            'on' if fan_dc > 0 else 'off',
                        'schedule_enabled': sched_on,
                        'mode':             fan_mode,
                        'current_time':     now.strftime('%H:%M'),
                        'test_info':        '2-day fan schedule test' if sched_on else None,
                    },
                    'water_pump': {
                        'duty_cycle': pump_dc,
                        'percentage': round((pump_dc / 4095) * 100, 2),
                        'state':      'on' if pump_dc > 0 else 'off',
                    },
                    'fertilizer_pump': {
                        'duty_cycle': fert_dc,
                        'percentage': round((fert_dc / 4095) * 100, 2),
                        'state':      'on' if fert_dc > 0 else 'off',
                    },
                },
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @bp.route('/api/actuators/heater', methods=['POST'])
    def control_heater():
        """Control heater — expects {state: 'on'/'off'} or {duty_cycle: 0-4095}."""
        try:
            data = request.get_json()
            if 'state' in data:
                duty_cycle = 2048 if data['state'] == 'on' else 0
            elif 'duty_cycle' in data:
                duty_cycle = int(data['duty_cycle'])
            else:
                return jsonify({'success': False, 'error': 'Missing state or duty_cycle'}), 400

            duty_cycle = max(0, min(4095, duty_cycle))

            if not actuator_helpers.set_all_heater_dc(duty_cycle):
                return jsonify({'success': False, 'error': 'Failed to set heater'}), 500

            env_actuators.set_mqtt_dc_value_heater(duty_cycle)
            return jsonify({'success': True, 'duty_cycle': duty_cycle})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @bp.route('/api/actuators/light', methods=['POST'])
    def control_light():
        """Control light strips — expects {state: 'on'/'off'} or {duty_cycle: 0-4095}."""
        try:
            data = request.get_json()
            if 'state' in data:
                duty_cycle = 2048 if data['state'] == 'on' else 0
            elif 'duty_cycle' in data:
                duty_cycle = int(data['duty_cycle'])
            else:
                return jsonify({'success': False, 'error': 'Missing state or duty_cycle'}), 400

            duty_cycle = max(0, min(4095, duty_cycle))

            if not actuator_helpers.set_all_light_strip_dc(duty_cycle):
                return jsonify({'success': False, 'error': 'Failed to set light'}), 500

            env_actuators.set_mqtt_dc_value_light_strip(duty_cycle)
            return jsonify({'success': True, 'duty_cycle': duty_cycle})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @bp.route('/api/actuators/fan', methods=['POST'])
    def control_fan():
        """Control fan — expects {state: 'on'/'off'} or {duty_cycle: 0-4095}."""
        try:
            data = request.get_json()
            if 'state' in data:
                duty_cycle = 2048 if data['state'] == 'on' else 0
            elif 'duty_cycle' in data:
                duty_cycle = int(data['duty_cycle'])
            else:
                return jsonify({'success': False, 'error': 'Missing state or duty_cycle'}), 400

            duty_cycle = max(0, min(4095, duty_cycle))

            if not env_actuators.set_fan_duty_cycle(duty_cycle):
                return jsonify({'success': False, 'error': 'Failed to set fan'}), 500

            env_actuators.set_mqtt_dc_value_fan(duty_cycle)
            return jsonify({'success': True, 'duty_cycle': duty_cycle})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @bp.route('/api/actuators/water_pump', methods=['POST'])
    def control_water_pump():
        """Control water pump — expects {state: 'on'/'off'} or {duty_cycle: 0-4095}."""
        try:
            data = request.get_json()
            if 'state' in data:
                duty_cycle = 2048 if data['state'] == 'on' else 0
            elif 'duty_cycle' in data:
                duty_cycle = int(data['duty_cycle'])
            else:
                return jsonify({'success': False, 'error': 'Missing state or duty_cycle'}), 400

            duty_cycle = max(0, min(4095, duty_cycle))

            if not env_actuators.set_water_pump_duty_cycle(duty_cycle):
                return jsonify({'success': False, 'error': 'Failed to set water pump'}), 500

            env_actuators.set_mqtt_dc_value_water_pump(duty_cycle)
            return jsonify({'success': True, 'duty_cycle': duty_cycle})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @bp.route('/api/actuators/fertilizer_pump', methods=['POST'])
    def control_fertilizer_pump():
        """Control fertilizer pump — expects {state: 'on'/'off'} or {duty_cycle: 0-4095}."""
        try:
            data = request.get_json()
            if 'state' in data:
                duty_cycle = 2048 if data['state'] == 'on' else 0
            elif 'duty_cycle' in data:
                duty_cycle = int(data['duty_cycle'])
            else:
                return jsonify({'success': False, 'error': 'Missing state or duty_cycle'}), 400

            duty_cycle = max(0, min(4095, duty_cycle))

            if not env_actuators.set_fertilizer_pump_duty_cycle(duty_cycle):
                return jsonify({'success': False, 'error': 'Failed to set fertilizer pump'}), 500

            env_actuators.set_mqtt_dc_value_fertilizer_pump(duty_cycle)
            return jsonify({'success': True, 'duty_cycle': duty_cycle})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # ── Operation mode ────────────────────────────────────────────────────────

    @bp.route('/api/operation_mode', methods=['GET', 'POST'])
    def operation_mode():
        """Get or set operation mode (manual/autonomous)."""
        try:
            if request.method == 'GET':
                mode = setpoints.get_operation_mode()
                return jsonify({'success': True, 'mode': mode})
            data = request.get_json()
            mode = data.get('mode')
            if mode not in ['manual', 'autonomous']:
                return jsonify({'success': False, 'error': 'Invalid mode'}), 400
            setpoints.set_operation_mode(mode)
            return jsonify({'success': True, 'mode': mode})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # ── Resource reset ────────────────────────────────────────────────────────

    @bp.route('/api/new-plant-cycle', methods=['POST'])
    def new_plant_cycle():
        """
        Start a new plant cycle — reset counters only, preserve all historical data.

        Safe operations (no collection wipes):
          1. Zero in-memory resource totals + hardware flow sensor counters
          2. Persist zeros to system_state (total_water_liters etc.)
          3. Update sensor_cache so frontend sees 0 immediately
          4. Delete today's daily_costs baseline → recreated at 0 on next Budget Gate run
          5. Cancel pending Layer 3 decisions (marked cancelled, not deleted)
          6. Deactivate active runtime constraints
          7. Reset layer3_status to idle

        Preserved (untouched):
          sensors_data, pump_logs, actuators_data, resources, plant_images,
          ai_setpoint_recommendations, layer3_decisions history,
          plant_health_results, growth_measurements, capture_sessions,
          budget_config, setpoints, all hardware control loops

        Note: this writes a new cycle_started_at, which becomes the plant-cycle
        boundary. Growth analysis/history is scoped to the current cycle, so the
        new plant never reuses the previous plant's growth data or images, while
        the old measurements and images remain stored (just not used).
        """
        import datetime as _dt
        try:
            # 1. Zero counters — no collection wipes
            app_loop.reset_counters_only()

            # 2. Delete today's daily_costs baseline so get_today_costs()
            #    recreates it at 0 on the next Budget Manager load/run
            mongo_db_handler.reset_daily_costs_baseline()

            # 3. Cancel pending Layer 3 decisions from the old cycle
            cancelled = mongo_db_handler.cancel_pending_layer3_decisions()

            # 4. Deactivate runtime constraints from the old cycle
            mongo_db_handler.clear_runtime_constraints()

            # 5. Set Layer 3 status to idle / ready
            mongo_db_handler.update_layer3_status({
                'current_status':       'idle',
                'blocked_reason':       None,
                'latest_decision_id':   None,
                'budget_status':        'unknown',
                'sensor_safety_status': 'unknown',
                'plant_health_status':  'unknown',
            })

            reset_ts = _dt.datetime.now().isoformat(timespec='seconds')
            mongo_db_handler.upsert_state('cycle_started_at', reset_ts)
            _CUSTOM_PRINT_FUNC(
                f"[NewCycle] Safe plant cycle reset complete at {reset_ts}. "
                f"Cancelled {cancelled} pending Layer 3 decision(s). "
                "No historical data deleted."
            )
            return jsonify({
                'success':      True,
                'message':      'New plant cycle started. Counters reset to zero. All historical data preserved.',
                'reset_at':     reset_ts,
                'l3_cancelled': cancelled,
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @bp.route('/api/reset_resources', methods=['POST'])
    def reset_resources():
        """
        Start a new plant cycle — reset resource counters and Layer 3 state.

        What is reset:
          - In-memory resource totals (water, fertilizer, energy) → 0
          - Hardware flow sensor counters → 0
          - system_state documents (total_water_liters, etc.) → 0
          - sensor_cache cost and volume fields → 0
          - today's daily_costs baseline (deleted; recreated at 0 on next Budget Gate run)
          - sensors_data, actuators_data, resources, pump_logs, plant_images (cleared)
          - pending Layer 3 decisions → cancelled
          - active runtime_constraints → deactivated
          - layer3_status → idle

        What is NOT reset:
          - Live sensor readings (DHT22, EC, pH, etc.)
          - budget_config (daily/monthly budget limits)
          - setpoints (temperature, moisture targets, etc.)
          - Layer 1 / Layer 2 / Layer 3 logic
          - Camera calibration
          - Pump logic
          - Historical layer3_decisions (kept as history, marked cancelled if pending)
        """
        import datetime as _dt
        try:
            # 1. Zero resource counters (existing logic — zeros system_state + sensor cache)
            app_loop.reset_resources()

            # 2. Delete today's daily_costs baseline so the next Budget Gate run
            #    creates a fresh baseline at 0.  get_today_costs() will then return
            #    today_cost = 0 - 0 = 0 for all resources.
            mongo_db_handler.reset_daily_costs_baseline()

            # 3. Cancel any pending Layer 3 decisions from the previous plant cycle
            cancelled = mongo_db_handler.cancel_pending_layer3_decisions()

            # 4. Deactivate active runtime constraints (belonged to the old cycle)
            mongo_db_handler.clear_runtime_constraints()

            # 5. Reset Layer 3 status to idle
            mongo_db_handler.update_layer3_status({
                'current_status':       'idle',
                'blocked_reason':       None,
                'latest_decision_id':   None,
                'budget_status':        'unknown',
                'sensor_safety_status': 'unknown',
                'plant_health_status':  'unknown',
            })

            reset_ts = _dt.datetime.now().isoformat(timespec='seconds')
            mongo_db_handler.upsert_state('cycle_started_at', reset_ts)
            _CUSTOM_PRINT_FUNC(
                f"[NewCycle] Plant cycle reset complete at {reset_ts}. "
                f"Cancelled {cancelled} pending Layer 3 decision(s)."
            )
            return jsonify({
                'success':    True,
                'message':    'New plant cycle started. All resource counters reset to zero.',
                'reset_at':   reset_ts,
                'l3_cancelled': cancelled,
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # ── Setpoints ─────────────────────────────────────────────────────────────

    @bp.route('/api/setpoints', methods=['GET', 'POST'])
    def setpoints_api():
        """Get or update setpoints. Each change is auto-saved to MongoDB."""
        try:
            if request.method == 'GET':
                resp = jsonify({'success': True, 'setpoints': setpoints.get_all_setpoints()})
                resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
                resp.headers['Pragma']        = 'no-cache'
                return resp

            data = request.get_json()

            _map = {
                'temperature':    setpoints.set_temperature_setpoint,
                'humidity':       setpoints.set_humidity_setpoint,
                'light':          setpoints.set_light_setpoint,
                'soil_ph':        setpoints.set_soil_ph_setpoint,
                'soil_ec':        setpoints.set_soil_ec_setpoint,
                'soil_temp':      setpoints.set_soil_temp_setpoint,
                'soil_moisture':  setpoints.set_soil_humidity_setpoint,
                'soil_hysteresis':setpoints.set_soil_humidity_hysteresis,
                'water_flow':     setpoints.set_water_flow_setpoint,
            }
            for key, setter in _map.items():
                if key in data:
                    setter(float(data[key]))

            return jsonify({'success': True, 'setpoints': setpoints.get_all_setpoints()})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # ── Plant health ──────────────────────────────────────────────────────────

    @bp.route('/api/plant_health', methods=['GET'])
    def get_plant_health():
        """Return the most recent scheduled health check result."""
        if capture_manager.last_health_result is None:
            return jsonify({
                'success': False,
                'error': 'No health check has run yet.',
            }), 200
        return jsonify(capture_manager.last_health_result), 200

    @bp.route('/api/plant_health', methods=['POST'])
    def check_plant_health():
        """Trigger an immediate capture + health check and return the result."""
        try:
            session_doc = capture_manager.run_full_capture_cycle(triggered_by='health_check')
            health = session_doc.get('health')
            if health:
                return jsonify(health), 200
            return jsonify({'success': False, 'error': 'No images captured for health check'}), 500
        except Exception as e:
            if 'already in progress' in str(e):
                return jsonify({'success': False, 'error': str(e)}), 409
            return jsonify({'success': False, 'error': str(e)}), 500

    # ── Plant health from DB ──────────────────────────────────────────────────

    @bp.route('/api/plant-health/latest', methods=['GET'])
    def get_plant_health_latest_db():
        """Return the most recent plant health result saved in the database."""
        try:
            doc = mongo_db_handler.get_latest_plant_health_result()
            if not doc:
                return jsonify({'success': False, 'error': 'No health results in database yet.'}), 200
            if hasattr(doc.get('created_at'), 'isoformat'):
                doc['created_at'] = doc['created_at'].isoformat()
            return jsonify({'success': True, 'result': doc}), 200
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @bp.route('/api/plant-health/history', methods=['GET'])
    def get_plant_health_history_db():
        """Return the last N plant health results from the database."""
        try:
            limit   = min(int(request.args.get('limit', 20)), 50)
            results = mongo_db_handler.get_plant_health_history(limit)
            for r in results:
                if hasattr(r.get('created_at'), 'isoformat'):
                    r['created_at'] = r['created_at'].isoformat()
            return jsonify({'success': True, 'results': results}), 200
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @bp.route('/api/camera/status', methods=['GET'])
    def get_camera_status():
        """Return current capture lock state — used by frontend to poll while waiting."""
        status = capture_manager.get_capture_status()
        resp = jsonify(status)
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
        resp.headers['Pragma']        = 'no-cache'
        return resp, 200

    @bp.route('/api/capture/unlock', methods=['POST'])
    def force_unlock_capture():
        """Force-release the capture lock if a previous cycle got stuck."""
        try:
            if capture_manager._capture_running_lock.locked():
                capture_manager._capture_running_lock.release()
                _CUSTOM_PRINT_FUNC("[Capture] Lock force-released via API.")
                return jsonify({'success': True, 'message': 'Capture lock released.'}), 200
            return jsonify({'success': True, 'message': 'Lock was not held — nothing to release.'}), 200
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # ── Capture sessions ──────────────────────────────────────────────────────

    @bp.route('/api/capture_sessions', methods=['GET'])
    def get_capture_sessions():
        """
        Return the last N capture sessions from MongoDB.
        Fresh presigned S3 URLs (1-hour expiry) are generated for each image.
        Query param: ?limit=20 (default)
        """
        try:
            limit    = min(int(request.args.get('limit', 20)), 50)
            sessions = mongo_db_handler.get_capture_sessions(limit)
            for session in sessions:
                for img in session.get('images', []):
                    if img.get('s3_key'):
                        img['url'] = s3_handler.generate_presigned_url(
                            img['s3_key'], expiry_seconds=3600
                        )
                    else:
                        img['url'] = None
                if hasattr(session.get('timestamp'), 'isoformat'):
                    session['timestamp'] = session['timestamp'].isoformat()
            return jsonify({'success': True, 'sessions': sessions}), 200
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @bp.route('/api/capture_sessions', methods=['POST'])
    def trigger_capture_now():
        """
        Trigger an immediate capture cycle from the frontend.
        Returns 202 immediately; the cycle runs in a background thread.
        Returns 409 if a capture is already running.
        """
        if capture_manager._capture_running_lock.locked():
            return jsonify({
                'success': False,
                'error': 'A capture cycle is already in progress. Please wait.',
            }), 409

        def _run():
            try:
                capture_manager.run_full_capture_cycle(triggered_by='manual')
            except Exception as e:
                _CUSTOM_PRINT_FUNC(f"[Capture] Background manual capture error: {e}")

        threading.Thread(target=_run, daemon=True).start()
        return jsonify({'success': True, 'pending': True}), 202

    # ── Pump activity logs ────────────────────────────────────────────────────

    @bp.route('/api/pump-logs', methods=['GET'])
    def get_pump_logs():
        """Return recent pump pulse events. Query param: ?limit=50"""
        try:
            limit = min(int(request.args.get('limit', 50)), 200)
            logs  = mongo_db_handler.get_pump_logs(limit)
            for log in logs:
                ts = log.get('timestamp')
                if hasattr(ts, 'isoformat'):
                    log['timestamp'] = ts.isoformat()
            return jsonify({'success': True, 'logs': logs}), 200
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # ── Legacy capture endpoints ──────────────────────────────────────────────

    @bp.route('/api/capture_images', methods=['GET'])
    def get_capture_images():
        """Legacy: redirect to capture_sessions."""
        try:
            sessions = mongo_db_handler.get_capture_sessions(2)
            captures = []
            for session in sessions:
                urls = []
                for img in session.get('images', []):
                    if img.get('s3_key'):
                        urls.append(
                            s3_handler.generate_presigned_url(img['s3_key'], expiry_seconds=3600)
                        )
                ts = session.get('timestamp')
                captures.append({
                    'timestamp':    ts.isoformat() if hasattr(ts, 'isoformat') else str(ts),
                    'urls':         urls,
                    'camera_count': session.get('camera_count', 0),
                    'health':       session.get('health'),
                })
            return jsonify({'success': True, 'captures': captures}), 200
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @bp.route('/api/capture_images', methods=['POST'])
    def capture_images_now():
        """Legacy: triggers a full capture cycle."""
        try:
            session_doc = capture_manager.run_full_capture_cycle(triggered_by='manual')
            urls = []
            for img in session_doc.get('images', []):
                if img.get('s3_key'):
                    urls.append(
                        s3_handler.generate_presigned_url(img['s3_key'], expiry_seconds=3600)
                    )
            ts = session_doc.get('timestamp')
            entry = {
                'timestamp':    ts.isoformat() if hasattr(ts, 'isoformat') else str(ts),
                'urls':         urls,
                'camera_count': session_doc.get('camera_count', 0),
                'health':       session_doc.get('health'),
            }
            return jsonify({'success': True, 'captures': [entry]}), 200
        except Exception as e:
            if 'already in progress' in str(e):
                return jsonify({'success': False, 'error': str(e)}), 409
            return jsonify({'success': False, 'error': str(e)}), 500

    # ── Local image capture ───────────────────────────────────────────────────

    @bp.route('/api/capture_local', methods=['POST'])
    def capture_local():
        """Capture one frame from each camera and save as JPEG files locally."""
        import os, datetime
        save_dir = os.path.join(os.path.dirname(__file__), 'captures')
        os.makedirs(save_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        saved = []
        for cam_id in (1, 2, 4):
            jpeg = camera.get_frame_jpeg(cam_id)
            if jpeg:
                filename = f'cam{cam_id}_{timestamp}.jpg'
                filepath = os.path.join(save_dir, filename)
                with open(filepath, 'wb') as f:
                    f.write(jpeg)
                saved.append({'camera_id': cam_id, 'file': filepath, 'success': True})
            else:
                saved.append({'camera_id': cam_id, 'file': None, 'success': False, 'error': 'No frame available'})
        return jsonify({'success': True, 'timestamp': timestamp, 'captures': saved})

    @bp.route('/api/capture_local/<int:cam_id>', methods=['POST'])
    def capture_local_single(cam_id):
        """Capture one frame from a single camera, save locally, and return the JPEG."""
        import os, datetime
        if cam_id not in (1, 2, 4):
            return jsonify({'success': False, 'error': 'Invalid camera id'}), 400
        jpeg = camera.get_frame_jpeg(cam_id)
        if not jpeg:
            return jsonify({'success': False, 'error': 'No frame available'}), 503
        save_dir = os.path.join(os.path.dirname(__file__), 'captures')
        os.makedirs(save_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'cam{cam_id}_{timestamp}.jpg'
        filepath = os.path.join(save_dir, filename)
        with open(filepath, 'wb') as f:
            f.write(jpeg)
        from flask import send_file
        return send_file(
            filepath,
            mimetype='image/jpeg',
            as_attachment=True,
            download_name=filename,
        )

    # ── S3 browser ───────────────────────────────────────────────────────────

    @bp.route('/api/s3/files', methods=['GET'])
    def list_s3_files():
        """
        List all objects in the S3 bucket, newest first.
        Optional query param: ?prefix=captures/ to filter by folder.
        """
        try:
            prefix  = request.args.get('prefix', None)
            objects = s3_handler.list_objects(prefix=prefix)
            objects.sort(key=lambda o: o['last_modified'], reverse=True)
            return jsonify({'success': True, 'count': len(objects), 'files': objects})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # ── Web / camera stream routes ────────────────────────────────────────────

    @bp.route('/')
    def index():
        return render_template('index.html')

    @bp.route('/video_c1')
    def stream_c1():
        if not camera.is_camera_available(1):
            return Response(status=503)
        return Response(camera.stream_camera_1(),
                        mimetype='multipart/x-mixed-replace; boundary=frame')

    @bp.route('/video_c2')
    def stream_c2():
        if not camera.is_camera_available(2):
            return Response(status=503)
        return Response(camera.stream_camera_2(),
                        mimetype='multipart/x-mixed-replace; boundary=frame')

    @bp.route('/video_c4')
    def stream_c4():
        if not camera.is_camera_available(4):
            return Response(status=503)
        return Response(camera.stream_camera_4(),
                        mimetype='multipart/x-mixed-replace; boundary=frame')

    @bp.route('/api/frame/<int:cam_id>')
    def get_frame(cam_id):
        """Return a single JPEG frame for polling-based live view."""
        if cam_id not in (1, 2, 4):
            return jsonify({'error': 'Invalid camera id'}), 400
        jpeg = camera.get_frame_jpeg(cam_id)
        if jpeg is None:
            return jsonify({'error': f'Camera {cam_id} unavailable'}), 503
        response = Response(jpeg, mimetype='image/jpeg')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma']        = 'no-cache'
        return response

    # ── Growth measurement endpoints ──────────────────────────────────────────

    def _serialize_growth_doc(doc: dict) -> dict:
        """Convert datetime and ObjectId fields in a growth doc to JSON-safe types."""
        out = {}
        for k, v in doc.items():
            if k == '_id':
                continue                        # never expose ObjectId to the frontend
            if hasattr(v, 'isoformat'):
                out[k] = v.isoformat()          # datetime → ISO string
            elif hasattr(v, '__str__') and type(v).__name__ == 'ObjectId':
                out[k] = str(v)                 # ObjectId fallback
            else:
                out[k] = v
        # Generate presigned URLs for S3 output images
        for field, url_key in [
            ('growth_chart_s3_key',   'growth_chart_url'),
            ('detection_cam1_s3_key', 'detection_cam1_url'),
            ('detection_cam2_s3_key', 'detection_cam2_url'),
            ('detection_cam3_s3_key', 'detection_cam3_url'),
        ]:
            s3_key = doc.get(field)
            if s3_key:
                out[url_key] = s3_handler.generate_presigned_url(s3_key, expiry_seconds=3600)
            else:
                out[url_key] = None
        return out

    @bp.route('/api/growth/latest', methods=['GET'])
    def get_growth_latest():
        """Return the most recent growth measurement from the database."""
        try:
            doc = mongo_db_handler.get_latest_growth_measurement()
            if doc is None:
                return jsonify({'success': True, 'data': None,
                                'message': 'No growth measurements yet.'}), 200
            return jsonify({'success': True, 'data': _serialize_growth_doc(doc)}), 200
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @bp.route('/api/growth/history', methods=['GET'])
    def get_growth_history():
        """Return all growth measurements ordered newest first."""
        try:
            limit = min(int(request.args.get('limit', 50)), 200)
            docs  = mongo_db_handler.get_growth_history(limit)
            return jsonify({
                'success': True,
                'count':   len(docs),
                'data':    [_serialize_growth_doc(d) for d in docs],
            }), 200
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @bp.route('/api/growth/run-latest-s3', methods=['POST'])
    def run_growth_latest_s3():
        """
        Manually trigger growth analysis using the latest S3 images.
        Reads AWS_S3_GROWTH_PREFIX env var (default: 'captures/').
        """
        try:
            prefix = request.get_json(silent=True, force=True) or {}
            prefix = prefix.get('prefix') or os.environ.get('AWS_S3_GROWTH_PREFIX', 'captures/')
            doc    = growth_metrics.run_from_s3(prefix=prefix)
            return jsonify({'success': True, 'data': _serialize_growth_doc(doc)}), 200
        except RuntimeError as e:
            if 'already in progress' in str(e):
                return jsonify({'success': False, 'error': str(e)}), 409
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @bp.route('/api/growth/capture-and-analyze', methods=['POST'])
    def growth_capture_and_analyze():
        """
        Capture 3 frames from the cameras, run growth analysis, save to DB.

        Uses capture_manager.run_full_capture_cycle() so the light toggle,
        concurrency lock, and S3 upload all happen exactly as normal captures do.
        The successful camera images from that session are then fed into the
        growth analysis pipeline.
        """
        try:
            # Step 1 — run the normal capture cycle (handles lights + lock + S3 upload)
            if capture_manager._capture_running_lock.locked():
                status = capture_manager.get_capture_status()
                return jsonify({
                    'success':      False,
                    'capture_busy': True,
                    'error':        'A camera capture is already in progress. Please wait.',
                    'capture_status': status,
                }), 409

            session_doc = capture_manager.run_full_capture_cycle(
                triggered_by='growth_analysis',
                run_health_check=False,
            )

            # Step 2 — extract successful S3 keys mapped by camera_id
            cam_id_to_b64 = {}
            for img_entry in session_doc.get('images', []):
                if img_entry.get('success') and img_entry.get('s3_key'):
                    cam_id_to_b64[img_entry['camera_id']] = img_entry.get('s3_key')

            if not cam_id_to_b64:
                failed = [
                    f"cam{img['camera_id']}: {img.get('error', 'no frame')}"
                    for img in session_doc.get('images', [])
                    if not img.get('success')
                ]
                return jsonify({
                    'success': False,
                    'error': 'No camera images were captured. ' + '; '.join(failed),
                }), 503

            # Step 3 — download captured images from S3 and run growth analysis
            doc = growth_metrics.run_from_session_s3_keys(cam_id_to_b64, s3_handler)
            return jsonify({'success': True, 'data': _serialize_growth_doc(doc)}), 200

        except RuntimeError as e:
            http_status = 409 if 'already in progress' in str(e) else 400
            return jsonify({
                'success':      False,
                'capture_busy': 'already in progress' in str(e),
                'error':        str(e),
            }), http_status
        except Exception as e:
            busy = 'already in progress' in str(e)
            return jsonify({
                'success':      False,
                'capture_busy': busy,
                'error':        str(e),
            }), (409 if busy else 500)

    # ── AI Setpoint Advisor endpoints ─────────────────────────────────────────

    @bp.route('/api/ai-advisor/latest', methods=['GET'])
    def ai_advisor_get_latest():
        """
        Return the most recent AI setpoint recommendation from the database.
        Also returns rate-limit info and whether the advisor is currently running.
        """
        try:
            import ai_setpoint_advisor
            doc = mongo_db_handler.get_latest_ai_recommendation()
            if doc:
                for field in ('created_at', 'applied_at'):
                    val = doc.get(field)
                    if hasattr(val, 'isoformat'):
                        doc[field] = val.isoformat()
            return jsonify({
                'success':    True,
                'recommendation': doc,
                'rate_limit': ai_setpoint_advisor.get_rate_limit_info(),
            }), 200
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @bp.route('/api/ai-advisor/history', methods=['GET'])
    def ai_advisor_get_history():
        """Return the last N AI recommendations (default 10)."""
        try:
            limit = min(int(request.args.get('limit', 10)), 50)
            docs  = mongo_db_handler.get_ai_recommendations(limit)
            for doc in docs:
                for field in ('created_at', 'applied_at'):
                    val = doc.get(field)
                    if hasattr(val, 'isoformat'):
                        doc[field] = val.isoformat()
            return jsonify({'success': True, 'recommendations': docs, 'count': len(docs)}), 200
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @bp.route('/api/ai-advisor/run', methods=['POST'])
    def ai_advisor_run_now():
        """
        Manually trigger the AI Setpoint Advisor (for testing).
        Runs in a background thread so the request returns immediately.
        Respects the daily rate limit.
        """
        import ai_setpoint_advisor

        if not ai_setpoint_advisor._run_lock.acquire(blocking=False):
            return jsonify({'success': False, 'error': 'Advisor is already running — please wait.'}), 409
        ai_setpoint_advisor._run_lock.release()

        rate = ai_setpoint_advisor.get_rate_limit_info()
        if rate['remaining_today'] <= 0:
            return jsonify({
                'success': False,
                'error':   f"Daily rate limit reached ({rate['max_per_day']} calls/day). Try again tomorrow.",
                'rate_limit': rate,
            }), 429

        def _run():
            try:
                ai_setpoint_advisor.run_advisor(triggered_by='manual')
            except Exception as e:
                _CUSTOM_PRINT_FUNC(f"[AI Advisor] Manual run error: {e}")

        threading.Thread(target=_run, daemon=True).start()
        return jsonify({
            'success': True,
            'message': 'AI Advisor started in background. Refresh /api/ai-advisor/latest in ~30 seconds.',
            'rate_limit': rate,
        }), 202

    @bp.route('/api/ai-advisor/<rec_id>/approve', methods=['POST'])
    def ai_advisor_approve(rec_id):
        """
        Layer 2 cannot apply setpoints directly (3-layer architecture).

        This endpoint no longer changes live setpoints. It forwards the
        recommendation to the Layer 3 Budget Manager for review. The live
        setpoint update happens ONLY through /api/layer3/approve after the
        user approves the budget decision. Kept for backward compatibility.
        """
        import layer3_budget_manager
        try:
            doc = mongo_db_handler.get_ai_recommendation_by_id(rec_id)
            if not doc:
                return jsonify({'success': False, 'error': f"Recommendation '{rec_id}' not found."}), 404

            # Forward to Layer 3 — never apply setpoints here.
            result = layer3_budget_manager.run(layer2_recommendation_id=rec_id)
            return jsonify({
                'success':              True,
                'applied_changes':      [],
                'forwarded_to_layer3':  True,
                'message':              ('Layer 2 cannot apply setpoints directly. The recommendation has '
                                         'been forwarded to the Budget Manager (Layer 3). Open the Budget '
                                         'Manager page to review and approve — that is the only path that '
                                         'updates live setpoints.'),
                'layer3_result':        result,
            }), 200
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @bp.route('/api/ai-advisor/<rec_id>/reject', methods=['POST'])
    def ai_advisor_reject(rec_id):
        """Reject an AI recommendation. Optionally accepts {reason: '...'} in the body."""
        try:
            data   = request.get_json(silent=True) or {}
            reason = data.get('reason', 'Rejected by user.')
            doc    = mongo_db_handler.get_ai_recommendation_by_id(rec_id)
            if not doc:
                return jsonify({'success': False, 'error': f"Recommendation '{rec_id}' not found."}), 404
            if doc.get('status') == 'applied':
                return jsonify({'success': False, 'error': 'Cannot reject an already applied recommendation.'}), 400
            mongo_db_handler.update_ai_recommendation(rec_id, {
                'status':           'rejected',
                'rejection_reason': reason,
            })
            return jsonify({'success': True, 'message': 'Recommendation rejected.', 'reason': reason}), 200
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # ── Layer 3 — Resource / Budget Manager endpoints ────────────────────────

    def _serialize_l3_doc(obj):
        """Recursively convert datetime objects to ISO strings for JSON responses."""
        if obj is None:
            return None
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        if isinstance(obj, dict):
            return {k: _serialize_l3_doc(v) for k, v in obj.items() if k != '_id'}
        if isinstance(obj, list):
            return [_serialize_l3_doc(i) for i in obj]
        return obj

    # Map Layer 3 modification parameter names → (setpoint key, getter, setter).
    # Covers every environment setpoint the AI Advisor can recommend so that an
    # approval actually applies the change. Pump power/pulse remain absent by design.
    _L3_SETPOINT_MAP = {
        'temperature_setpoint':     ('temperature',    lambda: setpoints.get_temperature_setpoint(),    setpoints.set_temperature_setpoint),
        'humidity_setpoint':        ('humidity',       lambda: setpoints.get_humidity_setpoint(),       setpoints.set_humidity_setpoint),
        'light_setpoint':           ('light',          lambda: setpoints.get_light_setpoint(),          setpoints.set_light_setpoint),
        'soil_ph_setpoint':         ('soil_ph',        lambda: setpoints.get_soil_ph_setpoint(),        setpoints.set_soil_ph_setpoint),
        'soil_ec_setpoint':         ('soil_ec',        lambda: setpoints.get_soil_ec_setpoint(),        setpoints.set_soil_ec_setpoint),
        'soil_temp_setpoint':       ('soil_temp',      lambda: setpoints.get_soil_temp_setpoint(),      setpoints.set_soil_temp_setpoint),
        'soil_moisture_setpoint':   ('soil_moisture',  lambda: setpoints.get_soil_humidity_setpoint(),  setpoints.set_soil_humidity_setpoint),
        'soil_hysteresis_setpoint': ('soil_hysteresis',lambda: setpoints.get_soil_humidity_hysteresis(),setpoints.set_soil_humidity_hysteresis),
        'fan_day_duty':             ('fan_day_duty',   lambda: setpoints.get_fan_day_duty(),            setpoints.set_fan_day_duty),
        'fan_night_duty':           ('fan_night_duty', lambda: setpoints.get_fan_night_duty(),          setpoints.set_fan_night_duty),
    }

    # Map Layer 2 (AI Advisor) parameter labels → Layer 3 parameter names
    # (used on APPROVE to apply the AI's recommended changes). Must cover every
    # label the advisor emits, otherwise that change is silently skipped.
    _L2_TO_L3_PARAM_MAP = {
        'Temperature':      'temperature_setpoint',
        'Humidity':         'humidity_setpoint',
        'Light':            'light_setpoint',
        'Soil pH':          'soil_ph_setpoint',
        'Soil EC':          'soil_ec_setpoint',
        'Soil Temp':        'soil_temp_setpoint',
        'Soil Moisture':    'soil_moisture_setpoint',
        'Soil Hysteresis':  'soil_hysteresis_setpoint',
    }

    @bp.route('/api/layer3/run', methods=['POST'])
    def layer3_run():
        """Manually trigger a Layer 3 review for the latest Layer 2 recommendation."""
        import layer3_budget_manager as _l3
        if not _l3._run_lock.acquire(blocking=False):
            return jsonify({'success': False, 'error': 'Layer 3 review already in progress.'}), 409
        _l3._run_lock.release()

        # No notification for the Layer 2 → Layer 3 hand-off: it is an internal
        # transition inside one workflow. The single user-facing notification is
        # emitted by the Budget Manager when its review completes.

        def _bg():
            try:
                _l3.run()
            except Exception as e:
                _CUSTOM_PRINT_FUNC(f"[Layer3] Manual run error: {e}")

        threading.Thread(target=_bg, daemon=True, name='Layer3-manual').start()
        return jsonify({
            'success': True,
            'message': 'Layer 3 review started. Check /api/layer3/latest in a few seconds.',
        }), 202

    @bp.route('/api/layer3/run-test', methods=['POST'])
    def layer3_run_test():
        """
        Test-mode Layer 3 run.  Bypasses real sensors and real daily costs.
        Does NOT write to MongoDB.  Returns the decision immediately (synchronous).

        Optional JSON body fields:
          sensors:  {soil_moisture, soil_ec, soil_ph, air_temperature, ...}
          costs:    {water_cost_nis, electricity_cost_nis, fertilizer_cost_nis}

        Uses the saved budget_config from MongoDB (water_budget, electricity_budget, etc.).
        If no body is supplied, uses safe default sensors and zero costs.
        """
        import layer3_budget_manager as _l3
        body = request.get_json(silent=True) or {}
        result = _l3.run_test(
            injected_sensors=body.get('sensors'),
            injected_costs=body.get('costs'),
        )
        return jsonify(result), 200

    @bp.route('/api/layer3/latest', methods=['GET'])
    def layer3_get_latest():
        """Return the latest Layer 3 decision with full gate results and proposed modifications."""
        try:
            doc    = mongo_db_handler.get_latest_layer3_decision()
            status = mongo_db_handler.get_layer3_status()
            return jsonify({
                'success':  True,
                'decision': _serialize_l3_doc(doc),
                'status':   _serialize_l3_doc(status),
                'message':  None if doc else 'No Layer 3 decisions yet.',
            }), 200
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @bp.route('/api/layer3/approve', methods=['POST'])
    def layer3_approve():
        """
        Approve the latest pending Layer 3 decision (or specify decision_id in body).

        Allowed setpoint changes (via existing GH_Setpoints setters):
          - light_setpoint  → setpoints.set_light_setpoint()
          - soil_moisture_setpoint → setpoints.set_soil_humidity_setpoint()

        Deferred until fan migration (Step 8):
          - fan_night_duty, fan_day_duty

        Never applied by Layer 3:
          - pump power, pump pulse duration, any actuator command

        BLOCK decisions cannot be approved.
        ALERT_ONLY decisions are acknowledged without changing any setpoints.
        """
        import datetime as _dt
        try:
            data        = request.get_json(silent=True) or {}
            decision_id = data.get('decision_id')

            doc = (mongo_db_handler.get_layer3_decision_by_id(decision_id)
                   if decision_id
                   else mongo_db_handler.get_latest_layer3_decision())

            if not doc:
                return jsonify({'success': False, 'error': 'No Layer 3 decision found.'}), 404

            decision = doc.get('decision')
            status   = doc.get('status')
            did      = doc.get('decision_id')

            # BLOCK — cannot approve under any circumstances
            if decision == 'BLOCK':
                return jsonify({
                    'success':        False,
                    'error':          ('BLOCK decisions cannot be approved. '
                                       'Resolve the sensor or plant health issue first.'),
                    'blocked_reason': doc.get('reason'),
                }), 403

            # Already finalised
            if status in ('approved', 'rejected', 'cancelled'):
                return jsonify({
                    'success': False,
                    'error':   f'This decision has already been {status}.',
                }), 400

            now = _dt.datetime.now()

            # ALERT_ONLY — acknowledge only, no setpoint changes
            if decision == 'ALERT_ONLY':
                mongo_db_handler.update_layer3_decision(did, {
                    'status':                'approved',
                    'user_action':           'acknowledged',
                    'user_action_timestamp': now,
                    'approved_values':       {},
                    'previous_values':       {},
                })
                # Sync linked AI recommendation status
                _alert_rec_id = doc.get('layer2_recommendation_id')
                if _alert_rec_id:
                    try:
                        mongo_db_handler.update_ai_recommendation(_alert_rec_id, {
                            'status':     'approved',
                            'applied_at': now,
                        })
                    except Exception as _sync_err:
                        _CUSTOM_PRINT_FUNC(f"[Layer3 Approve] AI rec status sync failed: {_sync_err}")
                _CUSTOM_PRINT_FUNC(f"[Layer3 Approve] ALERT_ONLY {did[:8]} acknowledged — no setpoints changed.")
                return jsonify({
                    'success': True,
                    'message': 'Alert acknowledged. No setpoints were changed.',
                    'applied': [],
                    'skipped': [],
                }), 200

            # APPROVE or MODIFY — apply supported setpoint changes
            applied   = []
            skipped   = []
            prev_vals = {}
            appr_vals = {}

            # Get list of modifications to apply
            mods_to_apply = doc.get('proposed_modifications', [])

            # APPROVE with no proposed_modifications: fetch Layer 2 changes
            if decision == 'APPROVE' and not mods_to_apply:
                layer2_rec_id = doc.get('layer2_recommendation_id')
                if layer2_rec_id:
                    layer2_doc = mongo_db_handler.get_ai_recommendation_by_id(layer2_rec_id)
                    if layer2_doc and layer2_doc.get('changes'):
                        # Convert Layer 2 changes to Layer 3 format
                        for l2_change in layer2_doc.get('changes', []):
                            l2_param = l2_change.get('parameter')
                            l3_param = _L2_TO_L3_PARAM_MAP.get(l2_param)
                            if l3_param:
                                mods_to_apply.append({
                                    'parameter': l3_param,
                                    'proposed_value': l2_change.get('recommended_value'),
                                })

            for mod in mods_to_apply:
                param    = mod.get('parameter')
                proposed = mod.get('proposed_value')

                if param in _L3_SETPOINT_MAP:
                    key, getter, setter = _L3_SETPOINT_MAP[param]
                    prev = getter()
                    setter(float(proposed))
                    prev_vals[key] = prev
                    appr_vals[key] = float(proposed)
                    applied.append({
                        'parameter': param,
                        'previous':  prev,
                        'applied':   float(proposed),
                        'unit':      mod.get('unit'),
                    })
                    _CUSTOM_PRINT_FUNC(
                        f"[Layer3 Approve] {param}: {prev} → {proposed}"
                    )
                else:
                    skipped.append({
                        'parameter': param,
                        'reason':    'No GH_Setpoints setter mapped for this parameter.',
                        'proposed':  proposed,
                    })

            # Save runtime_constraints to MongoDB (pump power/pulse always excluded)
            constraints = doc.get('runtime_constraints') or {}
            safe_rc = {k: v for k, v in constraints.items()}
            if safe_rc:
                safe_rc['active']     = True
                safe_rc['reason']     = f"Layer 3 decision {did[:8]} approved"
                safe_rc['created_at'] = now
                mongo_db_handler.save_runtime_constraints(safe_rc)

            # Update decision document
            mongo_db_handler.update_layer3_decision(did, {
                'status':                'approved',
                'user_action':           'approved',
                'user_action_timestamp': now,
                'previous_values':       prev_vals,
                'approved_values':       appr_vals,
            })

            # Sync the linked AI recommendation so the AI Advisor page reflects
            # the Layer 3 decision (no separate, conflicting approval state).
            layer2_rec_id = doc.get('layer2_recommendation_id')
            if layer2_rec_id:
                try:
                    mongo_db_handler.update_ai_recommendation(layer2_rec_id, {
                        'status':     'approved',
                        'applied_at': now,
                    })
                except Exception as _sync_err:
                    _CUSTOM_PRINT_FUNC(f"[Layer3 Approve] AI rec status sync failed: {_sync_err}")

            _CUSTOM_PRINT_FUNC(
                f"[Layer3 Approve] Decision {did[:8]}: "
                f"{len(applied)} applied, {len(skipped)} skipped."
            )
            try:
                import notifications
                notifications.create_notification(
                    'changes_approved', 'info',
                    'Changes approved',
                    f"{len(applied)} setpoint change(s) approved and applied to the live system.",
                    category='workflow', link='layer3',
                    meta={'decision_id': did},
                    dedup_key=f"changes_approved:{did}", dedup_window_sec=86400,
                )
            except Exception as _ntf_err:
                _CUSTOM_PRINT_FUNC(f"[Notifications] changes_approved skipped: {_ntf_err}")
            return jsonify({
                'success':   True,
                'message':   f'Layer 3 decision approved. {len(applied)} change(s) applied.',
                'applied':   applied,
                'skipped':   skipped,
                'setpoints': setpoints.get_all_setpoints(),
            }), 200

        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[Layer3 Approve] ERROR: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @bp.route('/api/layer3/reject', methods=['POST'])
    def layer3_reject():
        """Reject the latest pending Layer 3 decision (or specify decision_id). No changes applied."""
        import datetime as _dt
        try:
            data        = request.get_json(silent=True) or {}
            decision_id = data.get('decision_id')
            reason      = data.get('reason', 'Rejected by user.')

            doc = (mongo_db_handler.get_layer3_decision_by_id(decision_id)
                   if decision_id
                   else mongo_db_handler.get_latest_layer3_decision())

            if not doc:
                return jsonify({'success': False, 'error': 'No Layer 3 decision found.'}), 404

            did    = doc.get('decision_id')
            status = doc.get('status')

            if status in ('approved', 'rejected', 'cancelled'):
                return jsonify({
                    'success': False,
                    'error':   f'This decision has already been {status}.',
                }), 400

            mongo_db_handler.update_layer3_decision(did, {
                'status':                'rejected',
                'user_action':           'rejected',
                'user_action_timestamp': _dt.datetime.now(),
                'rejection_reason':      reason,
            })

            # Sync the linked AI recommendation so the AI Advisor page reflects
            # the Layer 3 rejection (single source of truth).
            layer2_rec_id = doc.get('layer2_recommendation_id')
            if layer2_rec_id:
                try:
                    mongo_db_handler.update_ai_recommendation(layer2_rec_id, {
                        'status':           'rejected',
                        'rejection_reason': reason,
                    })
                except Exception as _sync_err:
                    _CUSTOM_PRINT_FUNC(f"[Layer3 Reject] AI rec status sync failed: {_sync_err}")

            _CUSTOM_PRINT_FUNC(f"[Layer3 Reject] Decision {did[:8]} rejected. Reason: {reason}")
            try:
                import notifications
                notifications.create_notification(
                    'changes_rejected', 'info',
                    'Changes rejected',
                    'The Budget Manager decision was rejected. No changes were applied.',
                    category='workflow', link='layer3',
                    meta={'decision_id': did, 'reason': reason},
                    dedup_key=f"changes_rejected:{did}", dedup_window_sec=86400,
                )
            except Exception as _ntf_err:
                _CUSTOM_PRINT_FUNC(f"[Notifications] changes_rejected skipped: {_ntf_err}")
            return jsonify({
                'success':     True,
                'message':     'Layer 3 decision rejected. No changes applied.',
                'decision_id': did,
                'reason':      reason,
            }), 200
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @bp.route('/api/layer3/budget-config', methods=['GET', 'POST'])
    def layer3_budget_config():
        """GET: return current budget configuration. POST: update it."""
        try:
            if request.method == 'GET':
                cfg = mongo_db_handler.get_budget_config()
                cfg.pop('_source', None)
                return jsonify({'success': True, 'config': cfg}), 200

            data    = request.get_json(silent=True) or {}
            allowed = {
                'daily_budget', 'monthly_budget',
                'water_budget', 'electricity_budget', 'fertilizer_budget',
                'warning_threshold_pct', 'active',
            }
            update = {k: v for k, v in data.items() if k in allowed}
            if not update:
                return jsonify({
                    'success': False,
                    'error':   f'No valid budget fields. Allowed: {", ".join(sorted(allowed))}',
                }), 400

            mongo_db_handler.save_budget_config(update)
            cfg = mongo_db_handler.get_budget_config()
            cfg.pop('_source', None)
            return jsonify({'success': True, 'message': 'Budget config updated.', 'config': cfg}), 200
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @bp.route('/api/layer3/history', methods=['GET'])
    def layer3_get_history():
        """Return recent Layer 3 decisions. Query param: ?limit=10"""
        try:
            limit = min(int(request.args.get('limit', 10)), 50)
            docs  = mongo_db_handler.get_layer3_decisions(limit)
            return jsonify({
                'success':   True,
                'decisions': [_serialize_l3_doc(d) for d in docs],
                'count':     len(docs),
            }), 200
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # ── Actuator history (all 5 actuators, state-change events) ─────────────

    @bp.route('/api/actuators/history', methods=['GET'])
    def get_actuators_history():
        """
        Return recent actuator SESSIONS (event-based, no polling duplication).
        Each session is one ON→OFF run, or the current open 'running' session.
        Query params:
          limit    — max sessions to return (default 60, max 200)
          actuator — filter by actuator name (optional)
        """
        try:
            limit    = min(int(request.args.get('limit', 60)), 200)
            actuator = request.args.get('actuator', None)
            events   = mongo_db_handler.get_actuator_events(limit=limit, actuator=actuator)
            for ev in events:
                for field in ('started_at', 'stopped_at', 'last_updated'):
                    val = ev.get(field)
                    if hasattr(val, 'isoformat'):
                        ev[field] = val.isoformat()
            return jsonify({'success': True, 'events': events, 'count': len(events)}), 200
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # ── Actuator dashboard (enriched: sensors + setpoints + reason) ──────────

    @bp.route('/api/actuators/dashboard', methods=['GET'])
    def get_actuators_dashboard():
        """
        Return one structured object per actuator with related sensors,
        setpoints, action state, and a human-readable reason for the
        current ON/OFF decision.  Used exclusively by the Actuators page.
        """
        import datetime as _dt
        try:
            import control_loops

            # ── Snapshot sensor cache ─────────────────────────────────────────
            with app_loop._sensor_cache_lock:
                snap = dict(app_loop._sensor_cache)

            now = _dt.datetime.now()

            # ── Setpoints ─────────────────────────────────────────────────────
            sp_temp       = setpoints.get_temperature_setpoint()
            sp_light      = setpoints.get_light_setpoint()
            sp_ec         = setpoints.get_soil_ec_setpoint()
            sp_moisture   = setpoints.get_soil_humidity_setpoint()
            sp_hysteresis = setpoints.get_soil_humidity_hysteresis()
            sp_fan_day    = setpoints.get_fan_day_duty()
            sp_fan_night  = setpoints.get_fan_night_duty()

            # ── Actuator duty cycles ──────────────────────────────────────────
            heater_dc = env_actuators.get_heater_duty_cycle()
            light_dc  = env_actuators.get_light_strip_1_duty_cycle()
            fan_dc    = env_actuators.get_fan_duty_cycle()
            pump_dc   = env_actuators.get_water_pump_duty_cycle()
            fert_dc   = env_actuators.get_fertilizer_pump_duty_cycle()

            def dc_to_pct(dc):
                return round((dc / 4095) * 100, 1)

            # ── Fan schedule ──────────────────────────────────────────────────
            sched_on  = control_loops.FAN_SCHEDULE_ENABLED
            is_day    = control_loops.FAN_DAY_START_HOUR <= now.hour < control_loops.FAN_NIGHT_START_HOUR
            fan_phase = 'day' if is_day else 'night'
            fan_target_duty = sp_fan_day if is_day else sp_fan_night

            # ── Last pump logs ─────────────────────────────────────────────────
            recent_logs    = mongo_db_handler.get_pump_logs(30)
            last_water_log = next((l for l in recent_logs if l.get('pump') == 'water'), None)
            last_fert_log  = next((l for l in recent_logs if l.get('pump') == 'fertilizer'), None)

            ABSORB_WAIT_SEC = 10800   # 3 h — must match control_loops.py
            SETTLE_WAIT_SEC = 18000   # 5 h — must match control_loops.py

            def _fmt_duration(sec):
                if sec is None:
                    return None
                h = int(sec // 3600)
                m = int((sec % 3600) // 60)
                return f"{h}h {m}m" if h else f"{m}m"

            def _fmt_ago(ts):
                if ts is None:
                    return None
                delta = (now - ts).total_seconds()
                if delta < 60:
                    return "just now"
                m = int(delta // 60)
                if m < 60:
                    return f"{m}m ago"
                h = int(m // 60)
                return f"{h}h {m % 60}m ago"

            def _pump_action(log, cooldown_sec, dc):
                base = {
                    'state':               'on' if dc > 0 else 'off',
                    'percentage':          dc_to_pct(dc),
                    'last_pulse_sec':      None,
                    'last_run':            None,
                    'last_run_ago':        None,
                    'cooldown_remaining_sec': None,
                    'cooldown_remaining_str': None,
                    'is_in_cooldown':      False,
                }
                if log is None:
                    return base
                ts = log.get('timestamp')
                if not hasattr(ts, 'total_seconds'):
                    delta_sec = (now - ts).total_seconds() if ts else None
                else:
                    delta_sec = None
                if ts and not hasattr(ts, 'total_seconds'):
                    base['last_run']     = ts.isoformat()
                    base['last_run_ago'] = _fmt_ago(ts)
                    delta_sec = (now - ts).total_seconds()
                base['last_pulse_sec'] = log.get('pulse_sec')
                if delta_sec is not None:
                    rem = cooldown_sec - delta_sec
                    base['cooldown_remaining_sec'] = max(0, int(rem))
                    base['cooldown_remaining_str'] = _fmt_duration(max(0, rem))
                    base['is_in_cooldown']         = rem > 0
                return base

            # ── Live sensor values ─────────────────────────────────────────────
            soil_moisture = snap.get('soil_humidity')
            soil_ec       = snap.get('soil_ec')
            soil_ph       = snap.get('soil_ph')
            air_temp      = snap.get('air_temperature')
            air_humidity  = snap.get('air_humidity')
            soil_temp     = snap.get('soil_temperature')
            light_lux     = snap.get('light_intensity')

            def _safe(v, decimals=1):
                if v is None or (isinstance(v, float) and v != v):
                    return None
                return round(v, decimals)

            # ── Water pump reason ──────────────────────────────────────────────
            band_ok   = sp_moisture
            band_acc  = sp_moisture - sp_hysteresis
            band_1s   = band_acc - 5.0
            band_1_5s = band_1s  - 5.0
            _m = soil_moisture
            if _m is None or (_m == _m) is False or _m == 0 or _m < 5.0:
                water_reason = "Blocked: soil sensor data invalid (RS485 error)"
                water_sensor_status = 'error'
            else:
                water_sensor_status = 'ok'
                if _m >= band_ok:
                    water_reason = f"Moisture {_m:.1f}% ≥ target {band_ok:.1f}% — pump OFF"
                elif _m >= band_acc:
                    water_reason = f"Moisture {_m:.1f}% in acceptable range ({band_acc:.1f}–{band_ok:.1f}%) — pump OFF"
                elif _m >= band_1s:
                    water_reason = f"Moisture {_m:.1f}% low — 1 s pulse due ({band_1s:.1f}–{band_acc:.1f}%)"
                elif _m >= band_1_5s:
                    water_reason = f"Moisture {_m:.1f}% very low — 1.5 s pulse due"
                else:
                    water_reason = f"Moisture {_m:.1f}% critically low — 2 s pulse due"

            # ── Fertilizer pump reason ─────────────────────────────────────────
            EC_DANGER     = 2000.0
            EC_HIGH       = 1600.0
            EC_ABOVE_WARN = 1000.0
            ec_close    = sp_ec - 200.0
            ec_pulse_1s = sp_ec - 400.0
            _e = soil_ec
            if _e is None or (_e == _e) is False or _e < 50:
                fert_reason = "Blocked: EC sensor data invalid (RS485 error)"
                fert_sensor_status = 'error'
            elif _e >= EC_DANGER:
                fert_reason = f"DANGER: EC {_e:.0f} µS/cm ≥ {EC_DANGER:.0f} — root burn risk, diluting with water"
                fert_sensor_status = 'danger'
            elif _e >= EC_HIGH:
                fert_reason = f"EC {_e:.0f} µS/cm too high (≥ {EC_HIGH:.0f}) — pump OFF"
                fert_sensor_status = 'warn'
            elif _e > EC_ABOVE_WARN:
                fert_reason = f"EC {_e:.0f} µS/cm above safe range (> {EC_ABOVE_WARN:.0f}) — pump OFF"
                fert_sensor_status = 'warn'
            elif _e >= sp_ec:
                fert_reason = f"EC {_e:.0f} µS/cm at/above target {sp_ec:.0f} µS/cm — pump OFF"
                fert_sensor_status = 'ok'
            elif _e >= ec_close:
                fert_reason = f"EC {_e:.0f} µS/cm in acceptable band ({ec_close:.0f}–{sp_ec:.0f}) — pump OFF"
                fert_sensor_status = 'ok'
            elif _e >= ec_pulse_1s:
                fert_reason = f"EC {_e:.0f} µS/cm low — 1 s fertilizer pulse scheduled"
                fert_sensor_status = 'warn'
            else:
                fert_reason = f"EC {_e:.0f} µS/cm very low (< {ec_pulse_1s:.0f}) — 1.5 s fertilizer pulse scheduled"
                fert_sensor_status = 'warn'

            # ── LED reason ────────────────────────────────────────────────────
            _l = light_lux
            if sp_light == 0:
                led_reason = "Light setpoint is 0 — grow light OFF"
            elif _l is None:
                led_reason = "Light sensor unavailable — PID running open-loop"
            elif _l >= sp_light * 1.05:
                led_reason = f"Light {_l:.0f} lux above target {sp_light:.0f} — PID dimming"
            elif _l >= sp_light * 0.95:
                led_reason = f"Light {_l:.0f} lux near target {sp_light:.0f} — stable"
            else:
                led_reason = f"Light {_l:.0f} lux below target {sp_light:.0f} — PID increasing power"

            # ── Fan reason ────────────────────────────────────────────────────
            if sched_on:
                fan_reason = (
                    f"{'Day' if is_day else 'Night'} schedule ({now.strftime('%H:%M')}) — "
                    f"fan at {dc_to_pct(fan_target_duty):.0f}%"
                )
            else:
                _t = air_temp
                if _t is None:
                    fan_reason = "Temperature sensor unavailable — PID waiting"
                elif _t > sp_temp + 1.0:
                    fan_reason = f"Cooling: air {_t:.1f}°C above target {sp_temp:.1f}°C"
                elif _t < sp_temp - 1.0:
                    fan_reason = f"Air {_t:.1f}°C below target — fan idle (heater controls)"
                else:
                    fan_reason = f"Air {_t:.1f}°C near target {sp_temp:.1f}°C — stable"

            # ── Fan setpoints + action ─────────────────────────────────────────
            # The ventilator is driven by the temperature PID (cooling) unless the
            # day/night schedule is explicitly enabled. Report whichever mode is
            # actually active so the actuator card matches the real control logic.
            if sched_on:
                fan_setpoints = [
                    {'label': 'Day power',   'value': dc_to_pct(sp_fan_day),   'unit': '%'},
                    {'label': 'Night power', 'value': dc_to_pct(sp_fan_night), 'unit': '%'},
                    {'label': 'Schedule',
                     'value': f"{control_loops.FAN_DAY_START_HOUR:02d}:00 – {control_loops.FAN_NIGHT_START_HOUR:02d}:00",
                     'unit': ''},
                ]
                fan_action = {
                    'state':        'on' if fan_dc > 0 else 'off',
                    'percentage':   dc_to_pct(fan_dc),
                    'mode':         'schedule',
                    'phase':        fan_phase,
                    'current_time': now.strftime('%H:%M'),
                }
            else:
                fan_setpoints = [
                    {'label': 'Temp target', 'value': round(sp_temp, 1),       'unit': '°C'},
                    {'label': 'Cool above',  'value': round(sp_temp + 1.0, 1), 'unit': '°C'},
                    {'label': 'Max power',   'value': dc_to_pct(control_loops.FAN_DAY_DUTY), 'unit': '%'},
                ]
                fan_action = {
                    'state':      'on' if fan_dc > 0 else 'off',
                    'percentage': dc_to_pct(fan_dc),
                    'mode':       'pid',
                }

            # ── Heater reason ─────────────────────────────────────────────────
            DEADBAND = 1.0
            _t = air_temp
            if _t is None:
                heater_reason = "Temperature sensor unavailable — PID waiting"
            elif abs(_t - sp_temp) < DEADBAND:
                heater_reason = f"Air {_t:.1f}°C within ±{DEADBAND}°C deadband of target {sp_temp:.1f}°C — idle"
            elif _t < sp_temp:
                heater_reason = f"Heating: air {_t:.1f}°C below target {sp_temp:.1f}°C"
            else:
                heater_reason = f"Air {_t:.1f}°C above target {sp_temp:.1f}°C — heater OFF"

            return jsonify({
                'success':      True,
                'last_updated': now.strftime('%Y-%m-%d %H:%M:%S'),
                'data': {
                    'water_pump': {
                        'sensors': [
                            {'label': 'Moisture', 'value': _safe(soil_moisture, 1), 'unit': '%',
                             'status': water_sensor_status},
                        ],
                        'setpoints': [
                            {'label': 'Target',     'value': round(sp_moisture, 1),  'unit': '%'},
                            {'label': 'Deadband',   'value': f'±{sp_hysteresis:.1f}','unit': '%'},
                            {'label': 'Absorb wait','value': round(ABSORB_WAIT_SEC / 3600, 1), 'unit': 'h'},
                        ],
                        'action':   _pump_action(last_water_log, ABSORB_WAIT_SEC, pump_dc),
                        'reason':   water_reason,
                    },
                    'fertilizer_pump': {
                        'sensors': [
                            {'label': 'EC', 'value': _safe(soil_ec, 0), 'unit': 'µS/cm',
                             'status': fert_sensor_status},
                            {'label': 'pH', 'value': _safe(soil_ph, 2), 'unit': '',
                             'status': ('warn' if soil_ph is not None and (soil_ph < 5.2 or soil_ph > 7.5) else 'ok')},
                        ],
                        'setpoints': [
                            {'label': 'EC target',    'value': round(sp_ec, 0),       'unit': 'µS/cm'},
                            {'label': 'pH range',     'value': '5.2 – 7.5',            'unit': ''},
                            {'label': 'Settle wait',  'value': round(SETTLE_WAIT_SEC / 3600, 1), 'unit': 'h'},
                        ],
                        'action':   _pump_action(last_fert_log, SETTLE_WAIT_SEC, fert_dc),
                        'reason':   fert_reason,
                    },
                    'light': {
                        'sensors': [
                            {'label': 'Light', 'value': _safe(light_lux, 0), 'unit': 'lux', 'status': 'ok'},
                        ],
                        'setpoints': [
                            {'label': 'Target lux', 'value': round(sp_light, 0), 'unit': 'lux'},
                        ],
                        'action': {
                            'state':      'on' if light_dc > 0 else 'off',
                            'percentage': dc_to_pct(light_dc),
                        },
                        'reason': led_reason,
                    },
                    'fan': {
                        'sensors': [
                            {'label': 'Air Temp',  'value': _safe(air_temp, 1),     'unit': '°C', 'status': 'ok'},
                            {'label': 'Humidity',  'value': _safe(air_humidity, 1), 'unit': '%',  'status': 'ok'},
                        ],
                        'setpoints': fan_setpoints,
                        'action':    fan_action,
                        'reason':    fan_reason,
                    },
                    'heater': {
                        'sensors': [
                            {'label': 'Air Temp',  'value': _safe(air_temp, 1),  'unit': '°C', 'status': 'ok'},
                            {'label': 'Root Temp', 'value': _safe(soil_temp, 1), 'unit': '°C', 'status': 'ok'},
                        ],
                        'setpoints': [
                            {'label': 'Target',   'value': round(sp_temp, 1), 'unit': '°C'},
                            {'label': 'Deadband', 'value': f'±{DEADBAND}',   'unit': '°C'},
                        ],
                        'action': {
                            'state':      'on' if heater_dc > 0 else 'off',
                            'percentage': dc_to_pct(heater_dc),
                        },
                        'reason': heater_reason,
                    },
                },
            })
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[/api/actuators/dashboard] ERROR: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    # ── Notifications (UI bell + toast) ───────────────────────────────────────
    @bp.route('/api/notifications', methods=['GET'])
    def notifications_list():
        """Return notifications (newest first) plus the current unread count.

        Query params: since (ISO-8601), limit (default 50), unread_only (bool)."""
        try:
            since       = request.args.get('since') or None
            limit       = int(request.args.get('limit', 50))
            unread_only = request.args.get('unread_only', 'false').lower() == 'true'
            items = mongo_db_handler.get_notifications(
                since=since, limit=limit, unread_only=unread_only,
            )
            return jsonify({
                'success':      True,
                'notifications': items,
                'unread_count': mongo_db_handler.get_unread_notification_count(),
            }), 200
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @bp.route('/api/notifications/<notification_id>/read', methods=['POST'])
    def notifications_mark_read(notification_id):
        """Mark a single notification as read (mark-read on click)."""
        try:
            ok = mongo_db_handler.mark_notification_read(notification_id)
            return jsonify({
                'success':      ok,
                'unread_count': mongo_db_handler.get_unread_notification_count(),
            }), (200 if ok else 404)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @bp.route('/api/notifications/read-all', methods=['POST'])
    def notifications_mark_all_read():
        """Mark all notifications as read."""
        try:
            updated = mongo_db_handler.mark_all_notifications_read()
            return jsonify({'success': True, 'updated': updated, 'unread_count': 0}), 200
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @bp.route('/api/notifications/clear', methods=['DELETE'])
    def notifications_clear():
        """Delete all notifications (history)."""
        try:
            removed = mongo_db_handler.clear_notifications()
            return jsonify({'success': True, 'removed': removed, 'unread_count': 0}), 200
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # ── Register blueprint ────────────────────────────────────────────────────
    app.register_blueprint(bp)
    return bp
