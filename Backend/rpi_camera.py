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
        self.__camera_2K = None  # New 2K USB camera (device 5)
        self.__camera_4K = None  # 4K USB camera (device 2)
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

            # Try the specified camera ID first, fallback to 1 if 0 fails
            _CUSTOM_PRINT_FUNC(f"Attempting to open camera {cam_id}...")
            self.__camera_USB = cv2.VideoCapture(cam_id)

            # If camera 0 fails, try camera 1
            if not self.__camera_USB.isOpened() and cam_id == 0:
                _CUSTOM_PRINT_FUNC("Camera 0 failed, trying camera 1...")
                self.__camera_USB = cv2.VideoCapture(1)
                if self.__camera_USB.isOpened():
                    _CUSTOM_PRINT_FUNC("Using camera 1 instead")

            if not self.__camera_USB.isOpened():
                raise Exception(f"Could not open USB camera {cam_id}.")

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
            if not PICAMERA2_AVAILABLE:
                _CUSTOM_PRINT_FUNC("Error: picamera2 library not available")
                return False

            # Stop any existing camera instance first
            if cam_id == 0 and self.__camera_RPi:
                self.stop_camera_1()
            elif cam_id == 0 and self.__camera_RPi:
                self.stop_camera_2()

            # For PiCamera2
            camera = Picamera2(cam_id)
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
        """
        Generate video stream for Camera 2
        Now uses the new 2K USB camera on /dev/video5
        """
        # Use the new 2K camera for Camera 2
        _CUSTOM_PRINT_FUNC("Using 2K USB camera (device 5) for Camera 2 stream")

        return self.generate_video_stream_camera_2K()


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

    # ==================== NEW 4K CAMERA METHODS ====================

    def init_4K_camera_for_streaming(self, cam_id=2, resolution=(1920, 1080)):
        """
        Initialize the 4K USB Camera (Redeagle) for streaming

        Args:
            cam_id: Camera device ID (default: 2 for the 4K camera)
            resolution: Desired resolution (default: 1920x1080 for Full HD)
                       Supports up to 2592x1944 (5MP)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Stop any existing camera instance first
            if self.__camera_4K:
                self.stop_camera_4K()

            _CUSTOM_PRINT_FUNC(f"Initializing 4K camera on device {cam_id}...")
            self.__camera_4K = cv2.VideoCapture(cam_id)

            if not self.__camera_4K.isOpened():
                raise Exception(f"Could not open 4K camera on device {cam_id}.")

            # Set resolution
            self.__camera_4K.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
            self.__camera_4K.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])

            # Optional: Set additional camera parameters for better quality
            self.__camera_4K.set(cv2.CAP_PROP_AUTOFOCUS, 1)  # Enable autofocus
            self.__camera_4K.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)  # Enable auto exposure

            # Get actual resolution
            actual_width = int(self.__camera_4K.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.__camera_4K.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = self.__camera_4K.get(cv2.CAP_PROP_FPS)

            _CUSTOM_PRINT_FUNC(f"4K Camera initialized successfully!")
            _CUSTOM_PRINT_FUNC(f"  Resolution: {actual_width}x{actual_height}")
            _CUSTOM_PRINT_FUNC(f"  FPS: {fps}")

            time.sleep(2)  # Allow camera to warm up
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error initializing 4K camera: {e}")
            return False

    def generate_video_stream_camera_4K(self):
        """
        Generate video stream from the 4K camera for web streaming
        Yields JPEG frames in multipart format
        """
        if self.__camera_4K is None:
            # Initialize with 720p for better streaming performance
            self.init_4K_camera_for_streaming(cam_id=2, resolution=(1280, 720))

        if self.__camera_4K is None:
            _CUSTOM_PRINT_FUNC("4K Camera is not initialized.")
            return

        while True:
            try:
                ret, frame = self.__camera_4K.read()
                if not ret:
                    _CUSTOM_PRINT_FUNC("Failed to read frame from 4K camera.")
                    continue

                # Encode frame as JPEG
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                frame_bytes = buffer.tobytes()

                # Yield frame in HTTP multipart format
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            except Exception as e:
                _CUSTOM_PRINT_FUNC(f"Streaming error (4K camera): {e}")
                break

    def capture_image_4K(self, path="4k_capture.jpg", resolution=(2592, 1944)):
        """
        Capture a high-resolution image from the 4K camera

        Args:
            path: File path to save the image
            resolution: Capture resolution (default: full 5MP resolution)

        Returns:
            Path to the saved image, or None if failed
        """
        try:
            _CUSTOM_PRINT_FUNC(f"Capturing image from 4K camera at {resolution[0]}x{resolution[1]}...")

            # Create temporary capture object for high-res photo
            cap = cv2.VideoCapture(2)
            if not cap.isOpened():
                raise Exception("Could not open 4K camera for capture.")

            # Set high resolution
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])

            # Allow camera to adjust
            time.sleep(1)

            # Capture frame
            ret, frame = cap.read()
            cap.release()

            if not ret:
                raise Exception("Failed to capture frame.")

            # Save image
            cv2.imwrite(path, frame)
            actual_size = frame.shape
            _CUSTOM_PRINT_FUNC(f"Image captured successfully: {path}")
            _CUSTOM_PRINT_FUNC(f"  Resolution: {actual_size[1]}x{actual_size[0]}")

            return path
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error capturing 4K image: {e}")
            return None

    def stop_camera_4K(self):
        """Stop the 4K camera"""
        try:
            if self.__camera_4K is not None:
                self.__camera_4K.release()
                time.sleep(1)
                self.__camera_4K = None
                _CUSTOM_PRINT_FUNC("4K Camera stopped.")
            else:
                _CUSTOM_PRINT_FUNC("No 4K camera to stop.")
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error stopping 4K camera: {e}")

    # ==================== NEW 2K CAMERA METHODS ====================

    def init_2K_camera_for_streaming(self, cam_id=4, resolution=(1920, 1080)):
        """
        Initialize the 2K USB Camera (Redeagle) for streaming

        Args:
            cam_id: Camera device ID (default: 5 for the 2K camera)
            resolution: Desired resolution (default: 1920x1080 for Full HD)
                       Supports up to 2560x1440 (2K)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Stop any existing camera instance first
            if self.__camera_2K:
                self.stop_camera_2K()

            _CUSTOM_PRINT_FUNC(f"Initializing 2K camera on device {cam_id}...")
            self.__camera_2K = cv2.VideoCapture(cam_id)

            if not self.__camera_2K.isOpened():
                raise Exception(f"Could not open 2K camera on device {cam_id}.")

            # Set resolution
            self.__camera_2K.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
            self.__camera_2K.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])

            # Optional: Set additional camera parameters for better quality
            self.__camera_2K.set(cv2.CAP_PROP_AUTOFOCUS, 1)  # Enable autofocus
            self.__camera_2K.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)  # Enable auto exposure

            # Get actual resolution
            actual_width = int(self.__camera_2K.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.__camera_2K.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = self.__camera_2K.get(cv2.CAP_PROP_FPS)

            _CUSTOM_PRINT_FUNC(f"2K Camera initialized successfully!")
            _CUSTOM_PRINT_FUNC(f"  Resolution: {actual_width}x{actual_height}")
            _CUSTOM_PRINT_FUNC(f"  FPS: {fps}")

            time.sleep(2)  # Allow camera to warm up
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error initializing 2K camera: {e}")
            return False

    def generate_video_stream_camera_2K(self):
        """
        Generate video stream from the 2K camera for web streaming
        Yields JPEG frames in multipart format
        """
        if self.__camera_2K is None:
            # Initialize with 1080p for good streaming quality
            self.init_2K_camera_for_streaming(cam_id=4, resolution=(1920, 1080))

        if self.__camera_2K is None:
            _CUSTOM_PRINT_FUNC("2K Camera is not initialized.")
            return

        while True:
            try:
                ret, frame = self.__camera_2K.read()
                if not ret:
                    _CUSTOM_PRINT_FUNC("Failed to read frame from 2K camera.")
                    continue

                # Encode frame as JPEG
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                frame_bytes = buffer.tobytes()

                # Yield frame in HTTP multipart format
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            except Exception as e:
                _CUSTOM_PRINT_FUNC(f"Streaming error (2K camera): {e}")
                break

    def capture_image_2K(self, path="2k_capture.jpg", resolution=(2560, 1440)):
        """
        Capture a high-resolution image from the 2K camera

        Args:
            path: File path to save the image
            resolution: Capture resolution (default: full 2K resolution)

        Returns:
            Path to the saved image, or None if failed
        """
        try:
            _CUSTOM_PRINT_FUNC(f"Capturing image from 2K camera at {resolution[0]}x{resolution[1]}...")

            # Create temporary capture object for high-res photo
            cap = cv2.VideoCapture(4)
            if not cap.isOpened():
                raise Exception("Could not open 2K camera for capture.")

            # Set high resolution
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])

            # Allow camera to adjust
            time.sleep(1)

            # Capture frame
            ret, frame = cap.read()
            cap.release()

            if not ret:
                raise Exception("Failed to capture frame.")

            # Save image
            cv2.imwrite(path, frame)
            actual_size = frame.shape
            _CUSTOM_PRINT_FUNC(f"Image captured successfully: {path}")
            _CUSTOM_PRINT_FUNC(f"  Resolution: {actual_size[1]}x{actual_size[0]}")

            return path
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error capturing 2K image: {e}")
            return None

    def stop_camera_2K(self):
        """Stop the 2K camera"""
        try:
            if self.__camera_2K is not None:
                self.__camera_2K.release()
                time.sleep(1)
                self.__camera_2K = None
                _CUSTOM_PRINT_FUNC("2K Camera stopped.")
            else:
                _CUSTOM_PRINT_FUNC("No 2K camera to stop.")
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error stopping 2K camera: {e}")

    def get_available_cameras(self):
        """
        Get list of available cameras
        Returns dict with camera info
        """
        cameras = {
            "camera_1": {
                "name": "Integrated Camera",
                "device": "/dev/video1",
                "type": "USB",
                "max_resolution": "1280x720",
                "status": "available"
            },
            "camera_4": {
                "name": "2K USB Camera (Redeagle)",
                "device": "/dev/video4",
                "type": "USB",
                "max_resolution": "2560x1440",
                "status": "available"
            },
            "camera_2": {
                "name": "4K USB Camera (Redeagle)",
                "device": "/dev/video2",
                "type": "USB",
                "max_resolution": "2592x1944",
                "status": "available"
            }
        }
        return cameras
