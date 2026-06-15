"""
growth_metrics.py — Plant growth analysis integration for PlantMind AI.

Wraps the plant-growth-calculator (teammate's code) and connects it to:
  - AWS S3  (image source and output upload)
  - MongoDB (result persistence via MongoDBHandler)
  - Camera  (direct capture for the "Capture & Analyze" flow)

Public API:
  init(s3_handler, mongo_db_handler)
  run_from_s3(prefix)          -> dict   # pull latest photos from S3, analyze
  run_from_capture(cam_results) -> dict  # analyze from live camera b64 results
"""

import os
import sys
import base64
import shutil
import tempfile
import threading
import datetime

import numpy as np
import cv2

from utils.utils import _CUSTOM_PRINT_FUNC

# ── Path to teammate's growth calculator ──────────────────────────────────────
_GROWTH_CALC_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'plant-growth-calculator')
)

# ── Module-level singletons ───────────────────────────────────────────────────
_s3_handler       = None
_mongo_db_handler = None
_analysis_lock    = threading.Lock()

# Maps project camera IDs → growth calculator camera names
#   camera 1 = side view  → cam1
#   camera 2 = front view → cam2
#   camera 4 = top-down   → cam3
CAM_ID_TO_NAME = {1: 'cam1', 2: 'cam2', 4: 'cam3'}


def init(s3_handler, mongo_db_handler):
    global _s3_handler, _mongo_db_handler
    _s3_handler       = s3_handler
    _mongo_db_handler = mongo_db_handler


# ── Lazy import of teammate's functions ───────────────────────────────────────

def _import_growth_functions():
    """Add the growth calculator directory to sys.path and import its functions."""
    if _GROWTH_CALC_DIR not in sys.path:
        sys.path.insert(0, _GROWTH_CALC_DIR)
    from functions import process_timestamp, compute_growth, smooth_area, save_growth_chart
    return process_timestamp, compute_growth, smooth_area, save_growth_chart


# ── S3 helpers ────────────────────────────────────────────────────────────────

def _cycle_boundary():
    """Return the active plant-cycle start as a timezone-aware datetime, or None.

    Images modified before this instant belong to a previous plant and must be
    ignored. The boundary is the 'cycle_started_at' value written by a
    New-Plant-Cycle / resource reset. Returns None when no cycle is set."""
    try:
        if _mongo_db_handler is None:
            return None
        raw = _mongo_db_handler.get_state('cycle_started_at')
        if not raw:
            return None
        dt = datetime.datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.astimezone()  # interpret naive local timestamp as aware
        return dt
    except Exception as e:
        _CUSTOM_PRINT_FUNC(f"[Growth] Could not parse cycle boundary: {e}")
        return None


