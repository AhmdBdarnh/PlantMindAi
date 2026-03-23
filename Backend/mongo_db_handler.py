from pymongo.mongo_client import MongoClient
import pymongo
import time
import datetime
# from pymongo.server_api import ServerApi
from utils.utils import _CUSTOM_PRINT_FUNC

class MongoDBHandler:
    def __init__(self, uri, db_name):
        self.__client = MongoClient(uri)
        # Send a ping to confirm a successful connection
        try:
            self.__client.admin.command('ping')
            _CUSTOM_PRINT_FUNC("Pinged your deployment. You successfully connected to MongoDB!")
        except Exception as e:
            _CUSTOM_PRINT_FUNC(e)

        self.__db = self.__client[db_name]
        self.__pi_data_map = {} # maps keys to their respective collection

    def sensor_field_doc_temp(self, sensor_id, sensor_type, sensor_value, sensor_unit):
        return {
            '_id': '',
            'sensor_id': sensor_id,
            'sensor_type': sensor_type,
            'sensor_value': sensor_value,
            'sensor_unit': sensor_unit,
            'timestamp': datetime.datetime.now()
        }
    
    def actuator_field_doc_temp(self, actuator_id, actuator_type, actuator_value):
        return {
            '_id': '',
            'actuator_id': actuator_id,
            'actuator_type': actuator_type,
            'actuator_value': actuator_value,
            'timestamp': datetime.datetime.now()
        }

    def resource_field_doc_temp(self, resource_id, resource_type, resource_value, unit=None):
        return {
            '_id': '',
            'resource_id': resource_id,
            'resource_type': resource_type,
            'resource_value': resource_value,
            'resource_unit': unit if unit else '',
            'timestamp': datetime.datetime.now()
        }

    def create_collection(self, collection_name, key, fields):
        self.__pi_data_map[key] = {
            'collection': self.__db[collection_name],
            'fields': fields           
        }

    def insert_sensor_data(self, key, sensor_value):
        try:
            timestamp_val = datetime.datetime.now()
            str_time = timestamp_val.strftime("%Y-%m-%d %H:%M:%S")
            self.__pi_data_map[key]['fields']['_id'] = self.__pi_data_map[key]['fields']['sensor_id'] + str_time.replace(" ", "").replace(":", "").replace("-", "") + str(int(time.time())) 
            self.__pi_data_map[key]['fields']['sensor_value'] = sensor_value
            self.__pi_data_map[key]['fields']['timestamp'] = timestamp_val
            self.__pi_data_map[key]['collection'].insert_one(self.__pi_data_map[key]['fields'])
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error inserting sensor data: {e}")
            return False

    def insert_actuator_data(self, key, actuator_value):
        try:
            timestamp_val = datetime.datetime.now()
            str_time = timestamp_val.strftime("%Y-%m-%d %H:%M:%S")
            self.__pi_data_map[key]['fields']['_id'] = self.__pi_data_map[key]['fields']['actuator_id'] + str_time.replace(" ", "").replace(":", "").replace("-", "") + str(int(time.time()))
            self.__pi_data_map[key]['fields']['actuator_value'] = actuator_value
            self.__pi_data_map[key]['fields']['timestamp'] = timestamp_val
            self.__pi_data_map[key]['collection'].insert_one(self.__pi_data_map[key]['fields'])
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error inserting actuator data: {e}")
            return False

    def insert_image_data(self, key, image_path, cam_id = 0):
        try:
            timestamp_val = datetime.datetime.now()
            str_time = timestamp_val.strftime("%Y-%m-%d %H:%M:%S")
            self.__pi_data_map[key]['fields']['_id'] = f'image_c{cam_id}' + str_time.replace(" ", "").replace(":", "").replace("-", "") + str(int(time.time()))
            self.__pi_data_map[key]['fields']['image'] = image_path
            self.__pi_data_map[key]['fields']['timestamp'] = timestamp_val
            self.__pi_data_map[key]['collection'].insert_one(self.__pi_data_map[key]['fields'])
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error inserting image data: {e}")
            return False

    def insert_resource_data(self, key, resource_value):
        try:
            timestamp_val = datetime.datetime.now()
            str_time = timestamp_val.strftime("%Y-%m-%d %H:%M:%S")
            self.__pi_data_map[key]['fields']['_id'] = self.__pi_data_map[key]['fields']['resource_id'] + str_time.replace(" ", "").replace(":", "").replace("-", "") + str(int(time.time()))
            self.__pi_data_map[key]['fields']['resource_value'] = resource_value
            self.__pi_data_map[key]['fields']['timestamp'] = timestamp_val
            self.__pi_data_map[key]['collection'].insert_one(self.__pi_data_map[key]['fields'])
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error inserting resource data: {e}")
            return False

    def get_data(self, key):
        try:
            return self.__pi_data_map[key]['collection'].find_one()
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error retrieving data: {e}")
            return None
    
    def get_all_data(self, key):
        try:            
            return self.__pi_data_map[key]['collection'].find()
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error retrieving all data: {e}")
            return None
    
    def delete_data(self, key):
        try:
            self.__pi_data_map[key]['collection'].delete_many({})
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error deleting data: {e}")
            return False

    def delete_all_data(self):
        try:            
            self.__db.drop()
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error deleting all data: {e}")
            return False

    def get_latest_doc_where(self, collection: str, query: dict) -> dict:
        try:
            cursor = self.__db[collection].find(query).sort("timestamp", pymongo.DESCENDING).limit(1)
            for doc in cursor:
                return doc
            return None
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error retrieving latest document: {e}")
            return None

    def close_connection(self):
        try:            
            self.__client.close()
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error closing connection: {e}")
            return False

    