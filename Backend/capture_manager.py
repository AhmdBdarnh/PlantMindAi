"""
capture_manager.py — Camera capture cycles and scheduled health checks.

Call init() once at startup.  After that:
  - run_full_capture_cycle()      — health capture → s3://captures/
  - run_growth_capture_cycle()    — growth capture → s3://growth_capture_input/
  - daily_capture_task()          — scheduler for health capture (14:00)
  - daily_growth_capture_task()   — scheduler for growth capture (17:00)
  - last_health_result            — most recent PlantId result (None until first run)
  - _capture_running_lock         — exported so routes can peek without acquiring
"""
import base64 as _b64
import datetime
import threading
import time

from utils.utils import _CUSTOM_PRINT_FUNC
from telegram_alerts import alert_camera_failure, alert_s3_failure, alert_system_crash, alert_health_api_failure

# ── Module-level state ────────────────────────────────────────────────────────
last_health_result    = None
_capture_running_lock = threading.Lock()

# Metadata about the current (or last) capture — updated atomically under _meta_lock
_meta_lock = threading.Lock()
_capture_meta = {
    'in_progress': False,
    'started_at':  None,   # datetime
    'source':      None,   # 'manual', 'scheduler', 'growth_analysis', ...
}
STALE_LOCK_MINUTES = 5     # warn (and attempt force-release) if lock held this long

_camera            = None
_s3_handler        = None
_mongo_db_handler  = None
_plant_health      = None
_env_actuators     = None
_setpoints         = None
_light_pause_event = None
_prev_light_dc     = 0   # saved before flash so we can restore after

# Camera ID → growth calculator name mapping (shared with growth_metrics.py)
_GROWTH_CAM_ID_TO_NAME = {1: 'cam1', 2: 'cam2', 4: 'cam3'}


def init(camera, s3_handler, mongo_db_handler, plant_health_checker,
         env_actuators, setpoints, light_pause_event):
    global _camera, _s3_handler, _mongo_db_handler, _plant_health
    global _env_actuators, _setpoints, _light_pause_event
    _camera            = camera
    _s3_handler        = s3_handler
    _mongo_db_handler  = mongo_db_handler
    _plant_health      = plant_health_checker
    _env_actuators     = env_actuators
    _setpoints         = setpoints
    _light_pause_event = light_pause_event


# ── Capture status helpers ────────────────────────────────────────────────────

def get_capture_status() -> dict:
    """Return a JSON-safe dict describing the current capture state."""
    with _meta_lock:
        meta = dict(_capture_meta)

    started_at  = meta['started_at']
    in_progress = meta['in_progress']
    elapsed_sec = None
    stale       = False

    if in_progress and started_at:
        elapsed_sec = (datetime.datetime.now() - started_at).total_seconds()
        if elapsed_sec > STALE_LOCK_MINUTES * 60:
            stale = True
            _CUSTOM_PRINT_FUNC(
                f"[Capture] WARNING: lock held for {elapsed_sec/60:.1f} min — possible stale lock"
            )

    return {
        'in_progress':  in_progress,
        'started_at':   started_at.isoformat() if started_at else None,
        'source':       meta['source'],
        'elapsed_sec':  round(elapsed_sec) if elapsed_sec is not None else None,
        'stale':        stale,
        'message': (
            f"Capture running (source={meta['source']}, "
            f"elapsed={round(elapsed_sec)}s)"
            if in_progress else 'No capture in progress'
        ),
    }


def _set_capture_meta(in_progress: bool, source: str = None):
    with _meta_lock:
        _capture_meta['in_progress'] = in_progress
        _capture_meta['started_at']  = datetime.datetime.now() if in_progress else None
        _capture_meta['source']      = source if in_progress else None


