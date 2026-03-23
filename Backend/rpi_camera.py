try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False
    print("Warning: picamera2 not available. RPi CSI camera will not work.")

import time
import datetime
import os
import cv2
import numpy as np
from utils.utils import _CUSTOM_PRINT_FUNC

class GH_Camera:
    def __init__(self):
        self.__last_path = ""
        self.__camera_USB = None
        self.__camera_RPi = None
        self.__camera_USB2 = None  # Third camera (USB camera 2)
        self.usb_cam_mod = None

    # def capture_store_image(self, image_num = 0, cam_id=0, usb_cam=False):
    #     try:
    #         if usb_cam:
    #             self.__last_path = f"{image_num}_1_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.jpg"
    #         else:
    #             self.__last_path = f"{image_num}_2_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.jpg"

    #         if usb_cam:
    #             self.capture_image_from_usb_cam(self.__last_path)
    #             _CUSTOM_PRINT_FUNC(f"Image captured from USB camera and saved as '{self.__last_path}'.")
    #             return self.__last_path
    #         else:
    #             with picamera2.Picamera2(cam_id) as camera:
    #                 # configure the resolution
    #                 # config = camera.create_still_configuration(
    #                 #     main={"size": (1920, 1080), "format": "RGB888"},
    #                 #     controls={
    #                 #         "ExposureTime": 10000,       # Adjust based on lighting
    #                 #         "AnalogueGain": 1.0,         # Keep low to reduce noise
    #                 #         "AwbMode": "auto",           # Or try "tungsten", "sunlight", etc.
    #                 #         "Sharpness": 1.0,            # Boosts edge clarity
    #                 #         "Contrast": 1.0,             # Enhances detail separation
    #                 #     }
    #                 # )
    #                 # camera.configure(config)
    #                 camera.start()
    #                 camera.capture_file(self.__last_path)
    #                 _CUSTOM_PRINT_FUNC(f"Image captured and saved as '{self.__last_path}'.")
    #                 camera.stop()
    #             return self.__last_path
    #     except Exception as e:
    #         _CUSTOM_PRINT_FUNC(f"Error capturing image: {e}")
    #         return None

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

    def capture_image_from_usb_cam(self, path="_cam.jpg"):
        cap = cv2.VideoCapture(0)  # Replace 2 with your actual USB cam device number
        ret, frame = cap.read()
        cv2.imwrite(path, frame)
        cap.release()

    def init_USB_camera_for_streaming(self, cam_id=0, resolution=(1280, 720)):
        """Initialize USB Camera 1 (Integrated Camera on /dev/video0)"""
        try:
            # Stop any existing camera instance first
            if self.__camera_USB:
                self.stop_camera_USB()

            _CUSTOM_PRINT_FUNC(f"Attempting to open Integrated Camera on device {cam_id}...")
            self.__camera_USB = cv2.VideoCapture(cam_id)

            if not self.__camera_USB.isOpened():
                raise Exception(f"Could not open Integrated Camera (device {cam_id}).")

            self.__camera_USB.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
            self.__camera_USB.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])
            _CUSTOM_PRINT_FUNC(f"Integrated Camera initialized for streaming with resolution {resolution}.")
            time.sleep(2)
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error initializing Integrated Camera: {e}")
            return False
        
    def init_RPi_camera_for_streaming(self, cam_id=0, resolution=(1080, 720)):
        try:
            if not PICAMERA2_AVAILABLE:
                _CUSTOM_PRINT_FUNC("Error: picamera2 library not available")
                return False

            # Stop any existing camera instance first
            if self.__camera_RPi:
                self.stop_camera_RPi()

            # For PiCamera2
            camera = Picamera2(cam_id)
            config = camera.create_video_configuration(
                main={"size": resolution},
                controls={"FrameRate": 15},
                encode="main"
            )
            camera.configure(config)
            camera.start()
            self.__camera_RPi = camera
            _CUSTOM_PRINT_FUNC(f"PiCamera initialized for streaming with resolution {resolution}.")
            time.sleep(2)
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error initializing RPi camera: {e}")
            return False

    def generate_video_stream_camera_RPi(self):
        # Try picamera2 (CSI camera) first, fallback to 4k USB on /dev/video1
        if self.__camera_RPi is None:
            if PICAMERA2_AVAILABLE:
                success = self.init_RPi_camera_for_streaming(cam_id=0, resolution=(640, 480))
            else:
                success = False

            if not success:
                # No CSI camera — fall back to 4k USB Camera on /dev/video2
                _CUSTOM_PRINT_FUNC("No CSI camera found. Using 4k USB Camera on /dev/video2 for Camera 2 stream.")
                try:
                    self.__camera_RPi = cv2.VideoCapture(2)
                    if not self.__camera_RPi.isOpened():
                        _CUSTOM_PRINT_FUNC("Cannot open camera device 1")
                        self.__camera_RPi = None
                        return
                    self.__camera_RPi.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                    self.__camera_RPi.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                    _CUSTOM_PRINT_FUNC("Camera 2 (4k USB /dev/video1) initialized for streaming.")
                    time.sleep(1)
                except Exception as e:
                    _CUSTOM_PRINT_FUNC(f"Error initializing camera 2 fallback: {e}")
                    self.__camera_RPi = None
                    return

        if self.__camera_RPi is None:
            _CUSTOM_PRINT_FUNC("Camera 2 is not initialized.")
            return

        # Stream frames — works for both picamera2 and OpenCV
        while True:
            try:
                if PICAMERA2_AVAILABLE and isinstance(self.__camera_RPi, Picamera2):
                    frame = self.__camera_RPi.capture_array()
                else:
                    ret, frame = self.__camera_RPi.read()
                    if not ret:
                        _CUSTOM_PRINT_FUNC("Failed to read frame from camera 2")
                        continue
                _, buffer = cv2.imencode('.jpg', frame)
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            except Exception as e:
                _CUSTOM_PRINT_FUNC(f"Streaming error (camera 2): {e}")
                break


    def generate_video_stream_camera_USB(self):
        if self.__camera_USB is None:
            self.init_USB_camera_for_streaming(cam_id=0)  # 2k USB Camera on /dev/video0

        if self.__camera_USB is None:
            _CUSTOM_PRINT_FUNC("Integrated Camera is not initialized.")
            return
        while True:
            try:
                ret, frame = self.__camera_USB.read()
                if not ret:
                    _CUSTOM_PRINT_FUNC("Failed to read frame from camera.")
                    continue
                _, buffer = cv2.imencode('.jpg', frame)
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            except Exception as e:
                _CUSTOM_PRINT_FUNC(f"Streaming error (camera 2): {e}")
                break

    def stop_camera_RPi(self):
        try:
            if self.__camera_RPi is not None:
                if not PICAMERA2_AVAILABLE:
                    # Using OpenCV VideoCapture - use release()
                    self.__camera_RPi.release()
                    time.sleep(1)
                    self.__camera_RPi = None
                    _CUSTOM_PRINT_FUNC("Camera 1 (USB device 1) stopped.")
                else:
                    # Using picamera2
                    self.__camera_RPi.stop()
                    time.sleep(1)
                    self.__camera_RPi.close()
                    self.__camera_RPi = None
                    _CUSTOM_PRINT_FUNC("RPi Camera stopped.")
            else:
                _CUSTOM_PRINT_FUNC("No camera to stop.")
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error stopping camera 1: {e}")

    def stop_camera_USB(self):
        try:
            if self.__camera_USB is not None:
                self.__camera_USB.release()
                time.sleep(1)
                self.__camera_USB = None
                _CUSTOM_PRINT_FUNC("USB Camera stopped.")
            else:
                _CUSTOM_PRINT_FUNC("No camera to stop.")
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error stopping camera 2: {e}")

    # ==================== CAMERA 3 (USB Camera 2) ====================

    def init_USB_camera2_for_streaming(self, cam_id=2, resolution=(1280, 720)):
        """Initialize the third camera (USB device 2) for streaming"""
        try:
            # Stop any existing camera instance first
            if self.__camera_USB2:
                self.stop_camera_USB2()

            _CUSTOM_PRINT_FUNC(f"Attempting to open USB camera 2 (device {cam_id})...")
            self.__camera_USB2 = cv2.VideoCapture(cam_id)

            # If camera 2 fails, try camera 3
            if not self.__camera_USB2.isOpened() and cam_id == 2:
                _CUSTOM_PRINT_FUNC("Camera 2 failed, trying camera 3...")
                self.__camera_USB2 = cv2.VideoCapture(3)
                if self.__camera_USB2.isOpened():
                    _CUSTOM_PRINT_FUNC("Using camera device 3 instead")

            if not self.__camera_USB2.isOpened():
                raise Exception(f"Could not open USB camera 2 (device {cam_id}).")

            self.__camera_USB2.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
            self.__camera_USB2.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])
            _CUSTOM_PRINT_FUNC(f"USB Camera 2 initialized for streaming with resolution {resolution}.")
            time.sleep(2)
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error initializing USB camera 2: {e}")
            return False

    def generate_video_stream_camera_USB2(self):
        """Generate video stream from the Integrated USB camera (/dev/video4)"""
        if self.__camera_USB2 is None:
            self.init_USB_camera2_for_streaming(cam_id=4)

        if self.__camera_USB2 is None:
            _CUSTOM_PRINT_FUNC("Integrated Camera (C3) is not initialized.")
            return

        while True:
            try:
                ret, frame = self.__camera_USB2.read()
                if not ret:
                    _CUSTOM_PRINT_FUNC("Failed to read frame from Integrated Camera.")
                    continue
                _, buffer = cv2.imencode('.jpg', frame)
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            except Exception as e:
                _CUSTOM_PRINT_FUNC(f"Streaming error (Integrated Camera): {e}")
                break

    def stop_camera_USB2(self):
        """Stop the third camera (USB device 2)"""
        try:
            if self.__camera_USB2 is not None:
                self.__camera_USB2.release()
                time.sleep(1)
                self.__camera_USB2 = None
                _CUSTOM_PRINT_FUNC("USB Camera 2 (Camera 3) stopped.")
            else:
                _CUSTOM_PRINT_FUNC("No camera 3 to stop.")
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error stopping camera 3: {e}")
