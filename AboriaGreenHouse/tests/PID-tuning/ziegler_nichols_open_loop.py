#!/usr/bin/env python3
"""
PID Auto-Tuning Script using Ziegler-Nichols Open-Loop (Reaction Curve) Method
For Raspberry Pi 5 with temperature control systems

This script implements the Ziegler-Nichols open-loop method for PID tuning:
1. Start with the system stable at an initial temperature.
2. Apply a step change to the actuator (e.g., heater).
3. Record the process variable (temperature) response over time.
4. Analyze the reaction curve to determine process gain (K), dead time (L), and time constant (T).
5. Calculate PID parameters based on Ziegler-Nichols rules.
"""

import time
import argparse
import numpy as np
import matplotlib.pyplot as plt
import os
import datetime
import board
import busio
from Actuators.actuators import GH_Actuators # Assuming this path is correct relative to script location
from Sensors.air import AirSensor # Assuming this path is correct

# ===== HARDWARE INITIALIZATION =====
# Extracted from user's provided script

print("Initializing hardware...")
airTemp = AirSensor()
airTemp.set_dht22_pin(board.D26)  # Set the pin for DHT22 sensor

i2cBus = busio.I2C(board.SCL, board.SDA)
act = GH_Actuators(esp32_i2c_address=0x30, i2c_bus=i2cBus, frame_endianes='big')
print("Initializing actuators (restarting ESP32)...", end='')
act.restart_esp32()
last_date_time = datetime.datetime.now()
while datetime.datetime.now() - last_date_time < datetime.timedelta(seconds=10):
    print(".", end='')
    time.sleep(1)
print(" done.")

# Setup actuators (ensure these pins/channels/frequencies are correct for your setup)
print("Configuring actuators...")
# Heater setup
while not act.setup_heater_esp32(pin=17, channel=1, timer_src=1, frequency=50, duty_cycle=0):
    print("Retrying heater setup...")
    time.sleep(5)
time.sleep(1)
# Heater Fan setup
while not act.setup_heater_fan_esp32(pin=18, channel=2, timer_src=0, frequency=5000, duty_cycle=0):
    print("Retrying heater fan setup...")
    time.sleep(5)
time.sleep(1)
# Cooling Fan setup
while not act.setup_fan_esp32(pin=19, channel=3, timer_src=0, frequency=5000, duty_cycle=0):
    print("Retrying cooling fan setup...")
    time.sleep(5)
time.sleep(1)
print("Hardware initialization complete.")

# ===== HARDWARE INTERFACE FUNCTIONS =====
# Using functions provided by the user

def read_temperature():
    """
    Reads temperature from the actual DHT22 sensor using AirSensor class.
    Returns: float - current temperature in degrees Celsius
    """
    try:
        temp = airTemp.get_air_temperature_C()
        if temp is None:
            print("Warning: Failed to read temperature (returned None)")
            # Decide how to handle failed readings, e.g., return last known good value or raise error
            # For now, returning a placeholder, but this should be handled robustly
            return 25.0 # Placeholder - adjust as needed
        return temp
    except Exception as e:
        print(f"Error in read_temperature: {e}")
        # Handle exception appropriately
        return 25.0 # Placeholder

def set_heater_power(power_level):
    """
    Controls the heater and its associated fan using GH_Actuators class.
    Args:
        power_level: int - PWM value (0-4095)
    """
    power_level = max(0, min(4095, int(power_level))) # Ensure valid range
    # Set heater power
    while not act.set_heater_duty_cycle(power_level):
        print("Retrying set_heater_duty_cycle...")
        time.sleep(0.1)
    # Set heater fan power (assuming it matches heater power)
    while not act.set_heater_fan_duty_cycle(power_level):
        print("Retrying set_heater_fan_duty_cycle...")
        time.sleep(0.1)

def set_fan_power(power_level):
    """
    Controls the cooling fan using GH_Actuators class.
    Args:
        power_level: int - PWM value (0-4095)
    """
    power_level = max(0, min(4095, int(power_level))) # Ensure valid range
    while not act.set_fan_duty_cycle(power_level):
        print("Retrying set_fan_duty_cycle...")
        time.sleep(0.1)

# ===== REACTION CURVE ANALYSIS (Improved Logic) =====

