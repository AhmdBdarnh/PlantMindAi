
import paho.mqtt.client as mqttClient
from paho import mqtt
import datetime

HOST = "smartgreen-884cb6eb.a03.euc1.aws.hivemq.cloud"
PORT = 8883
USERNAME = "SmartGreenHouse"
PASSWORD = "SmartGreenHouse2025"


def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("Connected to MQTT broker successfully.")
    else:
        print(f"Failed to connect, return code {rc}.")


def on_message(client, userdata, message):
    try:
        topic = message.topic
        payload = message.payload.decode("utf-8")
        print(f"Received message on topic '{topic}': {payload}")
        
        # Process the message as needed
        # For example, you can parse JSON if the payload is in JSON format
        # data = json.loads(payload)
        
    except Exception as e:
        print(f"Error processing message: {e}")


try:
    mqtt_client = mqttClient.Client(client_id="", protocol=mqttClient.MQTTv5)
    mqtt_client.tls_set(tls_version=mqtt.client.ssl.PROTOCOL_TLS)
    mqtt_client.username_pw_set(USERNAME, PASSWORD)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(HOST, PORT)
    mqtt_client.loop_start()
except Exception as e:
    print(f"Error connecting to MQTT broker: {e}")
    exit(1)


# # Subscribe to a topic
mqtt_client.subscribe("test/plant_growth", qos=1)

import json
json_str = json.dumps({
    "_id": "111",
    "id": 99, 
    "CreatedAt": datetime.datetime.now().isoformat(),
    "plant_name": "Cucumber",
    "date": "2025-06-19T14:21:16.467860",
    "file_name_image_1": "image_c0_2025-06-18_23-04-43.jpg", # must replace this with the link of the picture from the aws s3
    "file_name_image_2": "image_c0_2025-06-18_23-04-43.jpg", # must replace this with the link of the picture from the aws s3
    "size_compare": {
        "current_day_px": 71102, 
        "growth": 80
        }, 
    "disease_class": {
        "name": "Cucumber___healthy"
        }
}
)  

mqtt_client.publish("test/plant_growth", json_str, qos=1, retain=True)


while True:
    try:
        pass
    except KeyboardInterrupt:
        print("Exiting...")
        break
    except Exception as e:
        print(f"Error: {e}")
        break