def _fetch_latest_s3_images(prefix: str) -> tuple[dict, str]:
    """
    List objects under `prefix`, find the latest file for cam1, cam2, cam3
    (matched by filename prefix), download them to a temp dir.

    Returns:
        cam_files : {cam_name: (local_path, s3_key)}
        tmpdir    : path to the temp directory (caller must clean up)

    Raises RuntimeError when S3 is unreachable or no matching images exist.
    """
    objects = _s3_handler.list_objects(prefix=prefix)
    if not objects:
        raise RuntimeError(f"No objects found in S3 under prefix '{prefix}'")

    # Group objects by camera name.
    # Supports two filename conventions:
    #   cam1_*.jpg / cam2_*.jpg / cam3_*.jpg   (growth calculator style)
    #   camera_1.jpg / camera_2.jpg / camera_4.jpg  (capture_manager style)
    cam_buckets: dict[str, list] = {'cam1': [], 'cam2': [], 'cam3': []}
    # Maps capture_manager camera IDs to growth-calculator cam names
    _CAMID_TO_NAME = {'1': 'cam1', '2': 'cam2', '4': 'cam3'}
    for obj in objects:
        filename = obj['key'].split('/')[-1].lower()
        matched = False
        # Convention 1: cam1_*, cam2_*, cam3_*
        for cam_name in cam_buckets:
            if filename.startswith(cam_name + '_') or filename.startswith(cam_name + '.'):
                cam_buckets[cam_name].append(obj)
                matched = True
                break
        if matched:
            continue
        # Convention 2: camera_1.jpg, camera_2.jpg, camera_4.jpg
        if filename.startswith('camera_'):
            stem = filename.split('.')[0]            # e.g. 'camera_1'
            cam_id_str = stem.split('_', 1)[-1]      # e.g. '1'
            cam_name = _CAMID_TO_NAME.get(cam_id_str)
            if cam_name:
                cam_buckets[cam_name].append(obj)

    if not any(cam_buckets.values()):
        raise RuntimeError(
            f"No cam1/cam2/cam3 images found under prefix '{prefix}'. "
            "Files must start with 'cam1_', 'cam2_', or 'cam3_'."
        )

    # ── Scope to the current plant cycle ──────────────────────────────────────
    # Ignore images captured before the last New-Plant-Cycle / resource reset so a
    # new plant never analyzes the previous plant's photos. Old images stay in S3.
    boundary = _cycle_boundary()
    if boundary is not None:
        def _after_boundary(obj):
            lm = obj.get('last_modified')
            if lm is None:
                return False
            try:
                if lm.tzinfo is None:
                    lm = lm.replace(tzinfo=datetime.timezone.utc)
                return lm >= boundary
            except Exception:
                return False
        for cam_name in cam_buckets:
            cam_buckets[cam_name] = [o for o in cam_buckets[cam_name] if _after_boundary(o)]
        if not any(cam_buckets.values()):
            raise RuntimeError(
                "No camera images have been captured since the new plant cycle "
                "started. Capture new photos for this plant before running growth "
                "analysis — the previous plant's images are kept but not used."
            )

    tmpdir = tempfile.mkdtemp(prefix='growth_s3_')
    cam_files: dict[str, tuple[str, str]] = {}

    for cam_name, items in cam_buckets.items():
        if not items:
            _CUSTOM_PRINT_FUNC(f"[Growth] WARNING: No S3 image found for {cam_name}")
            continue
        # Pick the most recently modified file
        items.sort(key=lambda o: o['last_modified'], reverse=True)
        s3_key    = items[0]['key']
        filename  = s3_key.split('/')[-1]
        local_path = os.path.join(tmpdir, f'{cam_name}_{filename}')
        _s3_handler.download_file(s3_key, local_path)
        if os.path.isfile(local_path):
            cam_files[cam_name] = (local_path, s3_key)
            _CUSTOM_PRINT_FUNC(f"[Growth] Downloaded {cam_name} <- s3://{s3_key}")
        else:
            _CUSTOM_PRINT_FUNC(f"[Growth] WARNING: Download failed for {s3_key}")

    return cam_files, tmpdir


def _upload_outputs(output_dir: str, timestamp_label: str) -> dict:
    """
    Upload detection images (cam1.jpg, cam2.jpg, cam3.jpg) and growth_chart.png
    from `output_dir` to S3 under `growth_outputs/<timestamp_label>/`.

    Returns {type_key: s3_key} where type_key is one of:
        'growth_chart', 'detection_cam1', 'detection_cam2', 'detection_cam3'
    """
    s3_keys: dict[str, str] = {}
    if not os.path.isdir(output_dir):
        return s3_keys

    s3_prefix = f"growth_outputs/{timestamp_label}"
    for filename in os.listdir(output_dir):
        local_path = os.path.join(output_dir, filename)
        if not os.path.isfile(local_path):
            continue
        s3_key = f"{s3_prefix}/{filename}"
        try:
            _s3_handler.upload_file(local_path, s3_key)
            if filename == 'growth_chart.png':
                s3_keys['growth_chart'] = s3_key
            elif filename in ('cam1.jpg', 'cam2.jpg', 'cam3.jpg'):
                cam = filename.replace('.jpg', '')
                s3_keys[f'detection_{cam}'] = s3_key
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[Growth] WARNING: Could not upload {filename}: {e}")

    return s3_keys


