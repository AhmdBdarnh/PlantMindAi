"""
config.py — All constants and hardware configuration for PlantMind AI.
Change values here to affect the whole application.
"""
import os
import board

# ── Timing intervals ──────────────────────────────────────────────────────────
CAPTURE_INTERVAL_SECONDS = 86400                   # capture images every 24 hours
HEALTH_CHECK_INTERVAL_SECONDS = 86400              # call Plant.id API every 24 hours
RESOURCES_CONSUMPTION_LOG_AND_RESET_INTERVAL = 1   # hours between resource log & reset

# ── Hardware pin assignments ──────────────────────────────────────────────────
DHT22_PIN               = board.D26
WATER_FLOW_SENSOR_PIN   = 12
ADS1115_SOIL_CH         = 0
ADS1115_LIGHT_CH        = 1
ADS1115_SOIL_DRY_VAL    = 18000
ADS1115_SOIL_WET_VAL    = 7000

# ── ESP32 I2C ─────────────────────────────────────────────────────────────────
ESP32_I2C_ADDRESS  = 0x30
ESP32_ENDIANNESS   = 'big'

# ── MQTT (HiveMQ cloud) ───────────────────────────────────────────────────────
MQTT_HOST = "114fcbcf879e4e88a21d9f0bd7ab1ccc.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "SmartGreenHouse"
MQTT_PASS = "SmartGreenHouse2025"

# ── MongoDB Atlas ─────────────────────────────────────────────────────────────
MONGO_URI     = "mongodb+srv://PlantMind:ShenkarPlantMind@plantmindai.lma5ro9.mongodb.net/?retryWrites=true&w=majority&appName=PlantMindAi"
MONGO_DB_NAME = "GreenHouse"

# ── AWS S3 ────────────────────────────────────────────────────────────────────
AWS_S3_BUCKET = os.environ.get('AWS_S3_BUCKET', 'plant-mindai')
AWS_REGION    = os.environ.get('AWS_REGION', 'eu-west-1')
