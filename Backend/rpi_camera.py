try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False
    print("Warning: picamera2 not available. RPi CSI camera will not work.")

import time
import datetime
import os
import glob
import base64
import subprocess
import threading
import cv2
import numpy as np
from utils.utils import _CUSTOM_PRINT_FUNC


def _find_camera_device(name_pattern: str) -> int:
    """
    Scan all /dev/video* devices via v4l2-ctl and return the device index
    whose Card type contains name_pattern (case-insensitive).
    Prefers even-numbered nodes (main capture) over odd ones (metadata).
    Returns None if not found.
    """
    candidates = []
    for path in sorted(glob.glob('/dev/video*')):
        try:
            idx = int(path.replace('/dev/video', ''))
        except ValueError:
            continue
        try:
            result = subprocess.run(
                ['v4l2-ctl', '--device', path, '--info'],
                capture_output=True, text=True, timeout=2
            )
            if name_pattern.lower() in result.stdout.lower():
                candidates.append(idx)
        except Exception:
            pass
    if not candidates:
        return None
    even = [c for c in candidates if c % 2 == 0]
    return even[0] if even else candidates[0]


class GH_Camera:
    """
    Stateless camera handler for scheduled image capture.
    No persistent camera connections are kept open between captures.
    Each capture opens the device, reads frames, then releases it.
    A per-instance lock prevents concurrent captures from conflicting.
    """

    def __init__(self):
        self.__last_path = ""
        # Global lock to prevent concurrent captures across all cameras
        self._capture_lock = threading.Lock()

    def remove_image(self, path=None):
        try:
            if path:
                self.__last_path = path
            if self.__last_path:
                os.remove(self.__last_path)
                _CUSTOM_PRINT_FUNC(f"Image '{self.__last_path}' removed.")
            else:
                _CUSTOM_PRINT_FUNC("No image to remove.")
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error removing image: {e}")

    # ==================== LOW-LEVEL CAPTURE HELPERS ====================

    def _capture_usb_frame(self, device_idx: int, resolution=(1280, 720), retries=2) -> "np.ndarray | None":
        """
        Open a USB VideoCapture at device_idx, discard warmup frames,
        read one good frame, release the device. Returns frame or None.
        Retries up to `retries` times with a short delay between attempts.
        """
        for attempt in range(retries):
            cap = None
            try:
                cap = cv2.VideoCapture(device_idx, cv2.CAP_V4L2)
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])
                if not cap.isOpened():
                    raise Exception(f"/dev/video{device_idx} could not be opened")
                # Discard warmup frames so the sensor has time to adjust
                for _ in range(5):
                    cap.read()
                ret, frame = cap.read()
                if ret and frame is not None and frame.size > 0:
                    return frame
                raise Exception("Empty or invalid frame returned")
            except Exception as e:
                _CUSTOM_PRINT_FUNC(
                    f"[Camera] USB /dev/video{device_idx} attempt {attempt + 1}/{retries} failed: {e}"
                )
                if attempt < retries - 1:
                    time.sleep(1.5)
            finally:
                if cap is not None:
                    try:
                        cap.release()
                    except Exception:
                        pass
        return None

    def _capture_picamera_frame(self, cam_id=0, resolution=(1280, 720), retries=2) -> "np.ndarray | None":
        """
        Capture a single frame from the RPi CSI camera using picamera2.
        Opens, captures, closes. Returns frame or None.
        """
        if not PICAMERA2_AVAILABLE:
            return None
        for attempt in range(retries):
            cam = None
            try:
                cam = Picamera2(cam_id)
                config = cam.create_still_configuration(main={"size": resolution})
                cam.configure(config)
                cam.start()
                time.sleep(0.5)  # Allow sensor to settle
                frame = cam.capture_array()
                if frame is not None and frame.size > 0:
                    return frame
                raise Exception("Empty frame from picamera2")
            except Exception as e:
                _CUSTOM_PRINT_FUNC(
                    f"[Camera] PiCamera cam_id={cam_id} attempt {attempt + 1}/{retries} failed: {e}"
                )
                if attempt < retries - 1:
                    time.sleep(1.5)
            finally:
                if cam is not None:
                    try:
                        cam.stop()
                    except Exception:
                        pass
                    try:
                        cam.close()
                    except Exception:
                        pass
        return None

    def _encode_frame_b64(self, frame) -> str:
        """Encode an OpenCV/numpy frame to a base64 JPEG string."""
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        return base64.b64encode(buffer.tobytes()).decode('utf-8')

    # ==================== MAIN CAPTURE METHOD ====================

    def capture_frames_base64(self) -> list:
        """
        Capture one frame from each of the 3 cameras independently.
        Returns a list of 3 dicts (one per camera):
            {
                'camera_id': int,      # 1, 2, or 3
                'name': str,           # Human-readable camera name
                'b64': str | None,     # Base64 JPEG string, or None on failure
                'success': bool,
                'error': str | None,   # Error message if not successful
            }
        If one camera fails, its entry has success=False and the others continue.
        A lock prevents concurrent invocations from interfering with each other.
        """
        results = []

        with self._capture_lock:

            # ---- Camera 1: 2K USB Camera ----------------------------------------
            cam1 = {
                'camera_id': 1,
                'name': '2K USB Camera',
                'b64': None,
                'success': False,
                'error': None,
            }
            try:
                dev1 = _find_camera_device('2k usb')
                if dev1 is None:
                    dev1 = 0
                    _CUSTOM_PRINT_FUNC("[Camera 1] '2k usb' not found via v4l2, trying /dev/video0")
                frame = self._capture_usb_frame(dev1)
                # Fallback to device 0 if auto-discovered device fails and isn't already 0
                if frame is None and dev1 != 0:
                    _CUSTOM_PRINT_FUNC(f"[Camera 1] /dev/video{dev1} failed, falling back to /dev/video0")
                    frame = self._capture_usb_frame(0)
                if frame is not None:
                    cam1['b64'] = self._encode_frame_b64(frame)
                    cam1['success'] = True
                    _CUSTOM_PRINT_FUNC(f"[Camera 1] Capture OK from /dev/video{dev1}")
                else:
                    cam1['error'] = f"All attempts failed for Camera 1 (tried /dev/video{dev1})"
                    _CUSTOM_PRINT_FUNC(f"[Camera 1] {cam1['error']}")
            except Exception as e:
                cam1['error'] = str(e)
                _CUSTOM_PRINT_FUNC(f"[Camera 1] Unexpected error: {e}")
            results.append(cam1)

            # ---- Camera 2: RPi CSI camera (fallback: 4K USB) --------------------
            cam2 = {
                'camera_id': 2,
                'name': 'RPi/4K Camera',
                'b64': None,
                'success': False,
                'error': None,
            }
            try:
                frame = None
                if PICAMERA2_AVAILABLE:
                    _CUSTOM_PRINT_FUNC("[Camera 2] Trying RPi CSI camera via picamera2...")
                    frame = self._capture_picamera_frame(0)
                if frame is None:
                    dev2 = _find_camera_device('4k usb')
                    if dev2 is None:
                        dev2 = 2
                        _CUSTOM_PRINT_FUNC("[Camera 2] '4k usb' not found via v4l2, trying /dev/video2")
                    _CUSTOM_PRINT_FUNC(f"[Camera 2] Trying 4K USB on /dev/video{dev2}...")
                    frame = self._capture_usb_frame(dev2, resolution=(1280, 720))
                if frame is not None:
                    cam2['b64'] = self._encode_frame_b64(frame)
                    cam2['success'] = True
                    _CUSTOM_PRINT_FUNC("[Camera 2] Capture OK")
                else:
                    cam2['error'] = "Camera 2 failed: CSI unavailable and 4K USB capture failed"
                    _CUSTOM_PRINT_FUNC(f"[Camera 2] {cam2['error']}")
            except Exception as e:
                cam2['error'] = str(e)
                _CUSTOM_PRINT_FUNC(f"[Camera 2] Unexpected error: {e}")
            results.append(cam2)

            # ---- Camera 3: Integrated Camera ------------------------------------
            cam3 = {
                'camera_id': 3,
                'name': 'Integrated Camera',
                'b64': None,
                'success': False,
                'error': None,
            }
            try:
                dev3 = _find_camera_device('integrated')
                if dev3 is None:
                    dev3 = 5
                    _CUSTOM_PRINT_FUNC("[Camera 3] 'integrated' not found via v4l2, trying /dev/video5")
                frame = self._capture_usb_frame(dev3, resolution=(1280, 720))
                if frame is not None:
                    cam3['b64'] = self._encode_frame_b64(frame)
                    cam3['success'] = True
                    _CUSTOM_PRINT_FUNC(f"[Camera 3] Capture OK from /dev/video{dev3}")
                else:
                    cam3['error'] = f"All attempts failed for Camera 3 (tried /dev/video{dev3})"
                    _CUSTOM_PRINT_FUNC(f"[Camera 3] {cam3['error']}")
            except Exception as e:
                cam3['error'] = str(e)
                _CUSTOM_PRINT_FUNC(f"[Camera 3] Unexpected error: {e}")
            results.append(cam3)

        successful = sum(1 for r in results if r['success'])
        _CUSTOM_PRINT_FUNC(
            f"[Camera] Capture cycle complete: {successful}/3 cameras successful"
        )
        return results