def _check_and_release_stale_lock():
    """If the lock has been held for > STALE_LOCK_MINUTES, force-release it safely."""
    if not _capture_running_lock.locked():
        return
    with _meta_lock:
        started = _capture_meta.get('started_at')
    if started is None:
        return
    elapsed = (datetime.datetime.now() - started).total_seconds()
    if elapsed > STALE_LOCK_MINUTES * 60:
        _CUSTOM_PRINT_FUNC(
            f"[Capture] STALE LOCK: held for {elapsed/60:.1f} min — force releasing"
        )
        try:
            _capture_running_lock.release()
        except RuntimeError:
            pass
        _set_capture_meta(False)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _toggle_flash_light(state=1):
    global _prev_light_dc
    if state == 1:
        # Save current duty cycle so we can restore it after capture
        _prev_light_dc = _env_actuators.get_light_strip_1_duty_cycle()
        # If light is currently ON, turn it OFF for the capture
        if _prev_light_dc > 0:
            if _setpoints.get_operation_mode() == "autonomous":
                _light_pause_event.clear()  # Pause light PID thread
            while not _env_actuators.set_light_strip_1_duty_cycle(0):
                _CUSTOM_PRINT_FUNC("Turning off light strip 1 for capture...")
                time.sleep(0.1)
            while not _env_actuators.set_light_strip_2_duty_cycle(0):
                _CUSTOM_PRINT_FUNC("Turning off light strip 2 for capture...")
                time.sleep(0.1)
            _CUSTOM_PRINT_FUNC(f"[Capture] Light was at {_prev_light_dc} → turned OFF for capture")
        else:
            _CUSTOM_PRINT_FUNC("[Capture] Light already off — no change before capture")
    else:
        # Restore light to exactly what it was before the capture
        while not _env_actuators.set_light_strip_1_duty_cycle(_prev_light_dc):
            _CUSTOM_PRINT_FUNC("Restoring light strip 1 to previous state...")
            time.sleep(0.1)
        while not _env_actuators.set_light_strip_2_duty_cycle(_prev_light_dc):
            _CUSTOM_PRINT_FUNC("Restoring light strip 2 to previous state...")
            time.sleep(0.1)
        if _setpoints.get_operation_mode() == "autonomous":
            _light_pause_event.set()  # Resume light PID thread
        _CUSTOM_PRINT_FUNC(f"[Capture] Light restored to {_prev_light_dc}")


# ── Public API ────────────────────────────────────────────────────────────────

