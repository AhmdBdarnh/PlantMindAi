"""
capture_manager.py — Camera capture cycles and scheduled health checks.

Call init() once at startup.  After that:
  - run_full_capture_cycle() can be called from any thread or route.
  - camera_capture_task() is designed to run as a background thread target.
  - last_health_result holds the most recent PlantId result (None until first run).
  - _capture_running_lock is exported so routes can peek at it without acquiring.
"""
import base64 as _b64
import datetime
import threading
import time

from utils.utils import _CUSTOM_PRINT_FUNC

# ── Module-level state ────────────────────────────────────────────────────────
last_health_result = None
_capture_running_lock = threading.Lock()

_camera            = None
_s3_handler        = None
_mongo_db_handler  = None
_plant_health      = None
_env_actuators     = None
_setpoints         = None
_light_pause_event = None


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


# ── Internal helpers ──────────────────────────────────────────────────────────

def _toggle_flash_light(state=1):
    if state == 1:
        if _setpoints.get_operation_mode() == "autonomous":
            _light_pause_event.clear()  # Pause light PID thread
        while not _env_actuators.set_light_strip_1_duty_cycle(4095):
            _CUSTOM_PRINT_FUNC("Turning on light strip 1 for camera flash...")
            time.sleep(0.1)
        while not _env_actuators.set_light_strip_2_duty_cycle(4095):
            _CUSTOM_PRINT_FUNC("Turning on light strip 2 for camera flash...")
            time.sleep(0.1)
    else:
        if _setpoints.get_operation_mode() == "autonomous":
            _light_pause_event.set()  # Resume light PID thread


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

    if not _capture_running_lock.acquire(blocking=False):
        raise Exception("A capture cycle is already in progress. Please wait.")

    session_id = datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    timestamp  = datetime.datetime.now()
    _CUSTOM_PRINT_FUNC(
        f"[Capture] Starting session {session_id} (triggered_by={triggered_by})"
    )

    try:
        # Step 1 — flash lights for better image quality
        _toggle_flash_light(1)
        time.sleep(0.5)

        # Step 2 — capture from all cameras (reads from live grabbers — instant)
        try:
            cam_results = _camera.capture_frames_base64()
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[Capture] Camera capture call failed entirely: {e}")
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
                    last_health_result = result
                    _mongo_db_handler.update_capture_session_health(session_id, result)
                    status = "HEALTHY" if result.get("is_healthy") else "ISSUES DETECTED"
                    _CUSTOM_PRINT_FUNC(
                        f"[Health] {status} ({result.get('health_probability')}%)"
                    )
                except Exception as e:
                    _CUSTOM_PRINT_FUNC(f"[Health] Background check error: {e}")
            threading.Thread(target=_run_health, daemon=True).start()

        return session_doc

    finally:
        _toggle_flash_light(0)
        _capture_running_lock.release()


def camera_capture_task(capture_interval: int, health_check_interval: int):
    """
    Background thread: captures images every capture_interval seconds but only
    calls the Plant.id health API every health_check_interval seconds to preserve credits.
    """
    last_health_check_time = datetime.datetime.min  # force check on first run
    while True:
        try:
            now = datetime.datetime.now()
            seconds_since_health = (now - last_health_check_time).total_seconds()
            run_health = seconds_since_health >= health_check_interval
            run_full_capture_cycle(triggered_by="scheduler", run_health_check=run_health)
            if run_health:
                last_health_check_time = datetime.datetime.now()
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[CaptureTask] Cycle error: {e}")
        time.sleep(capture_interval)