# ── Core analysis engine ──────────────────────────────────────────────────────

def _run_analysis(images_dict: dict, timestamp_label: str, output_dir: str) -> dict:
    """
    Run the growth calculator pipeline on `images_dict` ({cam_name: bgr_ndarray}).

    Steps:
      1. process_timestamp() — segmentation + measurements per camera.
      2. Fetch previous DB record and build a two-point list for compute_growth().
      3. Save growth chart if there are ≥2 historical points.

    Returns the enriched metrics dict for the current measurement.
    """
    process_timestamp, compute_growth, smooth_area, save_growth_chart = _import_growth_functions()

    if not images_dict:
        raise RuntimeError("No images provided for growth analysis")

    os.makedirs(output_dir, exist_ok=True)

    # ── Step 1: Run the segmentation + measurement pipeline ───────────────────
    metrics = process_timestamp(
        images_dict,
        debug=False,
        label=timestamp_label,
        output_dir=output_dir,
    )
    metrics['timestamp'] = timestamp_label

    # ── Step 2: Compute AGR / RGR / growth% relative to last DB record ───────
    prev_doc = _mongo_db_handler.get_latest_growth_measurement()

    if prev_doc and prev_doc.get('status') == 'success' and prev_doc.get('area_cm2') is not None:
        captured_at = prev_doc.get('captured_at')
        prev_label  = (
            captured_at.strftime('%Y-%m-%d') if hasattr(captured_at, 'strftime')
            else str(captured_at)
        )
        prev_record = {
            'timestamp':   prev_label,
            'area_cm2':    float(prev_doc.get('area_cm2',   0.0)),
            'height_cm':   float(prev_doc.get('height_cm',  0.0)),
            'width_cm':    float(prev_doc.get('width_cm',   0.0)),
            'volume_cm3':  float(prev_doc.get('volume_cm3', 0.0)),
        }
        records = compute_growth([prev_record, metrics])
        current = records[1]
    else:
        records = compute_growth([metrics])
        current = records[0]

    smooth_area(records)

    # ── Step 3: Build historical chart using DB records + this one ────────────
    try:
        history_docs = _mongo_db_handler.get_growth_history(50)
        chart_records = []
        for h in reversed(history_docs):
            if h.get('status') != 'success' or h.get('area_cm2') is None:
                continue
            ts = h.get('captured_at')
            chart_records.append({
                'timestamp': ts.strftime('%Y-%m-%d') if hasattr(ts, 'strftime') else str(ts),
                'area_cm2':  float(h.get('area_cm2',  0.0)),
                'height_cm': float(h.get('height_cm', 0.0)),
            })
        chart_records.append({
            'timestamp': timestamp_label,
            'area_cm2':  float(current.get('area_cm2',  0.0)),
            'height_cm': float(current.get('height_cm', 0.0)),
        })
        if len(chart_records) >= 2:
            save_growth_chart(chart_records, output_dir)
    except Exception as e:
        _CUSTOM_PRINT_FUNC(f"[Growth] WARNING: Could not save growth chart: {e}")

    return current


# ── Public pipeline functions ─────────────────────────────────────────────────

def _build_empty_doc(source_type: str) -> dict:
    now = datetime.datetime.now()
    return {
        'captured_at':           now,
        'source_type':           source_type,
        'cam1_s3_key':           None,
        'cam2_s3_key':           None,
        'cam3_s3_key':           None,
        'area_cm2':              None,
        'height_cm':             None,
        'width_cm':              None,
        'depth_cm':              None,
        'canopy_area_cm2':       None,
        'volume_cm3':            None,
        'agr':                   None,
        'rgr':                   None,
        'growth_pct':            None,
        'vol_growth_pct':        None,
        'output_folder_path':    None,
        'growth_chart_s3_key':   None,
        'detection_cam1_s3_key': None,
        'detection_cam2_s3_key': None,
        'detection_cam3_s3_key': None,
        'status':                'error',
        'error_message':         None,
        'created_at':            now,
    }