def run_full_capture_cycle(triggered_by: str = 'scheduler', run_health_check: bool = True) -> dict:
    """
    One full capture cycle:
      1. Flash light on briefly for better photos.
      2. Capture one frame from each of the 3 cameras (independently – one failure
         doesn't block the others).
      3. Upload each successful image to S3 using a stable key (no expiry).
      4. Run Plant.id health assessment on the captured images.
      5. Persist the session document (session_id, timestamp, images, health)
         to MongoDB's capture_sessions collection.
      6. Update the in-memory last_health_result so /api/plant_health keeps working.

    Returns the session document (with S3 keys, not presigned URLs).
    Raises if a capture is already in progress; per-camera failures are logged.
    """
    global last_health_result

    # Auto-release stale lock before trying to acquire
    _check_and_release_stale_lock()

    if not _capture_running_lock.acquire(blocking=True, timeout=120):
        raise Exception("A camera capture is already in progress. Please wait.")

    # Everything from here is inside try/finally — lock is always released
    try:
        session_id = datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        timestamp  = datetime.datetime.now()
        _set_capture_meta(True, triggered_by)
        _CUSTOM_PRINT_FUNC(
            f"[Capture] ► START  session={session_id}  source={triggered_by}"
        )
        # Step 1 — flash lights for better image quality
        _toggle_flash_light(1)
        time.sleep(0.5)

        # Step 2 — capture from all cameras (reads from live grabbers — instant)
        try:
            cam_results = _camera.capture_frames_base64()
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[Capture] Camera capture call failed entirely: {e}")
            alert_camera_failure("all", str(e))
            cam_results = []

        # Step 3 — upload all successful captures to S3 in parallel threads
        images = [None] * len(cam_results)
        images_b64_for_health = []
        upload_lock = threading.Lock()

        def _upload_one(idx, cam):
            entry = {
                "camera_id":   cam["camera_id"],
                "camera_name": cam["name"],
                "s3_key":      None,
                "success":     False,
                "error":       cam.get("error"),
            }
            if not cam.get("success"):
                _CUSTOM_PRINT_FUNC(
                    f"[Capture] Camera {cam['camera_id']} skipped: {cam.get('error')}"
                )
                alert_camera_failure(cam['camera_id'], cam.get('error', 'unknown'))
                images[idx] = entry
                return
            key = f"captures/{session_id}/camera_{cam['camera_id']}.jpg"
            try:
                img_bytes = _b64.b64decode(cam["b64"])
                url = _s3_handler.upload_bytes(img_bytes, key)
                if url:
                    entry["s3_key"]  = key
                    entry["success"] = True
                    entry["error"]   = None
                    with upload_lock:
                        images_b64_for_health.append(cam["b64"])
                    _CUSTOM_PRINT_FUNC(
                        f"[Capture] Camera {cam['camera_id']} uploaded -> s3://{key}"
                    )
                else:
                    entry["error"] = "S3 upload returned no URL"
            except Exception as e:
                entry["error"] = f"S3 upload error: {e}"
                _CUSTOM_PRINT_FUNC(f"[Capture] Camera {cam['camera_id']} S3 error: {e}")
                alert_s3_failure(key, str(e))
            images[idx] = entry

        upload_threads = [
            threading.Thread(target=_upload_one, args=(i, cam))
            for i, cam in enumerate(cam_results)
        ]
        for t in upload_threads:
            t.start()
        for t in upload_threads:
            t.join()

        # Step 4 — save session immediately (health=None for now)
        camera_count = sum(1 for img in images if img and img["success"])
        session_doc = {
            "session_id":   session_id,
            "timestamp":    timestamp,
            "triggered_by": triggered_by,
            "images":       images,
            "health":       None,
            "camera_count": camera_count,
        }
        _mongo_db_handler.insert_capture_session(session_doc)
        session_doc.pop('_id', None)
        _CUSTOM_PRINT_FUNC(
            f"[Capture] Session {session_id} saved ({camera_count}/3 cameras)"
        )

        # Step 5 — run health check in background (does not block the response)
        if run_health_check and images_b64_for_health:
            def _run_health():
                global last_health_result
                try:
                    _CUSTOM_PRINT_FUNC(
                        f"[Health] Checking {len(images_b64_for_health)} image(s) in background..."
                    )
                    result = _plant_health.check_health(images_b64_for_health)
                    if not result.get('success'):
                        alert_health_api_failure(result.get('error', 'No error details returned'))
                    last_health_result = result
                    _mongo_db_handler.update_capture_session_health(session_id, result)

                    # Persist to plant_health_results collection
                    health_doc = {
                        'session_id':         session_id,
                        'created_at':         datetime.datetime.now(),
                        'is_healthy':         result.get('is_healthy'),
                        'health_probability': result.get('health_probability'),
                        'success':            result.get('success'),
                        'images_sent':        result.get('images_sent'),
                        'diseases':           result.get('diseases', []),
                        's3_urls':            result.get('s3_urls', []),
                        'error':              result.get('error'),
                    }
                    _mongo_db_handler.insert_plant_health_result(health_doc)

                    status = "HEALTHY" if result.get("is_healthy") else "ISSUES DETECTED"
                    _CUSTOM_PRINT_FUNC(
                        f"[Health] {status} ({result.get('health_probability')}%) — saved to DB"
                    )
                except Exception as e:
                    _CUSTOM_PRINT_FUNC(f"[Health] Background check error: {e}")
                    alert_health_api_failure(str(e))
            threading.Thread(target=_run_health, daemon=True).start()

        _CUSTOM_PRINT_FUNC(
            f"[Capture] ■ END    session={session_id}  cameras_ok={camera_count}/3"
        )
        return session_doc

    except Exception as e:
        _CUSTOM_PRINT_FUNC(f"[Capture] ✗ FAILED: {e}")
        raise
    finally:
        _toggle_flash_light(0)
        _set_capture_meta(False)
        _capture_running_lock.release()
        _CUSTOM_PRINT_FUNC("[Capture] Lock released.")


