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

    def upsert_actuator_data(self, key, actuator_value):
        """Update the single actuator document for this key (upsert — never duplicates)."""
        try:
            actuator_id   = self.__pi_data_map[key]['fields']['actuator_id']
            actuator_type = self.__pi_data_map[key]['fields']['actuator_type']
            self.__pi_data_map[key]['collection'].update_one(
                {'actuator_id': actuator_id},
                {'$set': {
                    'actuator_id':    actuator_id,
                    'actuator_type':  actuator_type,
                    'actuator_value': actuator_value,
                    'timestamp':      datetime.datetime.now(),
                }},
                upsert=True,
            )
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error upserting actuator data: {e}")
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

    def upsert_resource_data(self, key, resource_value, cost_nis=None):
        """Update the single resource document for this key (upsert — never duplicates)."""
        try:
            resource_id   = self.__pi_data_map[key]['fields']['resource_id']
            resource_type = self.__pi_data_map[key]['fields']['resource_type']
            resource_unit = self.__pi_data_map[key]['fields'].get('resource_unit', '')
            update_fields = {
                'resource_id':    resource_id,
                'resource_type':  resource_type,
                'resource_value': resource_value,
                'resource_unit':  resource_unit,
                'timestamp':      datetime.datetime.now(),
            }
            if cost_nis is not None:
                update_fields['cost_nis'] = round(cost_nis, 4)
            self.__pi_data_map[key]['collection'].update_one(
                {'resource_id': resource_id},
                {'$set': update_fields},
                upsert=True,
            )
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error upserting resource data: {e}")
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

    def clear_collection(self, collection_name: str):
        """Delete all documents from a collection by name."""
        try:
            self.__db[collection_name].delete_many({})
            _CUSTOM_PRINT_FUNC(f"[MongoDB] Cleared collection: {collection_name}")
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[MongoDB] Error clearing {collection_name}: {e}")
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

    def insert_capture_session(self, session_doc: dict) -> bool:
        """
        Store a full capture session document in the capture_sessions collection.
        session_doc should contain: session_id, timestamp, images[], health, camera_count.
        S3 keys (not presigned URLs) are stored so they can be refreshed on read.
        """
        try:
            self.__db['capture_sessions'].insert_one(session_doc)
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error inserting capture session: {e}")
            return False

    def update_capture_session_health(self, session_id: str, health: dict) -> bool:
        """Patch the health field of an existing capture session after async health check."""
        try:
            self.__db['capture_sessions'].update_one(
                {'session_id': session_id},
                {'$set': {'health': health}}
            )
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error updating session health: {e}")
            return False

    def get_capture_sessions(self, limit: int = 20) -> list:
        """
        Return the most recent capture sessions, newest first.
        _id is excluded to make serialisation easier.
        """
        try:
            cursor = (
                self.__db['capture_sessions']
                .find({}, {'_id': 0})
                .sort('timestamp', pymongo.DESCENDING)
                .limit(limit)
            )
            return list(cursor)
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error fetching capture sessions: {e}")
            return []

    def upsert_state(self, key: str, value) -> bool:
        """Save a single running value (e.g. water_amount) — one document per key, always overwritten."""
        try:
            self.__db['system_state'].update_one(
                {'key': key},
                {'$set': {'key': key, 'value': value, 'timestamp': datetime.datetime.now()}},
                upsert=True,
            )
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error upserting state '{key}': {e}")
            return False

    def get_state(self, key: str):
        """Load a previously saved running value. Returns None if not found."""
        try:
            doc = self.__db['system_state'].find_one({'key': key})
            return doc['value'] if doc else None
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error getting state '{key}': {e}")
            return None

    def insert_pump_log(self, pump_type: str, pulse_sec: float, duty_cycle: int, flow_rate_l_min: float = 0.0) -> bool:
        """Log a single pump pulse event to the pump_logs collection."""
        try:
            self.__db['pump_logs'].insert_one({
                'pump':            pump_type,
                'timestamp':       datetime.datetime.now(),
                'pulse_sec':       pulse_sec,
                'duty_cycle':      duty_cycle,
                'flow_rate_l_min': round(flow_rate_l_min, 4),
            })
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error inserting pump log: {e}")
            return False

    def get_pump_logs(self, limit: int = 50) -> list:
        """Return the most recent pump pulse events, newest first."""
        try:
            cursor = (
                self.__db['pump_logs']
                .find({}, {'_id': 0})
                .sort('timestamp', pymongo.DESCENDING)
                .limit(limit)
            )
            return list(cursor)
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error fetching pump logs: {e}")
            return []

    # ── Growth measurements ───────────────────────────────────────────────────

    def insert_growth_measurement(self, doc: dict) -> bool:
        """
        Insert a growth measurement document into the growth_measurements collection.
        The doc should follow the schema produced by growth_metrics.py.
        """
        try:
            self.__db['growth_measurements'].insert_one(doc)
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error inserting growth measurement: {e}")
            return False

    def get_latest_growth_measurement(self) -> dict:
        """Return the most recent growth measurement, or None if none exist."""
        try:
            cursor = (
                self.__db['growth_measurements']
                .find({}, {'_id': 0})
                .sort('created_at', pymongo.DESCENDING)
                .limit(1)
            )
            for doc in cursor:
                return doc
            return None
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error fetching latest growth measurement: {e}")
            return None

    def get_growth_history(self, limit: int = 50) -> list:
        """Return the most recent growth measurements, newest first."""
        try:
            cursor = (
                self.__db['growth_measurements']
                .find({}, {'_id': 0})
                .sort('created_at', pymongo.DESCENDING)
                .limit(limit)
            )
            return list(cursor)
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error fetching growth history: {e}")
            return []

    # ── Plant health results ──────────────────────────────────────────────────

    def insert_plant_health_result(self, doc: dict) -> bool:
        """
        Save a plant health API result to the plant_health_results collection.
        doc fields: is_healthy, health_probability, diseases, s3_urls,
                    session_id, created_at, raw_response (optional).
        """
        try:
            self.__db['plant_health_results'].insert_one(doc)
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error inserting plant health result: {e}")
            return False

    def get_latest_plant_health_result(self) -> dict:
        """Return the most recent plant health result, or None if none exist."""
        try:
            cursor = (
                self.__db['plant_health_results']
                .find({}, {'_id': 0})
                .sort('created_at', pymongo.DESCENDING)
                .limit(1)
            )
            for doc in cursor:
                return doc
            return None
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error fetching latest plant health result: {e}")
            return None

    def get_plant_health_history(self, limit: int = 20) -> list:
        """Return the most recent plant health results, newest first."""
        try:
            cursor = (
                self.__db['plant_health_results']
                .find({}, {'_id': 0})
                .sort('created_at', pymongo.DESCENDING)
                .limit(limit)
            )
            return list(cursor)
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error fetching plant health history: {e}")
            return []

    # ── Sensor statistics (for AI Advisor) ───────────────────────────────────

    def get_sensor_stats(self, sensor_id: str, hours: int = 24,
                         min_value: float = None, max_value: float = None) -> dict:
        """
        Return avg/min/max/count for a sensor over the last `hours` hours.
        Queries the sensors_data collection by sensor_id + timestamp range.
        min_value / max_value: optional plausible-range filter applied at query
        time to exclude glitch/restart spikes before computing statistics.
        """
        try:
            since = datetime.datetime.now() - datetime.timedelta(hours=hours)
            query: dict = {'sensor_id': sensor_id, 'timestamp': {'$gte': since}}
            if min_value is not None or max_value is not None:
                val_filter: dict = {}
                if min_value is not None:
                    val_filter['$gte'] = min_value
                if max_value is not None:
                    val_filter['$lte'] = max_value
                query['sensor_value'] = val_filter
            cursor = self.__db['sensors_data'].find(
                query,
                {'sensor_value': 1, 'sensor_unit': 1, '_id': 0},
            )
            values = []
            unit   = ''
            for doc in cursor:
                val = doc.get('sensor_value')
                if val is not None:
                    try:
                        values.append(float(val))
                        if not unit:
                            unit = doc.get('sensor_unit', '')
                    except (TypeError, ValueError):
                        pass
            if not values:
                return {'count': 0, 'avg': None, 'min': None, 'max': None, 'unit': unit}
            return {
                'count': len(values),
                'avg':   round(sum(values) / len(values), 4),
                'min':   round(min(values), 4),
                'max':   round(max(values), 4),
                'unit':  unit,
            }
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error computing sensor stats for '{sensor_id}': {e}")
            return {'count': 0, 'avg': None, 'min': None, 'max': None, 'unit': ''}

    # ── AI setpoint recommendations ───────────────────────────────────────────

    def insert_ai_recommendation(self, doc: dict) -> bool:
        """Insert an AI setpoint recommendation document."""
        try:
            self.__db['ai_setpoint_recommendations'].insert_one(doc)
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error inserting AI recommendation: {e}")
            return False

    def get_latest_ai_recommendation(self) -> dict:
        """Return the most recent AI recommendation, or None."""
        try:
            cursor = (
                self.__db['ai_setpoint_recommendations']
                .find({}, {'_id': 0})
                .sort('created_at', pymongo.DESCENDING)
                .limit(1)
            )
            for doc in cursor:
                return doc
            return None
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error fetching latest AI recommendation: {e}")
            return None

    def get_ai_recommendations(self, limit: int = 10) -> list:
        """Return the most recent AI recommendations, newest first."""
        try:
            cursor = (
                self.__db['ai_setpoint_recommendations']
                .find({}, {'_id': 0, 'raw_ai_response': 0})
                .sort('created_at', pymongo.DESCENDING)
                .limit(limit)
            )
            return list(cursor)
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error fetching AI recommendations: {e}")
            return []

    def get_ai_recommendation_by_id(self, rec_id: str) -> dict:
        """Return a single AI recommendation by recommendation_id."""
        try:
            doc = self.__db['ai_setpoint_recommendations'].find_one(
                {'recommendation_id': rec_id}
            )
            if doc:
                doc.pop('_id', None)
            return doc
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error fetching AI recommendation '{rec_id}': {e}")
            return None

    def update_ai_recommendation(self, rec_id: str, fields: dict) -> bool:
        """Update specific fields in an AI recommendation document."""
        try:
            self.__db['ai_setpoint_recommendations'].update_one(
                {'recommendation_id': rec_id},
                {'$set': fields},
            )
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error updating AI recommendation '{rec_id}': {e}")
            return False

    # ── Daily cost baseline (Layer 3 Budget Gate) ────────────────────────────

    def reset_daily_costs_baseline(self) -> bool:
        """
        Delete today's daily_costs document.

        Called during a new plant cycle reset, AFTER system_state totals have been
        zeroed by reset_resources(). The next call to get_today_costs() will create
        a fresh baseline at the current (post-reset) values — which are all 0 — so
        today's cost calculation starts from zero.
        """
        try:
            import datetime as _dt
            today_str = _dt.date.today().isoformat()
            result = self.__db['daily_costs'].delete_one({'_id': today_str})
            _CUSTOM_PRINT_FUNC(
                f"[DailyCosts] Baseline reset for {today_str} "
                f"(deleted={result.deleted_count}). "
                "Next get_today_costs() will recreate it at 0."
            )
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[DailyCosts] Error resetting daily costs baseline: {e}")
            return False

    def get_today_costs(
        self,
        water_price_per_liter: float,
        electricity_price_per_kwh: float,
        fertilizer_price_per_5l: float,
    ) -> dict:
        """
        Return today's resource usage and costs only — not lifetime cumulative totals.

        Option A daily-baseline approach:
          - On the first call of each calendar day, reads the current cumulative
            totals from system_state and saves them as today's starting baseline
            in the daily_costs collection.
          - Today's usage = current cumulative - baseline.
          - If a mid-day plant-cycle reset is detected (current < baseline),
            the baseline is updated to the new current so the counter restarts
            from zero for the remainder of the day.

        Parameters:
          water_price_per_liter      — NIS per litre of water (from config)
          electricity_price_per_kwh  — NIS per kWh of electricity (from config)
          fertilizer_price_per_5l    — NIS per 5 litres of fertilizer (from config)

        Returns a dict with today's usage and costs.
        """
        today_str = datetime.date.today().isoformat()   # e.g. "2026-05-29"
        col       = self.__db['daily_costs']
        is_new_baseline = False

        # ── Read current cumulative totals from system_state ───────────────────
        def _state_float(key: str) -> float:
            doc = self.__db['system_state'].find_one({'key': key})
            if doc and doc.get('value') is not None:
                try:
                    return float(doc['value'])
                except (TypeError, ValueError):
                    pass
            return 0.0

        current_water  = _state_float('total_water_liters')
        current_energy = _state_float('total_energy_wh')
        current_fert   = _state_float('total_fertilizer_liters')

        # ── Look up today's baseline ───────────────────────────────────────────
        baseline_doc = col.find_one({'_id': today_str})

        if baseline_doc is None:
            # First call of this calendar day — snapshot current totals as baseline
            baseline_doc = {
                '_id':                        today_str,
                'baseline_water_liters':      current_water,
                'baseline_energy_wh':         current_energy,
                'baseline_fertilizer_liters': current_fert,
                'created_at':                 datetime.datetime.now(),
            }
            col.insert_one(baseline_doc)
            is_new_baseline = True
            _CUSTOM_PRINT_FUNC(
                f"[DailyCosts] New baseline created for {today_str} — "
                f"water={current_water:.3f}L  energy={current_energy:.3f}Wh  "
                f"fert={current_fert:.3f}L"
            )

        baseline_water  = float(baseline_doc.get('baseline_water_liters',      0.0))
        baseline_energy = float(baseline_doc.get('baseline_energy_wh',         0.0))
        baseline_fert   = float(baseline_doc.get('baseline_fertilizer_liters', 0.0))

        # ── Detect mid-day resource reset (reset_resources() called mid-day) ──
        # If any current total dropped below its baseline, a new plant cycle
        # started during the day. Update the baseline to current so usage
        # restarts from zero rather than going negative.
        if (current_water  < baseline_water or
                current_energy < baseline_energy or
                current_fert   < baseline_fert):
            _CUSTOM_PRINT_FUNC(
                f"[DailyCosts] Mid-day reset detected on {today_str} — "
                "updating baseline to current values."
            )
            col.update_one(
                {'_id': today_str},
                {'$set': {
                    'baseline_water_liters':      current_water,
                    'baseline_energy_wh':         current_energy,
                    'baseline_fertilizer_liters': current_fert,
                    'reset_detected_at':          datetime.datetime.now(),
                }},
            )
            baseline_water  = current_water
            baseline_energy = current_energy
            baseline_fert   = current_fert

        # ── Compute today's usage ──────────────────────────────────────────────
        water_today  = round(max(0.0, current_water  - baseline_water),  4)
        energy_today = round(max(0.0, current_energy - baseline_energy), 4)
        fert_today   = round(max(0.0, current_fert   - baseline_fert),   4)

        # ── Compute today's costs ──────────────────────────────────────────────
        water_cost = round(water_today  * water_price_per_liter,              4)
        elec_cost  = round((energy_today / 1000.0) * electricity_price_per_kwh, 4)
        fert_cost  = round((fert_today   / 5.0)    * fertilizer_price_per_5l,  4)
        total_cost = round(water_cost + elec_cost + fert_cost,                4)

        return {
            'date':                    today_str,
            'water_liters_today':      water_today,
            'energy_wh_today':         energy_today,
            'fertilizer_liters_today': fert_today,
            'water_cost_nis':          water_cost,
            'electricity_cost_nis':    elec_cost,
            'fertilizer_cost_nis':     fert_cost,
            'total_cost_nis':          total_cost,
            'baseline_created_at':     baseline_doc.get('created_at'),
            'is_new_baseline':         is_new_baseline,
        }

    # ── Layer 3 — layer3_decisions ───────────────────────────────────────────

    def insert_layer3_decision(self, doc: dict) -> bool:
        """Insert a new Layer 3 decision document into layer3_decisions."""
        try:
            self.__db['layer3_decisions'].insert_one(doc)
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[Layer3] Error inserting decision: {e}")
            return False

    def get_latest_layer3_decision(self) -> dict:
        """Return the most recent Layer 3 decision (any status), or None."""
        try:
            cursor = (
                self.__db['layer3_decisions']
                .find({}, {'_id': 0})
                .sort('timestamp', pymongo.DESCENDING)
                .limit(1)
            )
            for doc in cursor:
                return doc
            return None
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[Layer3] Error fetching latest decision: {e}")
            return None

    def get_layer3_decision_by_id(self, decision_id: str) -> dict:
        """Return a single Layer 3 decision by decision_id, or None."""
        try:
            doc = self.__db['layer3_decisions'].find_one(
                {'decision_id': decision_id}, {'_id': 0}
            )
            return doc
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[Layer3] Error fetching decision '{decision_id}': {e}")
            return None

    def update_layer3_decision(self, decision_id: str, fields: dict) -> bool:
        """Update specific fields in a Layer 3 decision document."""
        try:
            self.__db['layer3_decisions'].update_one(
                {'decision_id': decision_id},
                {'$set': fields},
            )
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[Layer3] Error updating decision '{decision_id}': {e}")
            return False

    def get_layer3_decisions(self, limit: int = 10) -> list:
        """Return the most recent Layer 3 decisions, newest first."""
        try:
            cursor = (
                self.__db['layer3_decisions']
                .find({}, {'_id': 0})
                .sort('timestamp', pymongo.DESCENDING)
                .limit(limit)
            )
            return list(cursor)
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[Layer3] Error fetching decision history: {e}")
            return []

    def cancel_pending_layer3_decisions(self) -> int:
        """
        Mark all decisions with status=pending_approval as cancelled.
        Called before starting a new Layer 3 review cycle so stale decisions
        are never shown as actionable in the frontend.
        Returns the number of documents cancelled.
        """
        try:
            result = self.__db['layer3_decisions'].update_many(
                {'status': 'pending_approval'},
                {'$set': {
                    'status':               'cancelled',
                    'cancelled_at':         datetime.datetime.now(),
                    'cancel_reason':        'New Layer 2 recommendation received',
                }},
            )
            count = result.modified_count
            if count > 0:
                _CUSTOM_PRINT_FUNC(f"[Layer3] Cancelled {count} pending decision(s).")
            return count
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[Layer3] Error cancelling pending decisions: {e}")
            return 0

    # ── Layer 3 — budget_config ──────────────────────────────────────────────

    # Default budget configuration — used when no config has been saved yet.
    _BUDGET_CONFIG_DEFAULTS = {
        'daily_budget':          10.0,   # NIS per day total
        'monthly_budget':       200.0,   # NIS per month total
        'water_budget':           3.0,   # NIS per day water only
        'electricity_budget':     5.0,   # NIS per day electricity only
        'fertilizer_budget':      2.0,   # NIS per day fertilizer only
        'warning_threshold_pct':  80,    # % of budget that triggers WARNING state
        'active':                True,
    }

    def get_budget_config(self) -> dict:
        """
        Return the current budget configuration.
        If no config has been saved yet, returns the default values.
        The returned dict never contains MongoDB's _id field.
        """
        try:
            doc = self.__db['budget_config'].find_one({'_id': 'budget_config'})
            if doc is None:
                _CUSTOM_PRINT_FUNC("[Layer3] No budget_config found — returning defaults.")
                defaults = dict(self._BUDGET_CONFIG_DEFAULTS)
                defaults['_source'] = 'defaults'
                return defaults
            doc.pop('_id', None)
            doc['_source'] = 'mongodb'
            return doc
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[Layer3] Error fetching budget_config: {e}")
            defaults = dict(self._BUDGET_CONFIG_DEFAULTS)
            defaults['_source'] = 'defaults_fallback'
            return defaults

    def save_budget_config(self, config: dict) -> bool:
        """
        Save (upsert) the budget configuration document.
        Always stamps updated_at. Adds created_at only on first save.
        """
        try:
            now = datetime.datetime.now()
            fields = {k: v for k, v in config.items() if k not in ('_id', '_source')}
            fields['updated_at'] = now
            self.__db['budget_config'].update_one(
                {'_id': 'budget_config'},
                {
                    '$set':         fields,
                    '$setOnInsert': {'created_at': now},
                },
                upsert=True,
            )
            _CUSTOM_PRINT_FUNC(f"[Layer3] budget_config saved: {fields}")
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[Layer3] Error saving budget_config: {e}")
            return False

    # ── Layer 3 — runtime_constraints ───────────────────────────────────────

    def get_runtime_constraints(self) -> dict:
        """
        Return the current active runtime constraints document.
        If none exist, returns a zeroed-out inactive document.
        """
        try:
            doc = self.__db['runtime_constraints'].find_one(
                {'_id': 'active_constraints'}, {'_id': 0}
            )
            if doc is None:
                return {
                    'led_power_cap':      None,
                    'led_duration_limit': None,
                    'fan_day_duty':       None,
                    'fan_night_duty':     None,
                    'irrigation_delay':   None,
                    'fertilizer_delay':   None,
                    'active':             False,
                    'reason':             None,
                    'created_at':         None,
                    'expires_at':         None,
                }
            return doc
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[Layer3] Error fetching runtime_constraints: {e}")
            return {'active': False, 'error': str(e)}

    def save_runtime_constraints(self, constraints: dict) -> bool:
        """
        Save (upsert) the active runtime constraints document.
        Automatically stamps created_at on first save.
        """
        try:
            now    = datetime.datetime.now()
            fields = {k: v for k, v in constraints.items() if k != '_id'}
            if 'created_at' not in fields:
                fields['created_at'] = now
            self.__db['runtime_constraints'].update_one(
                {'_id': 'active_constraints'},
                {'$set': fields},
                upsert=True,
            )
            _CUSTOM_PRINT_FUNC(f"[Layer3] runtime_constraints saved (active={fields.get('active')})")
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[Layer3] Error saving runtime_constraints: {e}")
            return False

    def clear_runtime_constraints(self) -> bool:
        """
        Deactivate all runtime constraints without deleting the document.
        Sets active=False and nulls out every constraint field.
        """
        try:
            self.__db['runtime_constraints'].update_one(
                {'_id': 'active_constraints'},
                {'$set': {
                    'led_power_cap':      None,
                    'led_duration_limit': None,
                    'fan_day_duty':       None,
                    'fan_night_duty':     None,
                    'irrigation_delay':   None,
                    'fertilizer_delay':   None,
                    'active':             False,
                    'reason':             None,
                    'expires_at':         None,
                    'cleared_at':         datetime.datetime.now(),
                }},
                upsert=True,
            )
            _CUSTOM_PRINT_FUNC("[Layer3] runtime_constraints cleared.")
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[Layer3] Error clearing runtime_constraints: {e}")
            return False

    # ── Layer 3 — layer3_status ──────────────────────────────────────────────

    def get_layer3_status(self) -> dict:
        """
        Return the current Layer 3 operational status document.
        If none exists, returns a default idle document.
        """
        try:
            doc = self.__db['layer3_status'].find_one(
                {'_id': 'layer3_status'}, {'_id': 0}
            )
            if doc is None:
                return {
                    'current_status':       'idle',
                    'last_run_at':          None,
                    'latest_decision_id':   None,
                    'active':               True,
                    'blocked_reason':       None,
                    'budget_status':        'unknown',
                    'sensor_safety_status': 'unknown',
                    'plant_health_status':  'unknown',
                }
            return doc
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[Layer3] Error fetching layer3_status: {e}")
            return {'current_status': 'error', 'error': str(e)}

    def update_layer3_status(self, fields: dict) -> bool:
        """Update fields in the single layer3_status document (upsert)."""
        try:
            clean = {k: v for k, v in fields.items() if k != '_id'}
            self.__db['layer3_status'].update_one(
                {'_id': 'layer3_status'},
                {'$set': clean},
                upsert=True,
            )
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"[Layer3] Error updating layer3_status: {e}")
            return False

    def close_connection(self):
        try:
            self.__client.close()
            return True
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"Error closing connection: {e}")
            return False

    