def run_from_s3(prefix: str = None) -> dict:
    """
    Full pipeline using S3 as the image source:
      1. List S3 objects under `prefix`.
      2. Download the latest cam1/cam2/cam3 image.
      3. Run growth analysis.
      4. Upload detection images + chart back to S3.
      5. Save measurement to MongoDB.
      6. Return the result document.

    Raises RuntimeError if another analysis is already running.
    """
    if not _analysis_lock.acquire(blocking=False):
        raise RuntimeError("A growth analysis is already in progress. Please wait.")

    prefix          = prefix or os.environ.get('AWS_S3_GROWTH_PREFIX', 'captures/')
    timestamp_label = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    output_dir      = os.path.join(os.path.dirname(__file__), 'growth_outputs', timestamp_label)
    doc             = _build_empty_doc('s3')
    doc['output_folder_path'] = output_dir

    tmpdir = None
    try:
        # 1. Download latest images from S3
        _CUSTOM_PRINT_FUNC(f"[Growth] Fetching images from S3 prefix='{prefix}'")
        cam_files, tmpdir = _fetch_latest_s3_images(prefix)

        for cam_name, (_, s3_key) in cam_files.items():
            doc[f'{cam_name}_s3_key'] = s3_key

        # 2. Load images into numpy arrays
        images_dict: dict[str, np.ndarray] = {}
        for cam_name, (local_path, _) in cam_files.items():
            img = cv2.imread(local_path)
            if img is not None:
                images_dict[cam_name] = img
            else:
                _CUSTOM_PRINT_FUNC(f"[Growth] WARNING: cv2 could not read {local_path}")

        if not images_dict:
            raise RuntimeError("All S3 images failed to load — cannot run analysis")

        # 3. Run analysis
        _CUSTOM_PRINT_FUNC(f"[Growth] Analyzing cameras: {list(images_dict.keys())}")
        metrics = _run_analysis(images_dict, timestamp_label, output_dir)

        # 4. Upload outputs to S3
        s3_output_keys = _upload_outputs(output_dir, timestamp_label)

        # 5. Fill result document
        doc.update({
            'area_cm2':              metrics.get('area_cm2'),
            'height_cm':             metrics.get('height_cm'),
            'width_cm':              metrics.get('width_cm'),
            'depth_cm':              metrics.get('depth_cm'),
            'canopy_area_cm2':       metrics.get('canopy_area_cm2'),
            'volume_cm3':            metrics.get('volume_cm3'),
            'agr':                   metrics.get('agr'),
            'rgr':                   metrics.get('rgr'),
            'growth_pct':            metrics.get('growth%'),
            'vol_growth_pct':        metrics.get('vol_growth%'),
            'growth_chart_s3_key':   s3_output_keys.get('growth_chart'),
            'detection_cam1_s3_key': s3_output_keys.get('detection_cam1'),
            'detection_cam2_s3_key': s3_output_keys.get('detection_cam2'),
            'detection_cam3_s3_key': s3_output_keys.get('detection_cam3'),
            'status':                'success',
            'error_message':         None,
        })
        _CUSTOM_PRINT_FUNC(
            f"[Growth] Done — area={doc['area_cm2']:.3f} cm²  "
            f"height={doc['height_cm']:.3f} cm"
        )

    except Exception as e:
        doc['status']        = 'error'
        doc['error_message'] = str(e)
        _CUSTOM_PRINT_FUNC(f"[Growth] run_from_s3 failed: {e}")
        raise

    finally:
        if tmpdir and os.path.isdir(tmpdir):
            shutil.rmtree(tmpdir, ignore_errors=True)
        _analysis_lock.release()

    _mongo_db_handler.insert_growth_measurement(doc)
    doc.pop('_id', None)   # MongoDB adds ObjectId after insert — not JSON serializable
    return doc


