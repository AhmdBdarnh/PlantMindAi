# --- Serial Logger with 3 Tables (Sensors/Actuators | Mode/Setpoints + Resources) --- 

import os
import time
import datetime
import threading

# Global dictionary to store the latest data for display
latest_data = {
    "timestamp": "N/A",
    "temperature": "N/A", "humidity": "N/A",
    "soil_ph": "N/A", "soil_ec": "N/A", "soil_temp": "N/A", "soil_humidity": "N/A",
    "water_flow": "N/A", 
    "electricity_voltage": "N/A", "electricity_current": "N/A", "electricity_power": "N/A",
    "electricity_energy": "N/A", "electricity_frequency": "N/A", "electricity_pf": "N/A",
    "electricity_alarm": "N/A",
    "light_intensity": "N/A",
    "heater_dc": "N/A", "heater_fan_dc": "N/A", "light_strip_1_dc": "N/A",
    "light_strip_2_dc": "N/A", "water_pump_dc": "N/A", "fan_dc": "N/A",
    "mode": "N/A",
    "temp_sp": "N/A", "hum_sp": "N/A", "light_sp": "N/A",
    "soil_ph_sp": "N/A", "soil_ec_sp": "N/A", "soil_temp_sp": "N/A",
    "soil_hum_sp": "N/A", "flow_sp": "N/A",
    "water_consumed": 0.0, # Initialize cumulative water
    "last_resource_reset": "Never", # Store last resource reset time
    "last_update_readings": "Never" # Store last update time for readings
}

# Lock for safely updating/reading latest_data 
data_lock = threading.Lock()

