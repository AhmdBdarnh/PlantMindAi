from pymongo.mongo_client import MongoClient
import pymongo
import time
import datetime
# from pymongo.server_api import ServerApi


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

    def sensor_field_doc_temp(self, sensor_id, sensor_type, sensor_value, sensor_unit):
        return {
            '_id': '',
            'sensor_id': sensor_id,
            'sensor_type': sensor_type,
            'sensor_value': sensor_value,
            'sensor_unit': sensor_unit,
            'timestamp': ''
        }
    
    def actuator_field_doc_temp(self, actuator_id, actuator_type, actuator_value):
        return {
            '_id': '',
            'actuator_id': actuator_id,
            'actuator_type': actuator_type,
            'actuator_value': actuator_value,
            'timestamp': ''
        }

    def create_collection(self, collection_name, key, fields):
        self.__pi_data_map[key] = {
            'collection': self.__db[collection_name],
            'fields': fields           
        }

    def insert_sensor_data(self, key, sensor_value):
        try:
            timestamp_val = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.__pi_data_map[key]['fields']['_id'] = self.__pi_data_map[key]['fields']['sensor_id'] + timestamp_val.replace(" ", "").replace(":", "").replace("-", "") + str(int(time.time())) 
            self.__pi_data_map[key]['fields']['sensor_value'] = sensor_value
            self.__pi_data_map[key]['fields']['timestamp'] = timestamp_val
            self.__pi_data_map[key]['collection'].insert_one(self.__pi_data_map[key]['fields'])
            return True
        except Exception as e:
            print(f"Error inserting sensor data: {e}")
            return False

    def insert_actuator_data(self, key, actuator_value):
        try:
            timestamp_val = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.__pi_data_map[key]['fields']['_id'] = self.__pi_data_map[key]['fields']['actuator_id'] + timestamp_val.replace(" ", "").replace(":", "").replace("-", "") + str(int(time.time()))
            self.__pi_data_map[key]['fields']['actuator_value'] = actuator_value
            self.__pi_data_map[key]['fields']['timestamp'] = timestamp_val
            self.__pi_data_map[key]['collection'].insert_one(self.__pi_data_map[key]['fields'])
            return True
        except Exception as e:
            print(f"Error inserting actuator data: {e}")
            return False

    def insert_image_data(self, key, image_path):
        try:
            timestamp_val = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.__pi_data_map[key]['fields']['_id'] = 'image' + timestamp_val.replace(" ", "").replace(":", "").replace("-", "") + str(int(time.time()))
            self.__pi_data_map[key]['fields']['image'] = image_path
            self.__pi_data_map[key]['fields']['timestamp'] = timestamp_val
            self.__pi_data_map[key]['collection'].insert_one(self.__pi_data_map[key]['fields'])
            return True
        except Exception as e:
            print(f"Error inserting image data: {e}")
            return False

    def get_data(self, key):
        try:
            return self.__pi_data_map[key]['collection'].find_one()
        except Exception as e:
            print(f"Error retrieving data: {e}")
            return None
    
    def get_all_data(self, key):
        try:            
            return self.__pi_data_map[key]['collection'].find()
        except Exception as e:
            print(f"Error retrieving all data: {e}")
            return None
    
    def delete_data(self, key):
        try:
            self.__pi_data_map[key]['collection'].delete_many({})
            return True
        except Exception as e:
            print(f"Error deleting data: {e}")
            return False

    def delete_all_data(self):
        try:            
            self.__db.drop()
            return True
        except Exception as e:
            print(f"Error deleting all data: {e}")
            return False

    def get_latest_doc_where(self, collection: str, query: dict) -> dict:
        try:
            cursor = self.__db[collection].find(query).sort("timestamp", pymongo.DESCENDING)

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

    