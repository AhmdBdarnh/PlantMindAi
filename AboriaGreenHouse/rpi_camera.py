# import picamera2
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
        try:
            # Stop any existing camera instance first
            if cam_id == 0 and self.__camera_USB:
                self.stop_camera_2()

            # For USB Camera
            self.__camera_USB = cv2.VideoCapture(cam_id)
            if not self.__camera_USB.isOpened():
                raise Exception("Could not open USB camera.")
            self.__camera_USB.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
            self.__camera_USB.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])
            _CUSTOM_PRINT_FUNC(f"USB Camera initialized for streaming with resolution {resolution}.")
            time.sleep(2)
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error initializing USB camera: {e}")
            return False
        
    def init_RPi_camera_for_streaming(self, cam_id=0, resolution=(1080, 720)):
        try:
            # Stop any existing camera instance first
            if cam_id == 0 and self.__camera_RPi:
                self.stop_camera_1()
            elif cam_id == 0 and self.__camera_RPi:
                self.stop_camera_2()

            # For PiCamera2
            camera = picamera2.Picamera2(cam_id)
            config = camera.create_video_configuration(
                main={"size": resolution},
                controls={"FrameRate": 15},
                encode="main"
            )
            camera.configure(config)
            camera.start()
            if cam_id == 0:
                self.__camera_RPi = camera
            else:
                self.__camera_USB = camera
            _CUSTOM_PRINT_FUNC(f"PiCamera {cam_id+1} initialized for streaming with resolution {resolution}.")
            time.sleep(2)
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error initializing camera {cam_id+1}: {e}")
            return False

    def generate_video_stream_camera_RPi(self):
        if self.__camera_RPi is None:
            self.init_RPi_camera_for_streaming(cam_id=0, resolution=(640, 480)) # id = 0

        if self.__camera_RPi is None:
            _CUSTOM_PRINT_FUNC("Camera 1 is not initialized.")
            return

        while True:
            try:
                frame = self.__camera_RPi.capture_array()
                _, buffer = cv2.imencode('.jpg', frame)
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            except Exception as e:
                _CUSTOM_PRINT_FUNC(f"Streaming error (camera 1): {e}")
                break


    def generate_video_stream_camera_USB(self):
        if self.__camera_USB is None:
            self.init_USB_camera_for_streaming(cam_id=0) # id = 0, usb_cam = False

        if self.__camera_USB is None:
            _CUSTOM_PRINT_FUNC("Camera 2 is not initialized.")
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
