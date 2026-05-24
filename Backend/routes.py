"""
routes.py — All Flask API routes and web endpoints.

Use init_routes() to create and register a Blueprint.
The function receives every dependency the routes need so there are no
module-level imports of hardware objects.
"""
import threading

import capture_manager
import actuator_helpers
import app_loop
from flask import Blueprint, Response, jsonify, render_template, request
from utils.utils import _CUSTOM_PRINT_FUNC
from config import (
    WATER_PRICE_PER_LITER_NIS,
    ELECTRICITY_PRICE_PER_KWH_NIS,
    FERTILIZER_PRICE_PER_3_LITERS_NIS,
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

    # ── Sensor endpoints ──────────────────────────────────────────────────────

    @bp.route('/api/sensors', methods=['GET'])
    def get_sensors():
        """Get all sensor readings."""
        try:
            temperature_semaphore.acquire()
            try:
                air_temp_c   = env_sensors.get_air_temperature_C()
                air_humidity = env_sensors.get_air_humidity()
            finally:
                temperature_semaphore.release()

            light_semaphore.acquire()
            try:
                light_intensity = env_sensors.get_light_intensity()
            finally:
                light_semaphore.release()

            soil_semaphore.acquire()
            try:
                soil_ph, soil_ec, soil_humidity, soil_temp = env_sensors.get_soil_values()
            finally:
                soil_semaphore.release()

            electricity_semaphore.acquire()
            try:
                voltage, current, power, energy, frequency, power_factor, alarm = (
                    env_sensors.get_electricity_values()
                )
            finally:
                electricity_semaphore.release()

            water_flow_semaphore.acquire()
            try:
                water_flow      = env_sensors.get_water_flow_rate()
                fertilizer_flow = env_sensors.get_fertilizer_flow_rate()
            finally:
                water_flow_semaphore.release()

            # Use accumulated totals from app_loop — these persist across sensor resets and restarts
            water_amount      = app_loop.get_total_water_liters()
            fertilizer_amount = app_loop.get_total_fertilizer_liters()
            total_energy_wh   = app_loop.get_total_energy_wh()

            water_cost = round(water_amount * WATER_PRICE_PER_LITER_NIS, 4)
            elec_cost  = round(total_energy_wh * ELECTRICITY_PRICE_PER_KWH_NIS / 1000.0, 4)
            fert_cost  = round(fertilizer_amount * (FERTILIZER_PRICE_PER_3_LITERS_NIS / 3.0), 4)
            total_cost = round(water_cost + elec_cost + fert_cost, 4)

            return jsonify({
                'success': True,
                'data': {
                    'air_temperature': round(air_temp_c, 2),
                    'air_humidity':    round(air_humidity, 2),
                    'light_intensity': round(light_intensity, 2),
                    'soil_ph':         round(soil_ph, 2),
                    'soil_ec':         round(soil_ec, 2),
                    'soil_humidity':   round(soil_humidity, 2),
                    'soil_temperature':round(soil_temp, 2),
                    'water_flow':        round(water_flow, 2),
                    'water_amount':      round(water_amount, 2),
                    'fertilizer_flow':   round(fertilizer_flow, 2),
                    'fertilizer_amount': round(fertilizer_amount, 2),
                    'voltage':         round(voltage, 2),
                    'current':         round(current, 2),
                    'power':           round(power, 2),
                    'energy':          round(total_energy_wh, 2),
                    'frequency':       round(frequency, 2),
                    'power_factor':    round(power_factor, 2),
                    'water_cost_nis':       water_cost,
                    'electricity_cost_nis': elec_cost,
                    'fertilizer_cost_nis':  fert_cost,
                    'total_cost_nis':       total_cost,
                },
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # ── Actuator endpoints ────────────────────────────────────────────────────

    @bp.route('/api/actuators', methods=['GET'])
    def get_actuators():
        """Get all actuator states."""
        try:
            heater_dc = env_actuators.get_heater_duty_cycle()
            light_dc  = env_actuators.get_light_strip_1_duty_cycle()
            fan_dc    = env_actuators.get_fan_duty_cycle()
            pump_dc   = env_actuators.get_water_pump_duty_cycle()
            fert_dc   = env_actuators.get_fertilizer_pump_duty_cycle()

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
                        'duty_cycle': fan_dc,
                        'percentage': round((fan_dc / 4095) * 100, 2),
                        'state':      'on' if fan_dc > 0 else 'off',
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

    # ── Setpoints ─────────────────────────────────────────────────────────────

    @bp.route('/api/setpoints', methods=['GET', 'POST'])
    def setpoints_api():
        """Get or update setpoints. Each change is auto-saved to MongoDB."""
        try:
            if request.method == 'GET':
                return jsonify({'success': True, 'setpoints': setpoints.get_all_setpoints()})

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

    # ── Register blueprint ────────────────────────────────────────────────────
    app.register_blueprint(bp)
    return bp