def run_from_session_s3_keys(cam_id_to_s3_key: dict, s3_handler_ref=None) -> dict:
    """
    Run growth analysis on images that were just captured and uploaded to S3
    by capture_manager.run_full_capture_cycle().

    cam_id_to_s3_key : {camera_id (int): s3_key (str)}
        Camera IDs from the project: 1 → cam1, 2 → cam2, 4 → cam3.
    s3_handler_ref   : S3Handler instance (falls back to module-level _s3_handler).

    Downloads each S3 key to a temp dir, loads as numpy arrays, runs analysis.
    """
    handler = s3_handler_ref or _s3_handler
    if not _analysis_lock.acquire(blocking=False):
        raise RuntimeError("A growth analysis is already in progress. Please wait.")

    timestamp_label = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    output_dir      = os.path.join(os.path.dirname(__file__), 'growth_outputs', timestamp_label)
    doc             = _build_empty_doc('manual_capture')
    doc['output_folder_path'] = output_dir

    tmpdir = None
    try:
        tmpdir = tempfile.mkdtemp(prefix='growth_capture_')
        images_dict: dict[str, np.ndarray] = {}

        for cam_id, s3_key in cam_id_to_s3_key.items():
            cam_name = CAM_ID_TO_NAME.get(cam_id)
            if not cam_name:
                _CUSTOM_PRINT_FUNC(f"[Growth] Unknown camera_id {cam_id} — skipping")
                continue

            # Store source key
            doc[f'{cam_name}_s3_key'] = s3_key

            filename   = s3_key.split('/')[-1]
            local_path = os.path.join(tmpdir, f'{cam_name}_{filename}')
            handler.download_file(s3_key, local_path)

            if not os.path.isfile(local_path):
                _CUSTOM_PRINT_FUNC(f"[Growth] WARNING: Download failed for {s3_key}")
                continue

            img = cv2.imread(local_path)
            if img is not None:
                images_dict[cam_name] = img
                _CUSTOM_PRINT_FUNC(f"[Growth] Loaded {cam_name} from s3://{s3_key}")
            else:
                _CUSTOM_PRINT_FUNC(f"[Growth] WARNING: cv2 could not read {local_path}")

        if not images_dict:
            raise RuntimeError(
                "No camera images could be loaded from S3 for growth analysis"
            )

        _CUSTOM_PRINT_FUNC(f"[Growth] Analyzing cameras: {list(images_dict.keys())}")
        metrics = _run_analysis(images_dict, timestamp_label, output_dir)

        s3_output_keys = _upload_outputs(output_dir, timestamp_label)

        doc.update({
            'area_cm2':              metrics.get('area_cm2'),
            'height_cm':             metrics.get('height_cm'),
            'width_cm':              metrics.get('width_cm'),
            'depth_cm':              metrics.get('depth_cm'),
            'canopy_area_cm2':       metrics.get('canopy_area_cm2'),
            'volume_cm3':            metrics.get('volume_cm3'),
            'agr':                   metrics.get('agr'),
            'rgr':                   metrics.get('rgr'),
            'growth_pct':            metrics.get('growth%'),
            'vol_growth_pct':        metrics.get('vol_growth%'),
            'growth_chart_s3_key':   s3_output_keys.get('growth_chart'),
            'detection_cam1_s3_key': s3_output_keys.get('detection_cam1'),
            'detection_cam2_s3_key': s3_output_keys.get('detection_cam2'),
            'detection_cam3_s3_key': s3_output_keys.get('detection_cam3'),
            'status':                'success',
            'error_message':         None,
        })
        _CUSTOM_PRINT_FUNC(
            f"[Growth] Done — area={doc['area_cm2']:.3f} cm²  "
            f"height={doc['height_cm']:.3f} cm"
        )

    except Exception as e:
        doc['status']        = 'error'
        doc['error_message'] = str(e)
        _CUSTOM_PRINT_FUNC(f"[Growth] run_from_session_s3_keys failed: {e}")
        raise

    finally:
        if tmpdir and os.path.isdir(tmpdir):
            shutil.rmtree(tmpdir, ignore_errors=True)
        _analysis_lock.release()

    _mongo_db_handler.insert_growth_measurement(doc)
    doc.pop('_id', None)   # MongoDB adds ObjectId after insert — not JSON serializable
    return doc


