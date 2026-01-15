from typing import Union
import paho.mqtt.client as paho
from paho import mqtt
import json
import time
from utils.utils import _CUSTOM_PRINT_FUNC

class MqttHandler:
    def __init__(self, broker_address, port, username=None, password=None):
        try:
            # create an mqtt client (client id, clean session, qos level 0)
            self.__client = paho.Client(client_id="RaspberryPi", protocol=paho.MQTTv311, clean_session=True)
            self.__client.tls_set(tls_version=mqtt.client.ssl.PROTOCOL_TLS)
            
            if username is not None and password is not None:
                self.__client.username_pw_set(username, password)

            # set qos level 0
            def __on_connect(client, userdata, flags, rc, protperties=None):
                _CUSTOM_PRINT_FUNC("MQTT Connected with result code " + str(rc))

            def __on_disconnect(client, userdata, rc, properties=None):
                print("Disconnected with result code", rc)
                if rc != 0:
                    print("Unexpected disconnection. Attempting to reconnect...")
                    try:
                        client.reconnect()
                    except Exception as e:
                        print("Reconnect failed:", e)


            def __on_message(client, userdata, message):
                try:
                    topic = message.topic
                    payload = message.payload.decode("utf-8")
                    _CUSTOM_PRINT_FUNC(f"Received message on topic '{topic}': {payload}")
                    
                    if payload not in [None, "On", "Off", "manual", "autonomous"]:
                        if 'setpoints' in topic:                        
                            self.__sub_map[topic](int(payload))
                        elif 'actuators' in topic:
                            self.__sub_map[topic](int(payload))                            
                    elif payload in ["manual", "autonomous"]:
                        self.__sub_map[topic](payload)                        
                except json.JSONDecodeError:
                    _CUSTOM_PRINT_FUNC(f"Error decoding JSON payload: {message.payload.decode('utf-8')} for topic: {message.topic}")
                except Exception as e:
                    _CUSTOM_PRINT_FUNC(f"Error processing message: {e} for topic: {message.topic}")
                    
            self.__client.on_connect = __on_connect
            self.__client.on_message = __on_message
            self.__client.on_disconnect = __on_disconnect
            self.__client.connect(broker_address, port)
            self.__client.loop_start()
            self.__sub_map = {}
            self.__pub_map = {}
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error initializing MQTT client: {e}")
            raise        

    def set_subscription(self, topic, callback):
        try:
            self.__sub_map[topic] = callback
            self.__client.subscribe(topic, qos=1)
            _CUSTOM_PRINT_FUNC(f"Subscribed to topic: {topic}")
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error subscribing to topic {topic}: {e}")
            return False

    def set_publish(self, topic, pub_tolerance, retain=False):
        try:            
            self.__pub_map[topic] = {'tolerance': pub_tolerance, 'last_published_value': 0, 'retain': retain}            
            _CUSTOM_PRINT_FUNC(f"Publish set for topic: {topic} with tolerance: {pub_tolerance}")
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error setting publish for topic {topic}: {e}")
            return False

    def publish(self, topic, payload: Union[int, float]) -> None:
        try:            
            if self.__pub_map[topic]['last_published_value'] == 0:
                self.__client.publish(topic, payload, qos=1, retain=self.__pub_map[topic]['retain'])
                self.__pub_map[topic]['last_published_value'] = payload                
            else:
                if abs(self.__pub_map[topic]['last_published_value'] - payload) >= self.__pub_map[topic]['tolerance']:
                    self.__client.publish(topic, payload, qos=1, retain=self.__pub_map[topic]['retain'])
                    self.__pub_map[topic]['last_published_value'] = payload                
            _CUSTOM_PRINT_FUNC(f"Published to topic: {topic} with payload: {payload}")
            # time.sleep(0.1)
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error publishing to topic {topic}: {e}")
            return False
    
    def publish(self, topic, payload: str) -> None:
        try:
            self.__client.publish(topic, payload, qos=1, retain=self.__pub_map[topic]['retain'])
            _CUSTOM_PRINT_FUNC(f"Published to topic: {topic} with payload: {payload}")
            # time.sleep(0.1)
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error publishing to topic {topic}: {e}")
            return False