def moving_average(data, window_size):
    """Calculate moving average"""
    if window_size <= 0 or window_size > len(data):
        return data # Return original data if window size is invalid
    return np.convolve(data, np.ones(window_size)/window_size, mode='valid')

def analyze_reaction_curve(times, pv_values, step_time, step_magnitude, initial_pv):
    """
    Analyze the reaction curve data to find K, L, and T (Improved Logic).
    Args:
        times: list - time points (seconds)
        pv_values: list - process variable values
        step_time: float - time when the step change was applied
        step_magnitude: float - magnitude of the step change in actuator output (0-4095)
        initial_pv: float - initial stable process variable value
    Returns:
        dict - containing K, L, T or None if analysis fails
    """
    print("Analyzing reaction curve (Improved Logic)...")
    
    if len(times) < 20: # Increased minimum points for better analysis
        print("Error: Not enough data points for analysis.")
        return None
        
    # Convert to numpy arrays
    times = np.array(times)
    pv_values = np.array(pv_values)
    
    # --- Smoothing --- 
    # Apply a larger moving average window for smoothing PV for slope calculation
    smooth_window_pv = 10 # Adjust window size as needed
    smoothed_pv = moving_average(pv_values, smooth_window_pv)
    # Adjust times array to match smoothed_pv length
    smoothed_times = times[smooth_window_pv//2 : len(times) - (smooth_window_pv-1)//2]
    
    if len(smoothed_pv) < 2:
        print("Error: Not enough data points after smoothing.")
        return None
        
    # --- Find Process Gain (K) --- 
    # Use average of last ~10% of points as final_pv for stability
    num_final_points = max(5, len(pv_values) // 10) # Use last 10% or at least 5 points
    final_pv = np.mean(pv_values[-num_final_points:])
    delta_pv = final_pv - initial_pv
    delta_output = step_magnitude # Change in actuator output
    
    if abs(delta_output) < 1e-6:
        print("Error: Step magnitude is zero.")
        return None
    if abs(delta_pv) < 1e-6:
        print("Error: No significant change in PV observed.")
        return None
        
    process_gain_K = delta_pv / delta_output
    print(f"Process Gain (K): {process_gain_K:.6f} units / actuator_unit")

    # --- Find Maximum Slope (R) and Time of Max Slope --- 
    # Calculate slopes from the SMOOTHED PV data
    slopes = np.diff(smoothed_pv) / np.diff(smoothed_times)
    slope_times = (smoothed_times[:-1] + smoothed_times[1:]) / 2 # Midpoint times for slopes
    
    # Optional: Smooth the slopes themselves (smaller window)
    smooth_window_slope = 5
    if len(slopes) > smooth_window_slope:
        valid_slope_window = min(smooth_window_slope, len(slopes))
        smoothed_slopes = moving_average(slopes, valid_slope_window)
        smoothed_slope_times = slope_times[valid_slope_window//2 : len(slope_times) - (valid_slope_window-1)//2]
    else:
        smoothed_slopes = slopes
        smoothed_slope_times = slope_times

    if len(smoothed_slopes) == 0:
        print("Error: Could not calculate slopes effectively.")
        return None
        
    # Find the maximum slope R and the time it occurs
    max_slope_index = np.argmax(smoothed_slopes)
    max_slope = smoothed_slopes[max_slope_index]
    time_at_max_slope = smoothed_slope_times[max_slope_index]
    
    # Get the ORIGINAL PV value at the time of max slope using interpolation
    pv_at_max_slope = np.interp(time_at_max_slope, times, pv_values)
    
    if max_slope <= 1e-6: # Check if slope is practically zero
        print("Error: Maximum slope is too small. System might not be responding.")
        return None
        
    print(f"Maximum slope (R): {max_slope:.4f} units/sec at t={time_at_max_slope:.2f}s")
    
    # --- Find Dead Time (L) --- 
    # Calculate tangent line intersection with initial_pv
    # y = m(t - t1) + y1 => initial_pv = max_slope * (t_intersect - time_at_max_slope) + pv_at_max_slope
    t_intersect = time_at_max_slope + (initial_pv - pv_at_max_slope) / max_slope
    
    # Dead time L is the time from step_time to t_intersect
    dead_time_L = t_intersect - step_time
    
    # Ensure L is not negative and not excessively large (e.g., > time_at_max_slope)
    if dead_time_L < 0:
        print(f"Warning: Calculated dead time L ({dead_time_L:.2f}s) is negative. Clamping to 0.")
        dead_time_L = 0
    elif dead_time_L > time_at_max_slope:
         print(f"Warning: Calculated dead time L ({dead_time_L:.2f}s) seems large (>{time_at_max_slope:.2f}s). Check plot.")
         # Consider alternative L estimation if this happens often, e.g., time to reach initial_pv + noise_threshold

    print(f"Dead Time (L): {dead_time_L:.4f} seconds")
    
    # --- Find Time Constant (T) --- 
    # Method 1: Using 63.2% rise time (potentially more robust than slope method)
    pv_target_t = initial_pv + 0.632 * delta_pv
    try:
        # Find the first time the SMOOTHED PV crosses the target value
        t63_indices = np.where(smoothed_pv >= pv_target_t)[0]
        if len(t63_indices) > 0:
            t63_index = t63_indices[0]
            # Interpolate for better accuracy
            if t63_index > 0:
                t1, pv1 = smoothed_times[t63_index-1], smoothed_pv[t63_index-1]
                t2, pv2 = smoothed_times[t63_index], smoothed_pv[t63_index]
                if pv2 - pv1 > 1e-6: # Avoid division by zero
                    t_63 = t1 + (t2 - t1) * (pv_target_t - pv1) / (pv2 - pv1)
                else:
                    t_63 = smoothed_times[t63_index]
            else:
                 t_63 = smoothed_times[t63_index]
                 
            time_constant_T = t_63 - dead_time_L
            print(f"Time Constant (T) from 63.2% rise: {time_constant_T:.4f} seconds (at t={t_63:.2f}s)")
        else:
            # Fallback to slope method if 63.2% point not reached or found
            print("Warning: 63.2% rise point not clearly found. Falling back to T = delta_pv / max_slope.")
            time_constant_T = delta_pv / max_slope
            print(f"Time Constant (T) from slope: {time_constant_T:.4f} seconds")
            
    except Exception as e:
        print(f"Error calculating T using 63.2% method: {e}. Falling back to slope method.")
        time_constant_T = delta_pv / max_slope
        print(f"Time Constant (T) from slope: {time_constant_T:.4f} seconds")

    if time_constant_T <= 0:
        print(f"Error: Calculated time constant T ({time_constant_T:.4f}) is not positive.")
        # Attempt fallback using slope method if not already used
        if 't_63' in locals(): # Check if fallback already happened
             time_constant_T_slope = delta_pv / max_slope
             if time_constant_T_slope > 0:
                 print(f"Using T from slope as fallback: {time_constant_T_slope:.4f}s")
                 time_constant_T = time_constant_T_slope
             else:
                 return None # Both methods failed
        else:
             return None # Slope method already failed
        
    # Store tangent line points for plotting (using the calculated L and T)
    tangent_t = np.array([dead_time_L + step_time, dead_time_L + step_time + time_constant_T])
    tangent_pv = np.array([initial_pv, final_pv]) # Tangent goes from (L, initial_pv) to (L+T, final_pv)
    
    return {
        "K": process_gain_K,
        "L": dead_time_L,
        "T": time_constant_T,
        "max_slope": max_slope,
        "tangent_t": tangent_t,
        "tangent_pv": tangent_pv
    }

# ===== ZIEGLER-NICHOLS PARAMETER CALCULATION =====

def calculate_zn_open_loop_params(K, L, T):
    """
    Calculate PID parameters using Ziegler-Nichols open-loop rules.
    Args:
        K: Process Gain
        L: Dead Time
        T: Time Constant
    Returns:
        dict - containing PID parameters for P, PI, PID controllers
    """
    if K is None or L is None or T is None or T <= 0 or K == 0 or L < 0:
        print("Error: Invalid K, L, or T values for ZN calculation.")
        return None
    if L <= 1e-6: # Check if L is effectively zero
        print("Warning: Dead time L is near zero. ZN rules might be unstable or result in very high gains.")
        # Avoid division by zero, but results might be poor. Consider alternative tuning if L is truly zero.
        L = 1e-6 
        
    params = {
        "P": {
            "Kp": T / (K * L),
            "Ki": 0.0,
            "Kd": 0.0
        },
        "PI": {
            "Kp": 0.9 * T / (K * L),
            "Ki": (0.9 * T / (K * L)) / (L / 0.3), # Ki = Kp / Ti, Ti = L / 0.3 -> Kp * 0.3 / L
            "Kd": 0.0
        },
        "Classic PID": { # Original ZN PID rule
            "Kp": 1.2 * T / (K * L),
            "Ki": (1.2 * T / (K * L)) / (2 * L), # Ki = Kp / Ti, Ti = 2L -> Kp / (2*L)
            "Kd": (1.2 * T / (K * L)) * (0.5 * L) # Kd = Kp * Td, Td = 0.5L -> Kp * L / 2
        }
        # Add other variations if needed (e.g., Cohen-Coon)
    }
    return params

# ===== PLOTTING =====

def plot_reaction_curve(times, pv_values, analysis_results, initial_pv, step_time, final_pv):
    """
    Generate plot of the reaction curve and analysis.
    """
    try:
        plt.figure(figsize=(12, 8))
        plt.plot(times, pv_values, label='Process Variable (Temperature)')
        plt.axhline(y=initial_pv, color='gray', linestyle='--', label=f'Initial PV ({initial_pv:.2f})')
        plt.axhline(y=final_pv, color='gray', linestyle=':', label=f'Final PV ({final_pv:.2f})')
        plt.axvline(x=step_time, color='red', linestyle='--', label='Step Input Time')
        
        if analysis_results:
            K = analysis_results['K']
            L = analysis_results['L']
            T = analysis_results['T']
            tangent_t = analysis_results['tangent_t']
            tangent_pv = analysis_results['tangent_pv']
            
            # Plot tangent line based on calculated L and T
            plt.plot(tangent_t, tangent_pv, 'g--', label=f'Calculated Tangent (L={L:.2f}s, T={T:.2f}s)')
            
            # Mark dead time L
            plt.plot([step_time, step_time + L], [initial_pv, initial_pv], 'm-', linewidth=3, label=f'Dead Time (L={L:.2f}s)')
            # Mark time constant T (from end of dead time)
            plt.plot([step_time + L, step_time + L + T], [final_pv, final_pv], 'c-', linewidth=3, label=f'Time Constant (T={T:.2f}s)')
            
            # Optionally plot the 63.2% point if calculated
            pv_target_t = initial_pv + 0.632 * (final_pv - initial_pv)
            plt.axhline(y=pv_target_t, color='orange', linestyle='-.', label=f'63.2% Rise ({pv_target_t:.2f})')
            t_63 = L + T # Time when 63.2% rise is reached
            plt.axvline(x=t_63, color='orange', linestyle='-.', label=f'Time at 63.2% (t={t_63:.2f}s)')

            plt.title(f'Reaction Curve Analysis (K={K:.4f}, L={L:.2f}s, T={T:.2f}s)')
        else:
            plt.title('Reaction Curve')
            
        plt.xlabel('Time (s)')
        plt.ylabel('Temperature (°C)')
        plt.legend()
        plt.grid(True)
        
        plot_filename = 'reaction_curve_analysis.png'
        plt.savefig(plot_filename)
        print(f"Plot saved to {plot_filename}")
        plt.close()
    except Exception as e:
        print(f"Error generating plot: {e}")

# ===== MAIN FUNCTION =====

def main():
    parser = argparse.ArgumentParser(description='PID Autotuning using Ziegler-Nichols Open-Loop method')
    parser.add_argument('--step-power', type=int, required=True,
                        help='Heater power level for the step input (0-4095)')
    parser.add_argument('--duration', type=float, required=True,
                        help='Duration of the step test in seconds')
    parser.add_argument('--sample-time', type=float, default=1.0,
                        help='Time between sensor readings in seconds')
    parser.add_argument('--stability-time', type=float, default=60.0,
                        help='Time to wait for system stability before starting test')
    parser.add_argument('--no-plot', action='store_true',
                        help='Disable plotting of results')

    args = parser.parse_args()
    
    # --- Initialization --- 
    print("Ensuring actuators are off before stability period...")
    set_heater_power(0)
    set_fan_power(0)
    print(f"Waiting {args.stability_time} seconds for system to stabilize...")
    
    # Monitor stability
    stability_start_time = time.time()
    stable_temps = []
    while time.time() - stability_start_time < args.stability_time:
        temp = read_temperature()
        stable_temps.append(temp)
        print(f"Stabilizing... Current Temp: {temp:.2f}°C (Remaining: {args.stability_time - (time.time() - stability_start_time):.0f}s)", end='\r')
        time.sleep(args.sample_time)
    print("\nStability period finished.")
    
    if not stable_temps:
        print("Error: Could not read temperature during stability period. Exiting.")
        return
        
    initial_temp = np.mean(stable_temps[-5:]) # Average last 5 readings
    print(f"Initial stable temperature: {initial_temp:.2f}°C")
    
    # --- Step Test --- 
    print(f"Applying step input: Heater power = {args.step_power}")
    print(f"Test duration: {args.duration} seconds")
    print("Press Ctrl+C to stop early.")
    
    times = []
    pv_values = []
    start_time = time.time()
    step_applied_time = start_time
    last_sample_time = start_time
    
    set_heater_power(args.step_power)
    set_fan_power(0) # Ensure cooling fan is off during heating test
    
    try:
        while time.time() - start_time < args.duration:
            current_time = time.time()
            if current_time - last_sample_time >= args.sample_time:
                temp = read_temperature()
                elapsed_time = current_time - start_time
                
                times.append(elapsed_time)
                pv_values.append(temp)
                
                # Real-time display
                os.system('cls' if os.name == 'nt' else 'clear')
                print(f"--- Open-Loop Step Test --- Heater Power: {args.step_power} ---")
                print(f"Elapsed Time: {elapsed_time:.1f}s / {args.duration:.0f}s")
                print(f"Current Temp: {temp:.2f}°C (Initial: {initial_temp:.2f}°C)")
                print("\n(Recording reaction curve... Press Ctrl+C to stop)")
                
                last_sample_time = current_time
            
            time.sleep(0.05) # Small delay
            
    except KeyboardInterrupt:
        print("\nStep test stopped by user.")
        
    finally:
        # Turn off actuators
        print("\nTurning off actuators...")
        set_heater_power(0)
        set_fan_power(0)
        print("Actuators turned off.")
        
    # --- Analysis --- 
    if not times or len(times) < 2:
        print("No sufficient data collected. Exiting.")
        return
        
    analysis_results = analyze_reaction_curve(
        times,
        pv_values,
        step_time=0, # Step was applied at time 0 relative to data collection
        step_magnitude=args.step_power,
        initial_pv=initial_temp
    )
    
    # --- Parameter Calculation --- 
    pid_params = None
    if analysis_results:
        pid_params = calculate_zn_open_loop_params(
            analysis_results['K'],
            analysis_results['L'],
            analysis_results['T']
        )
        
        if pid_params:
            print("\nZiegler-Nichols Open-Loop Tuning Results:")
            for controller_type, params in pid_params.items():
                print(f"{controller_type}: Kp={params['Kp']:.4f}, Ki={params['Ki']:.4f}, Kd={params['Kd']:.4f}")
                
            # Save results to file
            output_filename = "temperature_pid_parameters_open_loop.txt"
            with open(output_filename, "w") as f:
                f.write("# PID parameters for temperature control (ZN Open-Loop Method)\n")
                f.write(f"# Step Power: {args.step_power}\n")
                f.write(f"# Initial Temp: {initial_temp:.2f}\n")
                f.write(f"# K = {analysis_results['K']:.6f}\n")
                f.write(f"# L = {analysis_results['L']:.6f}\n")
                f.write(f"# T = {analysis_results['T']:.6f}\n\n")
                for controller_type, params in pid_params.items():
                    f.write(f"## {controller_type}\n")
                    f.write(f"Kp = {params['Kp']:.6f}\n")
                    f.write(f"Ki = {params['Ki']:.6f}\n")
                    f.write(f"Kd = {params['Kd']:.6f}\n\n")
            print(f"PID parameters saved to {output_filename}")
        else:
            print("\nFailed to calculate PID parameters from analysis results.")
    else:
        print("\nReaction curve analysis failed. Cannot calculate PID parameters.")
        
    # --- Plotting --- 
    if not args.no_plot and times:
        # Define num_final_points here for plotting scope
        num_final_points = max(5, len(pv_values) // 10) 
        actual_final_pv = np.mean(pv_values[-num_final_points:]) 
        plot_reaction_curve(
            times,
            pv_values,
            analysis_results,
            initial_pv=initial_temp,
            step_time=0,
            final_pv=actual_final_pv
        )

if __name__ == "__main__":
    main()