def serial_logger_task(sensors, get_last_sensor_update_fun, actuators, setpoints, temp_sem, light_sem, soil_sem, flow_sem, electricity_sem):
    """Reads data, mode, setpoints, resources; prints 3 tables."""
    global latest_data
    
    # Initialize cumulative water consumption within the task scope
    cumulative_water_liters = 0.0
    
    last_read_datetimes = {
        "temp_humidity": datetime.datetime.min,
        "soil": datetime.datetime.min,
        "flow": datetime.datetime.min,
        "electricity": datetime.datetime.min,
        "light": datetime.datetime.min,
        "actuators": datetime.datetime.min,
        "setpoints": datetime.datetime.min
    }
    
    intervals = {
        "temp_humidity": datetime.timedelta(seconds=5),
        "soil": datetime.timedelta(seconds=3),
        "flow": datetime.timedelta(seconds=1),
        "electricity": datetime.timedelta(seconds=10),
        "light": datetime.timedelta(seconds=3),
        "actuators": datetime.timedelta(seconds=1),
        "setpoints": datetime.timedelta(seconds=1)
    }

    while True:
        now = datetime.datetime.now()
        current_timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")
        
        current_state = {}
        current_state["timestamp"] = current_timestamp_str

        # --- Read Sensors/Actuators --- 
        # (Logic largely unchanged, stores results in current_state)
        # Temperature & Humidity (5s)
        if now >= last_read_datetimes["temp_humidity"] + intervals["temp_humidity"]:
            temp, humid = "N/A", "N/A"
            acquired = False
            if temp_sem: acquired = temp_sem.acquire(blocking=False)
            if acquired or not temp_sem:
                try:
                    temp = sensors.get_air_temperature_C()
                    humid = sensors.get_air_humidity()
                    current_state["temperature"] = temp if isinstance(temp, (int, float)) else "Read Error"
                    current_state["humidity"] = humid if isinstance(humid, (int, float)) else "Read Error"
                except Exception as e: print(f"Logger Error reading Temp/Hum: {e}"); current_state["temperature"] = "Exception"; current_state["humidity"] = "Exception"
                finally: 
                    if acquired: temp_sem.release()
                last_read_datetimes["temp_humidity"] = now
            else: 
                with data_lock: current_state["temperature"] = latest_data["temperature"]; current_state["humidity"] = latest_data["humidity"]
        else:
            with data_lock: current_state["temperature"] = latest_data["temperature"]; current_state["humidity"] = latest_data["humidity"]

        # Soil Sensors (3s)
        if now >= last_read_datetimes["soil"] + intervals["soil"]:
            acquired = False
            if soil_sem: acquired = soil_sem.acquire(blocking=False)
            if acquired or not soil_sem:
                try:
                    soil_ph, soil_ec, soil_hum, soil_temp = sensors.get_soil_values()
                    current_state["soil_ph"] = soil_ph if isinstance(soil_ph, (int, float)) else "Read Error"
                    current_state["soil_ec"] = soil_ec if isinstance(soil_ec, (int, float)) else "Read Error"
                    current_state["soil_temp"] = soil_temp if isinstance(soil_temp, (int, float)) else "Read Error"
                    current_state["soil_humidity"] = soil_hum if isinstance(soil_hum, (int, float)) else "Read Error"
                except Exception as e: print(f"Logger Error reading Soil: {e}"); current_state["soil_ph"] = "Ex"; current_state["soil_ec"] = "Ex"; current_state["soil_temp"] = "Ex"; current_state["soil_humidity"] = "Ex"
                finally: 
                    if acquired: soil_sem.release()
                last_read_datetimes["soil"] = now
            else: 
                with data_lock: current_state["soil_ph"] = latest_data["soil_ph"]; current_state["soil_ec"] = latest_data["soil_ec"]; current_state["soil_temp"] = latest_data["soil_temp"]; current_state["soil_humidity"] = latest_data["soil_humidity"]
        else:
             with data_lock: current_state["soil_ph"] = latest_data["soil_ph"]; current_state["soil_ec"] = latest_data["soil_ec"]; current_state["soil_temp"] = latest_data["soil_temp"]; current_state["soil_humidity"] = latest_data["soil_humidity"]

        # Water Flow (1s) & Calculate Cumulative Water
        if now >= last_read_datetimes["flow"] + intervals["flow"]:
            flow = "N/A"
            acquired = False
            if flow_sem: acquired = flow_sem.acquire(blocking=False)
            if acquired or not flow_sem:
                try:
                    flow = sensors.get_water_flow_rate() # L/min
                    if isinstance(flow, (int, float)):
                        current_state["water_flow"] = flow
                        # Add water consumed in the last second (flow L/min * 1 min/60 sec * 1 sec)
                        cumulative_water_liters = sensors.get_total_water_amount() 
                    else:
                        current_state["water_flow"] = "Read Error"
                except Exception as e: print(f"Logger Error reading Flow: {e}"); current_state["water_flow"] = "Exception"
                finally: 
                    if acquired: flow_sem.release()
                last_read_datetimes["flow"] = now
            else: 
                with data_lock: current_state["water_flow"] = latest_data["water_flow"]
        else:
            with data_lock: current_state["water_flow"] = latest_data["water_flow"]
        # Store cumulative water in state for display
        current_state["water_consumed"] = cumulative_water_liters 
        # Store last resource reset time
        current_state["last_resource_reset"] = sensors.get_last_resource_reset_time()
        # Store last update time for readings
        current_state["last_update_readings"] = get_last_sensor_update_fun()

        # Electricity (10s)
        if now >= last_read_datetimes["electricity"] + intervals["electricity"]:
            acquired = False
            if electricity_sem: acquired = electricity_sem.acquire(blocking=False)
            if acquired or not electricity_sem:
                try:
                        voltage, current, power, energy, frequency, power_factor, alarm = sensors.get_electricity_values()
                        current_state["electricity_voltage"] = voltage if isinstance(voltage, (int, float)) else "Read Error"
                        current_state["electricity_current"] = current if isinstance(current, (int, float)) else "Read Error"
                        current_state["electricity_power"] = power if isinstance(power, (int, float)) else "Read Error"
                        current_state["electricity_energy"] = energy if isinstance(energy, (int, float)) else "Read Error" # This is the cumulative energy
                        current_state["electricity_frequency"] = frequency if isinstance(frequency, (int, float)) else "Read Error"
                        current_state["electricity_pf"] = power_factor if isinstance(power_factor, (int, float)) else "Read Error"
                        current_state["electricity_alarm"] = str(alarm)
                except Exception as e: 
                    print(f"Logger Error reading Electricity: {e}"); current_state["electricity_voltage"] = "Ex"; current_state["electricity_current"] = "Ex"; current_state["electricity_power"] = "Ex"; current_state["electricity_energy"] = "Ex"; current_state["electricity_frequency"] = "Ex"; current_state["electricity_pf"] = "Ex"; current_state["electricity_alarm"] = "Ex"
                finally: 
                    if acquired: electricity_sem.release()
                last_read_datetimes["electricity"] = now
            else: 
                with data_lock: current_state["electricity_voltage"] = latest_data["electricity_voltage"]; current_state["electricity_current"] = latest_data["electricity_current"]; current_state["electricity_power"] = latest_data["electricity_power"]; current_state["electricity_energy"] = latest_data["electricity_energy"]; current_state["electricity_frequency"] = latest_data["electricity_frequency"]; current_state["electricity_pf"] = latest_data["electricity_pf"]; current_state["electricity_alarm"] = latest_data["electricity_alarm"]
        else:
            with data_lock: current_state["electricity_voltage"] = latest_data["electricity_voltage"]; current_state["electricity_current"] = latest_data["electricity_current"]; current_state["electricity_power"] = latest_data["electricity_power"]; current_state["electricity_energy"] = latest_data["electricity_energy"]; current_state["electricity_frequency"] = latest_data["electricity_frequency"]; current_state["electricity_pf"] = latest_data["electricity_pf"]; current_state["electricity_alarm"] = latest_data["electricity_alarm"]

        # Light Intensity (3s)
        if now >= last_read_datetimes["light"] + intervals["light"]:
            acquired = False
            if light_sem: acquired = light_sem.acquire(blocking=False)
            if acquired or not light_sem:
                try:
                    light = sensors.get_light_intensity()
                    current_state["light_intensity"] = light if isinstance(light, (int, float)) else "Read Error"
                except Exception as e: print(f"Logger Error reading Light: {e}"); current_state["light_intensity"] = "Exception"
                finally: 
                    if acquired: light_sem.release()
                last_read_datetimes["light"] = now
            else: 
                with data_lock: current_state["light_intensity"] = latest_data["light_intensity"]
        else:
            with data_lock: current_state["light_intensity"] = latest_data["light_intensity"]

        # Actuator Duty Cycles (1s)
        if now >= last_read_datetimes["actuators"] + intervals["actuators"]:
            try: current_state["heater_dc"] = actuators.get_heater_duty_cycle()
            except AttributeError: current_state["heater_dc"] = "Not Impl."
            except Exception as e: print(f"Logger Error reading Heater DC: {e}"); current_state["heater_dc"] = "Error"
            try: current_state["heater_fan_dc"] = actuators.get_heater_fan_duty_cycle()
            except AttributeError: current_state["heater_fan_dc"] = "Not Impl."
            except Exception as e: print(f"Logger Error reading Heater Fan DC: {e}"); current_state["heater_fan_dc"] = "Error"
            try: current_state["light_strip_1_dc"] = actuators.get_light_strip_1_duty_cycle()
            except AttributeError: current_state["light_strip_1_dc"] = "Not Impl."
            except Exception as e: print(f"Logger Error reading Light 1 DC: {e}"); current_state["light_strip_1_dc"] = "Error"
            try: current_state["light_strip_2_dc"] = actuators.get_light_strip_2_duty_cycle()
            except AttributeError: current_state["light_strip_2_dc"] = "Not Impl."
            except Exception as e: print(f"Logger Error reading Light 2 DC: {e}"); current_state["light_strip_2_dc"] = "Error"
            try: current_state["water_pump_dc"] = actuators.get_water_pump_duty_cycle()
            except AttributeError: current_state["water_pump_dc"] = "Not Impl."
            except Exception as e: print(f"Logger Error reading Pump DC: {e}"); current_state["water_pump_dc"] = "Error"
            try: current_state["fan_dc"] = actuators.get_fan_duty_cycle()
            except AttributeError: current_state["fan_dc"] = "Not Impl."
            except Exception as e: print(f"Logger Error reading Fan DC: {e}"); current_state["fan_dc"] = "Error"
            last_read_datetimes["actuators"] = now
        else:
            with data_lock: current_state["heater_dc"] = latest_data["heater_dc"]; current_state["heater_fan_dc"] = latest_data["heater_fan_dc"]; current_state["light_strip_1_dc"] = latest_data["light_strip_1_dc"]; current_state["light_strip_2_dc"] = latest_data["light_strip_2_dc"]; current_state["water_pump_dc"] = latest_data["water_pump_dc"]; current_state["fan_dc"] = latest_data["fan_dc"]

        # --- Read Mode and Setpoints (1s) --- 
        if now >= last_read_datetimes["setpoints"] + intervals["setpoints"]:
            try:
                current_state["mode"] = setpoints.operation_mode
                current_state["temp_sp"] = setpoints.get_temperature_setpoint()
                # current_state["hum_sp"] = setpoints.get_humidity_setpoint()
                current_state["light_sp"] = setpoints.get_light_setpoint()
                # current_state["soil_ph_sp"] = setpoints.get_soil_ph_setpoint()
                # current_state["soil_ec_sp"] = setpoints.get_soil_ec_setpoint()
                # current_state["soil_temp_sp"] = setpoints.get_soil_temp_setpoint()
                current_state["soil_hum_sp"] = setpoints.get_soil_humidity_setpoint()
                # current_state["flow_sp"] = setpoints.get_water_flow_setpoint()
            except Exception as e: print(f"Logger Error reading Setpoints: {e}"); current_state["mode"] = "Error"; current_state["temp_sp"] = "Error"; current_state["hum_sp"] = "Error"; current_state["light_sp"] = "Error"; current_state["soil_ph_sp"] = "Error"; current_state["soil_ec_sp"] = "Error"; current_state["soil_temp_sp"] = "Error"; current_state["soil_hum_sp"] = "Error"; current_state["flow_sp"] = "Error"
            last_read_datetimes["setpoints"] = now
        else:
            with data_lock: current_state["mode"] = latest_data["mode"]; current_state["temp_sp"] = latest_data["temp_sp"]; current_state["hum_sp"] = latest_data["hum_sp"]; current_state["light_sp"] = latest_data["light_sp"]; current_state["soil_ph_sp"] = latest_data["soil_ph_sp"]; current_state["soil_ec_sp"] = latest_data["soil_ec_sp"]; current_state["soil_temp_sp"] = latest_data["soil_temp_sp"]; current_state["soil_hum_sp"] = latest_data["soil_hum_sp"]; current_state["flow_sp"] = latest_data["flow_sp"]

        # Update global state safely
        with data_lock:
            latest_data.update(current_state)

        # --- Formatting --- 
        left_col1_width = 18; left_col2_width = 18
        right_col1_width = 25; right_col2_width = 25
        separator = " | "
        left_total_width = left_col1_width + left_col2_width + 3
        right_total_width = right_col1_width + right_col2_width + 3

        def format_value(value, unit):
            if isinstance(value, (int, float)):
                if unit == "Wh" or unit == "L": formatted_val = f"{value:.3f}"
                elif unit in ["A", "PF", "L/min", "L/h"]: formatted_val = f"{value:.2f}"
                elif unit == "Lux": formatted_val = f"{value:.0f}"
                elif isinstance(value, float): formatted_val = f"{value:.1f}"
                else: formatted_val = str(value)
                return f"{formatted_val} {unit}" if unit else formatted_val
            else: return str(value)

        # Build Left Table (Sensors/Actuators)
        left_lines = []
        left_sep =    '+' + '-' * left_col1_width + '+' + '-' * left_col2_width + '+'
        left_header = '|' + " Sensor".ljust(left_col1_width) + '|' + " Value".ljust(left_col2_width) + '|'
        act_header =  '|' + " Actuator".ljust(left_col1_width) + '|' + " Duty Cycle (Raw%)".ljust(left_col2_width) + '|'
        left_lines.append(left_sep)
        left_lines.append('|' + " Greenhouse Monitor".center(left_total_width - 2) + '|')
        left_lines.append(left_sep)
        left_lines.append('|' + f" Timestamp: {current_state['timestamp']} ".ljust(left_total_width - 2) + '|')
        left_lines.append(left_sep)
        left_lines.append(left_header)
        left_lines.append(left_sep)
        sensors_to_print = [
            ("Temp (Air)", "temperature", "C"), ("Humidity (Air)", "humidity", "%"),
            ("Light Intensity", "light_intensity", "Lux"), ("Soil pH", "soil_ph", "pH"),
            ("Soil EC", "soil_ec", "uS/cm"), ("Soil Temp", "soil_temp", "C"),
            ("Soil Humidity", "soil_humidity", "%"), ("Water Flow", "water_flow", "L/min"),
            ("Voltage", "electricity_voltage", "V"), ("Current", "electricity_current", "A"),
            ("Power", "electricity_power", "W"), ("Energy", "electricity_energy", "Wh"), # Display instantaneous energy here
            ("Frequency", "electricity_frequency", "Hz"), ("Power Factor", "electricity_pf", "PF"),
            ("Alarm Status", "electricity_alarm", "")
        ]
        for name, key, unit in sensors_to_print:
            val_str = format_value(current_state.get(key, "N/A"), unit)
            left_lines.append('|' + f" {name}".ljust(left_col1_width) + '|' + f" {val_str}".ljust(left_col2_width) + '|')
        left_lines.append(left_sep)
        left_lines.append(act_header)
        left_lines.append(left_sep)
        max_dc = 4095
        actuators_to_print = [
            ("Heater", "heater_dc"), ("Heater Fan", "heater_fan_dc"),
            ("Light Strip 1", "light_strip_1_dc"), ("Light Strip 2", "light_strip_2_dc"),
            ("Water Pump", "water_pump_dc"), ("Cooling Fan", "fan_dc")
        ]
        for name, key in actuators_to_print:
            dc = current_state.get(key, "N/A")
            if isinstance(dc, (int, float)): val_str = f"{dc:<4} ({(dc / max_dc * 100) if max_dc > 0 else 0:.1f}%)"
            else: val_str = str(dc)
            left_lines.append('|' + f" {name}".ljust(left_col1_width) + '|' + f" {val_str}".ljust(left_col2_width) + '|')
        left_lines.append(left_sep)

        # Build Right Top Table (Mode/Setpoints)
        right_top_lines = []
        right_sep =    '+' + '-' * right_col1_width + '+' + '-' * right_col2_width + '+'
        right_header = '|' + " Mode / Setpoint".ljust(right_col1_width) + '|' + " Value".ljust(right_col2_width) + '|'
        right_top_lines.append(right_sep)
        right_top_lines.append('|' + " Control Status".center(right_total_width - 2) + '|')
        right_top_lines.append(right_sep)
        right_top_lines.append(right_header)
        right_top_lines.append(right_sep)
        mode_str = str(current_state.get("mode", "N/A"))
        right_top_lines.append('|' + " Mode".ljust(right_col1_width) + '|' + f" {mode_str}".ljust(right_col2_width) + '|')
        right_top_lines.append(right_sep)
        setpoints_to_print = [
            ("Temp SP", "temp_sp", "C"),
            # ("Humidity SP", "hum_sp", "%"),
            ("Light SP", "light_sp", "Lux"), 
            # ("Soil pH SP", "soil_ph_sp", "pH"),
            # ("Soil EC SP", "soil_ec_sp", "uS/cm"), 
            # ("Soil Temp SP", "soil_temp_sp", "C"),
            ("Soil Humidity SP", "soil_hum_sp", "%"), 
            # ("Water Flow SP", "flow_sp", "L/h")
        ]
        for name, key, unit in setpoints_to_print:
            val_str = format_value(current_state.get(key, "N/A"), unit)
            right_top_lines.append('|' + f" {name}".ljust(right_col1_width) + '|' + f" {val_str}".ljust(right_col2_width) + '|')
        right_top_lines.append(right_sep)

        # Build Right Bottom Table (Resources)
        right_bottom_lines = []
        res_header = '|' + " Resource".ljust(right_col1_width) + '|' + " Consumption".ljust(right_col2_width) + '|'
        # No top title for this one, just append to the right column
        right_bottom_lines.append(res_header)
        right_bottom_lines.append(right_sep)
        resources_to_print = [
            ("Water Consumed", "water_consumed", "L"),
            ("Energy Consumed", "electricity_energy", "Wh"), # Get latest cumulative energy reading
            ("Last Resource Reset", "last_resource_reset", ""), # Not printing this as it is a datetime
            ("Last Update Readings", "last_update_readings", "") # Not printing this as it is a datetime
        ]
        for name, key, unit in resources_to_print:
            val_str = format_value(current_state.get(key, "N/A"), unit)
            right_bottom_lines.append('|' + f" {name}".ljust(right_col1_width) + '|' + f" {val_str}".ljust(right_col2_width) + '|')
        right_bottom_lines.append(right_sep)

        # Combine Right Tables Vertically
        right_lines = right_top_lines + right_bottom_lines

        # Combine Left and Right Tables Horizontally
        max_lines = max(len(left_lines), len(right_lines))
        combined_output = []
        left_blank = ' ' * left_total_width
        right_blank = ' ' * right_total_width
        for i in range(max_lines):
            left_line = left_lines[i] if i < len(left_lines) else left_blank
            right_line = right_lines[i] if i < len(right_lines) else right_blank
            combined_output.append(left_line + separator + right_line)

        # Print Output
        os.system('clear')
        print("\n".join(combined_output))

        # Sleep
        time.sleep(1)

# --- Placeholder for Integration --- 
# (Integration example remains the same as previous version)