def run_from_capture(cam_results: list) -> dict:
    """
    Run growth analysis on frames from a live camera capture session.

    cam_results: list from GH_Camera.capture_frames_base64(), each item:
        {camera_id: int, name: str, b64: str, success: bool, error: str|None}

    Camera ID mapping:  1 → cam1,  2 → cam2,  4 → cam3.

    Raises RuntimeError if another analysis is already running.
    """
    if not _analysis_lock.acquire(blocking=False):
        raise RuntimeError("A growth analysis is already in progress. Please wait.")

    timestamp_label = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    output_dir      = os.path.join(os.path.dirname(__file__), 'growth_outputs', timestamp_label)
    doc             = _build_empty_doc('manual_capture')
    doc['output_folder_path'] = output_dir

    try:
        # Decode base64 frames → numpy arrays
        images_dict: dict[str, np.ndarray] = {}
        for cam in (cam_results or []):
            if not cam.get('success') or not cam.get('b64'):
                continue
            cam_id   = cam.get('camera_id')
            cam_name = CAM_ID_TO_NAME.get(cam_id)
            if not cam_name:
                continue
            try:
                img_bytes = base64.b64decode(cam['b64'])
                arr       = np.frombuffer(img_bytes, np.uint8)
                img       = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if img is not None:
                    images_dict[cam_name] = img
                else:
                    _CUSTOM_PRINT_FUNC(f"[Growth] WARNING: imdecode failed for camera {cam_id}")
            except Exception as e:
                _CUSTOM_PRINT_FUNC(f"[Growth] WARNING: decode error camera {cam_id}: {e}")

        if not images_dict:
            raise RuntimeError("No camera frames could be decoded — cannot run analysis")

        _CUSTOM_PRINT_FUNC(f"[Growth] Analyzing live capture: {list(images_dict.keys())}")
        metrics = _run_analysis(images_dict, timestamp_label, output_dir)

        s3_output_keys = _upload_outputs(output_dir, timestamp_label)

        doc.update({
            'area_cm2':              metrics.get('area_cm2'),
            'height_cm':             metrics.get('height_cm'),
            'width_cm':              metrics.get('width_cm'),
            'depth_cm':              metrics.get('depth_cm'),
            'canopy_area_cm2':       metrics.get('canopy_area_cm2'),
            'volume_cm3':            metrics.get('volume_cm3'),
            'agr':                   metrics.get('agr'),
            'rgr':                   metrics.get('rgr'),
            'growth_pct':            metrics.get('growth%'),
            'vol_growth_pct':        metrics.get('vol_growth%'),
            'growth_chart_s3_key':   s3_output_keys.get('growth_chart'),
            'detection_cam1_s3_key': s3_output_keys.get('detection_cam1'),
            'detection_cam2_s3_key': s3_output_keys.get('detection_cam2'),
            'detection_cam3_s3_key': s3_output_keys.get('detection_cam3'),
            'status':                'success',
            'error_message':         None,
        })
        _CUSTOM_PRINT_FUNC(
            f"[Growth] Done — area={doc['area_cm2']:.3f} cm²  "
            f"height={doc['height_cm']:.3f} cm"
        )

    except Exception as e:
        doc['status']        = 'error'
        doc['error_message'] = str(e)
        _CUSTOM_PRINT_FUNC(f"[Growth] run_from_capture failed: {e}")
        raise

    finally:
        _analysis_lock.release()

    _mongo_db_handler.insert_growth_measurement(doc)
    doc.pop('_id', None)   # MongoDB adds ObjectId after insert — not JSON serializable
    return doc
