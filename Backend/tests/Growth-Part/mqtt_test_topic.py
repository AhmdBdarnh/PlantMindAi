import paho.mqtt.client as mqttClient
from paho import mqtt
import json
from pymongo.mongo_client import MongoClient
import pymongo
import time
import datetime
# from pymongo.server_api import ServerApi


HOST = "smartgreen-884cb6eb.a03.euc1.aws.hivemq.cloud"
PORT = 8883
USERNAME = "SmartGreenHouse"
PASSWORD = "SmartGreenHouse2025"

MONGO_URT = "mongodb+srv://smartGh-00:Smartgreenhouse1@greenhouse.ibf6l7y.mongodb.net/?retryWrites=true&w=majority&appName=GreenHouse"
MONGO_DB_NAME = "GreenHouse"


class MongoDBHandler:
    def __init__(self, uri, db_name):
        self.__client = MongoClient(uri)
        # Send a ping to confirm a successful connection
        try:
            self.__client.admin.command('ping')
            print("Pinged your deployment. You successfully connected to MongoDB!")
        except Exception as e:
            print(e)

        self.__db = self.__client[db_name]
        self.__pi_data_map = {} # maps keys to their respective collection
        self.__plant_growth_map = {
                                   "_id": "",
                                    "id": 999, 
                                   "CreatedAt": datetime.datetime.now(),
                                   "plant_name": "Cucumber",
                                   "date": "2025-06-19T14:21:16.467860",
                                   "file_name_image_1": "image_c0_2025-06-18_23-04-43.jpg", # must replace this with the link of the picture from the aws s3
                                   "file_name_image_2": "image_c0_2025-06-18_23-04-43.jpg", # must replace this with the link of the picture from the aws s3
                                   "size_compare": {
                                       "current_day_px": 71102, 
                                       "growth": 1
                                       }, 
                                    "disease_class": {
                                        "name": "Cucumber___healthy"
                                        }
                            }       


    def create_collection(self, collection_name, key, fields):
        self.__pi_data_map[key] = {
            'collection': self.__db[collection_name],
            'fields': fields           
        }

    def get_latest_x_docs(self, collection: str, limit: int = 1) -> list:
        try:
            cursor = self.__db[collection].find().sort("timestamp", pymongo.DESCENDING).limit(limit)
            return list(cursor)
        except Exception as e:
            print(f"Error retrieving latest documents: {e}")
            return []

    def insert_plant_growth_data(self, key, plant_growth_data = None):
        try:
            timestamp_val = datetime.datetime.now()
            str_time = timestamp_val.strftime("%Y-%m-%d %H:%M:%S")
            plant_growth_data['_id'] = 'plant_growth_' + str_time.replace(" ", "").replace(":", "").replace("-", "") + str(int(time.time()))
            plant_growth_data['CreatedAt'] = timestamp_val
            self.__pi_data_map[key]['fields'] = plant_growth_data
            self.__pi_data_map[key]['collection'].insert_one(self.__pi_data_map[key]['fields'])
            return True
        except Exception as e:
            print(f"Error inserting plant growth data: {e}")
            return False
        
        
    def get_latest_doc_where(self, collection: str, query: dict) -> dict:
        try:
            cursor = self.__db[collection].find(query).sort("timestamp", pymongo.DESCENDING).limit(1)
            for doc in cursor:
                return doc
            return None
        except Exception as e:
            print(f"Error retrieving latest document: {e}")
            return None

    def close_connection(self):
        try:            
            self.__client.close()
            return True
        except Exception as e:
            print(f"Error closing connection: {e}")
            return False

# initialize the mongo db handler
mongo_db_handler = MongoDBHandler(
    uri=MONGO_URT,
    db_name=MONGO_DB_NAME
)

# create a collection for plant growth data
mongo_db_handler.create_collection(
    "plant_growth_data",
    "plant_growth",
    {
        "plant_name": "Cucumber",
        "date": "2025-06-19T14:21:16.467860", 
        "file_name_image": "image_c0_2025-06-18_23-04-43.jpg", 
        "size_compare": {"current_day_px": 71102, "growth": 1}, 
        "disease_class": {"id": 999, "name": "Cucumber___healthy"}
    }
)

def push_data_to_mongo(json_data = None):
    try:
        mongo_db_handler.insert_plant_growth_data(
            "plant_growth",
            json_data)
        print("Data inserted into MongoDB successfully.")
        return True
    except Exception as e:
        print(f"Error inserting data into MongoDB: {e}")
        return False


def on_connect(client, userdata, flags, rc, protperties=None):
    print("Connected with result code " + str(rc))

def on_message(client, userdata, message):
    try:
        topic = message.topic
        payload = message.payload.decode("utf-8")
        print(f"Received message '{payload}' on topic '{topic}'")
        if topic == "test/plant_growth":
            try:
                json_data = json.loads(payload)    
                # move the disease_class/id to the root level
                if 'disease_class' in json_data and 'id' in json_data['disease_class']:
                    json_data['id'] = json_data['disease_class']['id']
                    del json_data['disease_class']['id']              
                              
                if push_data_to_mongo(json_data):
                    print("Data processed and pushed to MongoDB successfully.")
                else:
                    print("Failed to push data to MongoDB.")
            except json.JSONDecodeError:
                print(f"Error decoding JSON payload: {payload} for topic: {topic}")
        else:
            print(f"Unhandled topic: {topic} with payload: {payload}")
    except Exception as e:
        print(f"Error processing message: {e} for topic: {message.topic}")


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


# Subscribe to a topic
mqtt_client.subscribe("test/plant_growth", qos=1)

while True:
    try:
        pass
    except KeyboardInterrupt:
        print("Exiting...")
        break
    except Exception as e:
        print(f"Error: {e}")
        break