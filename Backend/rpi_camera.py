try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
except Exception:
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
    Scan /dev/video0–/dev/video9 via v4l2-ctl and return the device index
    whose Card type contains name_pattern (case-insensitive).
    Prefers even-numbered nodes (main capture) over odd ones (metadata).
    Returns None if not found.
    Scans only video0-9 to avoid slow queries on the 15+ pisp backend nodes.
    """
    candidates = []
    for path in sorted(glob.glob('/dev/video[0-9]')):
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


# ==================== PERSISTENT FRAME GRABBERS ====================

class _USBGrabber:
    """
    Background thread: keeps one USB camera open and continuously stores the
    latest frame as JPEG. As simple as possible — no format flags, no locks.
    """

    def __init__(self, dev_idx):
        self._dev = dev_idx
        self._jpeg = None
        self._lock = threading.Lock()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while True:

            cap = cv2.VideoCapture(self._dev)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            if not cap.isOpened():
                cap.release()
                time.sleep(2)
                continue
            consecutive_failures = 0
            while consecutive_failures < 30:
                ret, frame = cap.read()
                if not ret or frame is None:
                    consecutive_failures += 1
                    time.sleep(0.1)
                    continue
                consecutive_failures = 0
                _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                with self._lock:
                    self._jpeg = buf.tobytes()
            cap.release()
            time.sleep(1)

    def get_jpeg(self) -> "bytes | None":
        with self._lock:
            return self._jpeg




# ==================== MAIN CAMERA CLASS ====================

class GH_Camera:
    """
    Stateless camera handler for scheduled image capture.
    Live polling uses persistent grabber threads (real-time, no open/close overhead).
    Scheduled high-res captures use per-device open/close with the capture lock.
    """

    def __init__(self):
        self.__last_path = ""
        self._capture_lock = threading.Lock()

        # Persistent grabbers — device indices confirmed via v4l2-ctl --list-devices:
        #   Camera 1: 2K USB Camera  → /dev/video2
        #   Camera 2: 4K USB Camera  → /dev/video4
        #   Camera 3: Integrated     → /dev/video0
        self._grabber1 = _USBGrabber(2)
        self._grabber2 = _USBGrabber(4)
        self._grabber3 = _USBGrabber(0)

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
        Grab the latest frame from each live grabber and return as base64 JPEG.
        No device open/close — grabbers already keep cameras open continuously.
        Returns a list of 3 dicts (one per camera).
        """
        configs = [
            (1, self._grabber1, '2K USB Camera'),
            (2, self._grabber2, '4K USB Camera'),
            (3, self._grabber3, 'Integrated Camera'),
        ]
        results = []
        for cam_id, grabber, name in configs:
            jpeg = grabber.get_jpeg()
            if jpeg:
                results.append({
                    'camera_id': cam_id,
                    'name': name,
                    'b64': base64.b64encode(jpeg).decode('utf-8'),
                    'success': True,
                    'error': None,
                })
                _CUSTOM_PRINT_FUNC(f"[Camera {cam_id}] Capture OK ({len(jpeg)//1024}KB)")
            else:
                results.append({
                    'camera_id': cam_id,
                    'name': name,
                    'b64': None,
                    'success': False,
                    'error': 'No frame available — camera may still be initializing',
                })
                _CUSTOM_PRINT_FUNC(f"[Camera {cam_id}] No frame available yet")

        successful = sum(1 for r in results if r['success'])
        _CUSTOM_PRINT_FUNC(f"[Camera] Capture complete: {successful}/3 cameras")
        return results

    # ==================== SINGLE-FRAME ENDPOINT (real-time polling) ====================

    def get_frame_jpeg(self, cam_id: int) -> "bytes | None":
        """
        Return the latest JPEG frame from the persistent grabber for the given camera.
        Near-instant — no camera open/close overhead. Used by the live cams polling endpoint.
        """
        try:
            if cam_id == 1:
                return self._grabber1.get_jpeg()
            elif cam_id == 2:
                return self._grabber2.get_jpeg()
            elif cam_id == 3:
                return self._grabber3.get_jpeg()
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[Camera {cam_id}] get_frame_jpeg error: {e}")
        return None

    # ==================== MJPEG LIVE STREAM GENERATORS ====================

    def _mjpeg_usb_generator(self, device_idx, width=640, height=480):
        cap = None
        try:
            cap = cv2.VideoCapture(device_idx, cv2.CAP_V4L2)
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH,  width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            while True:
                if self._capture_lock.locked():
                    cap.release()
                    time.sleep(0.5)
                    cap = cv2.VideoCapture(device_idx, cv2.CAP_V4L2)
                    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  width)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                    continue
                ret, frame = cap.read()
                if not ret or frame is None:
                    time.sleep(0.1)
                    continue
                _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'
                       + buf.tobytes() + b'\r\n')
        except GeneratorExit:
            pass
        finally:
            if cap is not None:
                cap.release()

    def _mjpeg_picamera_generator(self, cam_id=0, width=640, height=480):
        if not PICAMERA2_AVAILABLE:
            dev = _find_camera_device('4k usb') or 4
            yield from self._mjpeg_usb_generator(dev, width, height)
            return
        cam = None
        try:
            cam = Picamera2(cam_id)
            config = cam.create_video_configuration(
                main={"size": (width, height), "format": "RGB888"}
            )
            cam.configure(config)
            cam.start()
            while True:
                if self._capture_lock.locked():
                    time.sleep(0.3)
                    continue
                frame = cam.capture_array()
                if frame is None:
                    time.sleep(0.05)
                    continue
                bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                _, buf = cv2.imencode('.jpg', bgr, [cv2.IMWRITE_JPEG_QUALITY, 70])
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'
                       + buf.tobytes() + b'\r\n')
        except GeneratorExit:
            pass
        finally:
            if cam is not None:
                try: cam.stop()
                except Exception: pass
                try: cam.close()
                except Exception: pass

    def stream_camera_1(self):
        dev = _find_camera_device('2k usb') or 2
        return self._mjpeg_usb_generator(dev)

    def stream_camera_2(self):
        return self._mjpeg_picamera_generator(cam_id=0)

    def stream_camera_3(self):
        dev = _find_camera_device('integrated') or 0
        return self._mjpeg_usb_generator(dev)