def daily_capture_task(hour: int = 14, minute: int = 0):
    """
    Background thread: fires one capture cycle every day at the specified time (default 14:00).
    Saves to s3://captures/ and runs PlantID health check.
    Sleeps until the next occurrence on startup, then repeats every 24 hours.
    """
    while True:
        now    = datetime.datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if now >= target:
            target += datetime.timedelta(days=1)
        sleep_seconds = (target - now).total_seconds()
        _CUSTOM_PRINT_FUNC(
            f"[DailyCapture] Next capture scheduled at {target.strftime('%Y-%m-%d %H:%M')} "
            f"(in {sleep_seconds / 3600:.1f}h)"
        )
        time.sleep(sleep_seconds)
        try:
            run_full_capture_cycle(triggered_by='daily_schedule')
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[DailyCapture] Cycle error: {e}")


# ── Dedicated growth capture (separate from health check) ─────────────────────

def run_growth_capture_cycle() -> dict:
    """
    Dedicated growth capture cycle — completely separate from the health check flow.

    Steps:
      1. Acquire the capture lock (shared with health capture — prevents concurrent use).
      2. Turn OFF LEDs using the existing _toggle_flash_light helper, which saves
         the current duty cycle so it can be restored exactly afterwards.
      3. Wait 3 seconds for camera exposure to stabilize under ambient light.
      4. Capture frames from all 3 cameras.
      5. Upload each frame to S3 under:
             growth_capture_input/YYYY-MM-DD/<session_id>/cam1.jpg
             growth_capture_input/YYYY-MM-DD/<session_id>/cam2.jpg
             growth_capture_input/YYYY-MM-DD/<session_id>/cam3.jpg
      6. Save session metadata to MongoDB (capture_type='growth', status='uploaded').
      7. Restore LEDs to their previous state.

    Returns the session document (S3 keys, status, metadata).
    Does NOT run the health check and does NOT run the growth algorithm —
    it only captures and stores images so the growth algorithm can run later.

    Raises if a capture is already in progress (timeout 120 s).
    """
    _check_and_release_stale_lock()

    if not _capture_running_lock.acquire(blocking=True, timeout=120):
        raise Exception("A camera capture is already in progress — please wait.")

    try:
        session_id  = datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        date_str    = datetime.datetime.now().strftime("%Y-%m-%d")
        timestamp   = datetime.datetime.now()
        s3_prefix   = f"growth_capture_input/{date_str}/{session_id}"
        _set_capture_meta(True, 'growth_capture')
        _CUSTOM_PRINT_FUNC(
            f"[GrowthCapture] ► START  session={session_id}  s3_prefix={s3_prefix}"
        )
        # ── Step 1: Turn LEDs OFF and wait for exposure to stabilize ─────────
        _toggle_flash_light(1)   # saves current LED state, turns both strips OFF
        _CUSTOM_PRINT_FUNC(
            "[GrowthCapture] LEDs turned OFF — waiting 3 s for exposure to stabilize..."
        )
        time.sleep(3)

        # ── Step 2: Capture from all cameras ──────────────────────────────────
        try:
            cam_results = _camera.capture_frames_base64()
            _CUSTOM_PRINT_FUNC(
                f"[GrowthCapture] Captured {len(cam_results)} camera frame(s)"
            )
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[GrowthCapture] Camera capture failed entirely: {e}")
            alert_camera_failure("all", str(e))
            cam_results = []

        # ── Step 3: Upload to growth_capture_input/ in S3 ────────────────────
        images      = [None] * len(cam_results)
        s3_keys     = {}          # {cam_name: s3_key}
        upload_lock = threading.Lock()

        def _upload_one(idx, cam):
            cam_id   = cam.get("camera_id")
            cam_name = _GROWTH_CAM_ID_TO_NAME.get(cam_id)
            entry = {
                "camera_id":   cam_id,
                "camera_name": cam.get("name"),
                "cam_name":    cam_name,
                "s3_key":      None,
                "success":     False,
                "error":       cam.get("error"),
            }

            if not cam.get("success"):
                _CUSTOM_PRINT_FUNC(
                    f"[GrowthCapture] Camera {cam_id} skipped: {cam.get('error')}"
                )
                alert_camera_failure(cam_id, cam.get('error', 'unknown'))
                images[idx] = entry
                return

            if not cam_name:
                _CUSTOM_PRINT_FUNC(
                    f"[GrowthCapture] Unknown camera_id {cam_id} — skipping"
                )
                images[idx] = entry
                return

            # S3 key: growth_capture_input/YYYY-MM-DD/session_id/cam1.jpg
            key = f"{s3_prefix}/{cam_name}.jpg"
            try:
                img_bytes = _b64.b64decode(cam["b64"])
                url       = _s3_handler.upload_bytes(img_bytes, key)
                if url:
                    entry["s3_key"]  = key
                    entry["success"] = True
                    entry["error"]   = None
                    with upload_lock:
                        s3_keys[cam_name] = key
                    _CUSTOM_PRINT_FUNC(
                        f"[GrowthCapture] {cam_name} (camera {cam_id}) uploaded → s3://{key}"
                    )
                else:
                    entry["error"] = "S3 upload returned no URL"
                    _CUSTOM_PRINT_FUNC(
                        f"[GrowthCapture] WARNING: {cam_name} upload returned no URL"
                    )
            except Exception as e:
                entry["error"] = f"S3 upload error: {e}"
                _CUSTOM_PRINT_FUNC(f"[GrowthCapture] {cam_name} S3 error: {e}")
                alert_s3_failure(key, str(e))

            images[idx] = entry

        upload_threads = [
            threading.Thread(target=_upload_one, args=(i, cam))
            for i, cam in enumerate(cam_results)
        ]
        for t in upload_threads:
            t.start()
        for t in upload_threads:
            t.join()

        # ── Step 4: Save session metadata to MongoDB ──────────────────────────
        camera_count = sum(1 for img in images if img and img.get("success"))
        session_doc  = {
            "session_id":   session_id,
            "capture_type": "growth",          # distinguishes from health captures
            "timestamp":    timestamp,
            "capture_time": timestamp,
            "triggered_by": "growth_daily_schedule",
            "s3_prefix":    s3_prefix,
            "s3_keys":      s3_keys,           # {cam_name: s3_key}
            "images":       images,
            "camera_count": camera_count,
            "status":       "uploaded",
        }
        _mongo_db_handler.insert_capture_session(session_doc)
        session_doc.pop('_id', None)   # ObjectId is not JSON-serializable

        _CUSTOM_PRINT_FUNC(
            f"[GrowthCapture] Session saved to MongoDB — "
            f"{camera_count}/3 cameras OK — "
            f"s3_keys={list(s3_keys.keys())}"
        )
        _CUSTOM_PRINT_FUNC(
            f"[GrowthCapture] ── Growth capture complete ──  session={session_id}"
        )

        _CUSTOM_PRINT_FUNC(
            f"[GrowthCapture] ■ END  session={session_id}  cameras_ok={camera_count}/3"
        )
        return session_doc

    except Exception as e:
        _CUSTOM_PRINT_FUNC(f"[GrowthCapture] ✗ FAILED: {e}")
        raise
    finally:
        _toggle_flash_light(0)
        _set_capture_meta(False)
        _capture_running_lock.release()
        _CUSTOM_PRINT_FUNC("[GrowthCapture] Lock released.")


def daily_growth_capture_task(hour: int = 17, minute: int = 0):
    """
    Background thread: fires one dedicated growth capture every day at 17:00.
    Saves images to s3://growth_capture_input/YYYY-MM-DD/<session_id>/ —
    completely separate from the health check captures in s3://captures/.
    The growth analysis scheduler (daily_growth_task in app.py) runs 30 min
    later at 17:30 and reads from growth_capture_input/.
    """
    while True:
        now    = datetime.datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if now >= target:
            target += datetime.timedelta(days=1)
        sleep_seconds = (target - now).total_seconds()
        _CUSTOM_PRINT_FUNC(
            f"[GrowthCapture] Next dedicated growth capture at "
            f"{target.strftime('%Y-%m-%d %H:%M')} (in {sleep_seconds / 3600:.1f}h)"
        )
        time.sleep(sleep_seconds)
        try:
            run_growth_capture_cycle()
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[GrowthCapture] Daily growth capture error: {e}")
