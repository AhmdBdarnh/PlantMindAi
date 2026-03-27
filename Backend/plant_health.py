import os
import base64
import datetime
import requests
import cv2

HEALTH_DETAILS = "local_name,description,url,treatment,classification,common_names,cause"


class PlantHealthChecker:
    def __init__(self, api_key=None):
        self._api_key = api_key or os.environ.get(
            'PLANT_ID_API_KEY', 'DR11O5JkxLSLvbB4eINRfHnYm0c8hPzhKfWvccngbh2uzcrc4y'
        )
        _base_url = os.environ.get('PLANT_ID_API_URL', 'https://plant.id/api/v3').rstrip('/')
        self._health_url = _base_url + '/health_assessment'

    def check_health(self, images_b64: list) -> dict:
        """
        Send base64-encoded images to Plant.id health assessment API.
        Returns a parsed result dict with is_healthy, health_probability, and diseases list.
        """
        if not images_b64:
            return {"success": False, "error": "No images provided"}

        headers = {
            "Api-Key": self._api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "images": images_b64,
        }
        params = {
            "details": HEALTH_DETAILS,
            "language": "en",
        }

        try:
            response = requests.post(
                self._health_url,
                json=payload,
                headers=headers,
                params=params,
                timeout=30,
            )
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}

        if response.status_code == 201:
            return self._parse_result(response.json())
        elif response.status_code == 401:
            return {"success": False, "error": "Invalid API key"}
        elif response.status_code == 429:
            return {"success": False, "error": "Out of credits"}
        else:
            return {"success": False, "error": f"API error {response.status_code}: {response.text}"}

    def _parse_result(self, data: dict) -> dict:
        result = data.get("result", {})
        is_healthy_obj = result.get("is_healthy", {})
        disease_suggestions = result.get("disease", {}).get("suggestions", [])

        diseases = []
        for d in disease_suggestions:
            entry = {
                "name": d.get("name"),
                "probability": round(d.get("probability", 0) * 100, 1),
            }
            details = d.get("details") or {}
            if details:
                entry["local_name"] = details.get("local_name")
                entry["description"] = details.get("description")
                entry["url"] = details.get("url")
                entry["cause"] = details.get("cause")
                entry["common_names"] = details.get("common_names")
                treatment = details.get("treatment") or {}
                entry["treatment"] = {
                    "biological": treatment.get("biological", []),
                    "chemical": treatment.get("chemical", []),
                    "prevention": treatment.get("prevention", []),
                }
            diseases.append(entry)

        return {
            "success": True,
            "is_healthy": is_healthy_obj.get("binary", True),
            "health_probability": round(is_healthy_obj.get("probability", 1.0) * 100, 1),
            "status": data.get("status"),
            "images_sent": len(data.get("input", {}).get("images", [])),
            "diseases": diseases,
        }

    def run(self, camera) -> dict:
        """
        Capture frames from all available cameras on the GH_Camera object,
        then send them to the Plant.id health assessment API.
        """
        images_b64 = camera.capture_frames_base64()
        if not images_b64:
            return {"success": False, "error": "Could not capture images from any camera"}
        return self.check_health(images_b64)

    def run_with_s3(self, camera, s3_handler) -> dict:
        """
        Capture frames from all cameras, upload each to S3, then check plant health.
        Returns the health result with an added 's3_urls' list.
        """
        from utils.utils import _CUSTOM_PRINT_FUNC

        images_b64 = camera.capture_frames_base64()
        if not images_b64:
            return {"success": False, "error": "Could not capture images from any camera", "s3_urls": []}

        # Upload each captured frame to S3
        s3_urls = []
        session = datetime.datetime.now().strftime('%Y-%m-%dT%H-%M-%S')
        for i, b64_str in enumerate(images_b64):
            try:
                img_bytes = base64.b64decode(b64_str)
                key = f"health-checks/{session}/camera_{i + 1}.jpg"
                url = s3_handler.upload_bytes(img_bytes, key)
                if url:
                    s3_urls.append(url)
                    _CUSTOM_PRINT_FUNC(f"[PlantHealth] Camera {i + 1} uploaded → {url}")
            except Exception as e:
                _CUSTOM_PRINT_FUNC(f"[PlantHealth] S3 upload error camera {i + 1}: {e}")

        result = self.check_health(images_b64)
        result['s3_urls'] = s3_urls
        return result
