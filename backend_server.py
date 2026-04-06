"""
================================================================================
HYBRID DIGITAL TWIN - BACKEND SERVER (WITH REALISTIC SIMULATION)
================================================================================
"""

import asyncio
import json
import struct
import socket
import os
import random
import math
from typing import Dict, Optional, List
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import numpy as np

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ============================================================================
# CONFIGURATION
# ============================================================================

PROJECT_DIR = r"C:\Users\ishaa\Documents\5th sem el\main el"
MODEL_DIR = os.path.join(PROJECT_DIR, "model_artifacts")
DATA_DIR = os.path.join(PROJECT_DIR, "data")

BACKEND_HOST = "0.0.0.0"
BACKEND_PORT = 8000
BLENDER_HOST = "localhost"
BLENDER_PORT = 5555

SEQ_LEN = 50
RUL_CLIP = 125

executor = ThreadPoolExecutor(max_workers=2)

ANSYS_PHYSICS = {
    'chamber_temp_max': 627.0,
    'nozzle_temp_max': 475.0,
    'stress_min_mpa': 54.195,
    'stress_max_mpa': 3543.9,
    'deformation_max_mm': 0.18929,
}

# OPTIMAL SENSORS = Brand new engine (gives RUL = 125)
OPTIMAL_SENSORS = {
    's_1': 518.67, 's_2': 642.0, 's_3': 1545.0, 's_4': 1370.0,
    's_5': 14.62, 's_6': 21.61, 's_7': 515.0, 's_8': 2388.0,
    's_9': 9046.0, 's_10': 1.3, 's_11': 7820.0, 's_12': 392.0,
    's_13': 2388.0, 's_14': 8130.0, 's_15': 8.58, 's_16': 0.03,
    's_17': 392.0, 's_18': 2388.0, 's_19': 100.0, 's_20': 39.0,
    's_21': 23.4, 'op_1': 0.0, 'op_2': 0.0, 'op_3': 100.0
}

# CRITICAL SENSORS = Engine about to fail
CRITICAL_SENSORS = {
    's_3': 1650.0, 's_4': 1450.0, 's_7': 600.0, 's_11': 9500.0, 's_15': 8.0,
}

def determine_status(rul: float) -> str:
    if rul <= 15:
        return 'CRITICAL'
    elif rul <= 40:
        return 'WARNING'
    elif rul <= 70:
        return 'DEGRADED'
    else:
        return 'HEALTHY'


# ============================================================================
# REALISTIC ENGINE SIMULATOR
# ============================================================================

class RealisticEngineSimulator:
    """
    Simulates realistic engine sensor behavior with:
    - Random fluctuations (operational noise)
    - Maintenance events (temporary improvements)  
    - Non-linear degradation (bathtub curve)
    - Fault development patterns
    - Operating condition variations (gradual transitions)
    """
    
    def __init__(self):
        self.reset()
    
    def reset(self, initial_sensors: Dict = None):
        """Reset simulator for a new engine, optionally starting from given sensor values."""
        if initial_sensors is None:
            self._current_sensors = OPTIMAL_SENSORS.copy()
            self._initial_sensors = OPTIMAL_SENSORS.copy()
            self._accumulated_wear = 0.0
            print("    [Simulator] New engine initialized - starting at optimal condition")
        else:
            self._current_sensors = initial_sensors.copy()
            self._initial_sensors = initial_sensors.copy()
            # Calculate initial wear based on how far sensors are from optimal
            self._accumulated_wear = self._estimate_wear_from_sensors(initial_sensors)
            print(f"    [Simulator] Engine initialized from current sensors - estimated wear: {self._accumulated_wear:.2f}")

        self._base_wear = self._accumulated_wear
        self._initial_wear = self._accumulated_wear  # Store initial wear level
        self._last_maintenance_cycle = 0
        self._operating_mode = 'normal'
        self._target_mode_factor = 1.0
        self._current_mode_factor = 1.0
        self._stress_multiplier = 1.0 # Multiplier for degradation rate based on inputs
        self._fault_active = False
        self._fault_sensor = None
        self._fault_severity = 0.0
        self._sensor_noise = {f's_{i}': 0.0 for i in range(1, 22)}
        self._last_cycle = 0

    def update_state(self, new_sensors: Dict):
        """
        Update simulator baselines and stress factors based on user intervention.
        Does NOT reset accumulated wear, ensuring continuity of RUL.
        """
        if new_sensors:
            # 1. Update the BASELINES. This ensures that when simulation resumes,
            #    it uses these new values (e.g., 1650) as the starting point + wear.
            self._initial_sensors.update(new_sensors)
            self._current_sensors.update(new_sensors)
            
            # 2. Calculate Stress Multiplier (Rate of Degradation)
            stress = 1.0
            
            # Temperature s_3 (Hotter = Faster degradation)
            s3_diff = new_sensors.get('s_3', 1545) - OPTIMAL_SENSORS['s_3']
            if s3_diff > 0:
                stress += (s3_diff / 50.0) * 0.5
            
            # Pressure s_7 (Higher = Faster degradation)
            s7_diff = new_sensors.get('s_7', 515) - OPTIMAL_SENSORS['s_7']
            if s7_diff > 0:
                stress += (s7_diff / 40.0) * 0.3
                
            # Fan Speed s_11 (Higher = Better Cooling = Slower degradation)
            s11_diff = new_sensors.get('s_11', 7820) - OPTIMAL_SENSORS['s_11']
            if s11_diff > 0:
                stress -= (s11_diff / 1000.0) * 0.4 
            
            self._stress_multiplier = max(0.2, min(5.0, stress))
            
            # 3. CRITICAL: We DO NOT update self._accumulated_wear here.
            #    This preserves the "Age" of the engine.
    
    def apply_wear_to_inputs(self, inputs: Dict) -> Dict:
        """
        Apply the current accumulated wear to a new set of manual inputs.
        Used when the simulation is paused to show accurate RUL for the current
        wear level, rather than resetting to a 'new engine' state.
        """
        sensors = inputs.copy()
        
        # Calculate effective wear (same logic as main loop)
        incremental_wear = self._accumulated_wear - self._initial_wear
        effective_wear = min(1.0, incremental_wear * self._current_mode_factor)

        if self._fault_active:
             effective_wear = min(1.0, effective_wear + self._fault_severity * 0.15)

        # Apply to key sensors using the INPUT values as the baseline (init_sX)
        init_s3 = sensors.get('s_3', OPTIMAL_SENSORS['s_3'])
        init_s4 = sensors.get('s_4', OPTIMAL_SENSORS['s_4'])
        init_s7 = sensors.get('s_7', OPTIMAL_SENSORS['s_7'])
        init_s11 = sensors.get('s_11', OPTIMAL_SENSORS['s_11'])
        init_s15 = sensors.get('s_15', OPTIMAL_SENSORS['s_15'])
        
        # Temp s3
        temp_range = CRITICAL_SENSORS['s_3'] - init_s3
        sensors['s_3'] = init_s3 + effective_wear * max(0, temp_range)
        
        # Nozzle s4
        temp_range_s4 = CRITICAL_SENSORS['s_4'] - init_s4
        sensors['s_4'] = init_s4 + effective_wear * max(0, temp_range_s4)
        
        # Pressure s7
        pressure_range = CRITICAL_SENSORS['s_7'] - init_s7
        sensors['s_7'] = init_s7 + effective_wear * max(0, pressure_range)
        
        # Speed s11
        speed_range = CRITICAL_SENSORS['s_11'] - init_s11
        sensors['s_11'] = init_s11 + effective_wear * max(0, speed_range)
        
        # Bypass s15
        bypass_range = init_s15 - CRITICAL_SENSORS['s_15']
        sensors['s_15'] = init_s15 - effective_wear * max(0, bypass_range)
        
        # Add Faults
        if self._fault_active and self._fault_sensor:
             if self._fault_sensor == 's_3': sensors['s_3'] += self._fault_severity * 25
             elif self._fault_sensor == 's_7': sensors['s_7'] += self._fault_severity * 18
             elif self._fault_sensor == 's_11': sensors['s_11'] += self._fault_severity * 250
             elif self._fault_sensor == 's_15': sensors['s_15'] -= self._fault_severity * 0.25

        # We skip noise for manual mode to keep it stable
        return sensors
    
    def _estimate_wear_from_sensors(self, sensors: Dict) -> float:
        """Estimate wear level (0-1) based on current sensor values."""
        # Calculate how far each key sensor is from optimal toward critical
        s3 = sensors.get('s_3', OPTIMAL_SENSORS['s_3'])
        s7 = sensors.get('s_7', OPTIMAL_SENSORS['s_7'])
        s11 = sensors.get('s_11', OPTIMAL_SENSORS['s_11'])
        s15 = sensors.get('s_15', OPTIMAL_SENSORS['s_15'])
        
        # Normalize each sensor to 0-1 range (0 = optimal, 1 = critical)
        s3_wear = (s3 - OPTIMAL_SENSORS['s_3']) / (CRITICAL_SENSORS['s_3'] - OPTIMAL_SENSORS['s_3'])
        s7_wear = (s7 - OPTIMAL_SENSORS['s_7']) / (CRITICAL_SENSORS['s_7'] - OPTIMAL_SENSORS['s_7'])
        s11_wear = (s11 - OPTIMAL_SENSORS['s_11']) / (CRITICAL_SENSORS['s_11'] - OPTIMAL_SENSORS['s_11'])
        s15_wear = (OPTIMAL_SENSORS['s_15'] - s15) / (OPTIMAL_SENSORS['s_15'] - CRITICAL_SENSORS['s_15'])
        
        # Clamp to 0-1 range
        s3_wear = max(0, min(1, s3_wear))
        s7_wear = max(0, min(1, s7_wear))
        s11_wear = max(0, min(1, s11_wear))
        s15_wear = max(0, min(1, s15_wear))
        
        # Average wear across sensors
        avg_wear = (s3_wear + s7_wear + s11_wear + s15_wear) / 4
        return avg_wear
    
    def get_sensors_for_cycle(self, cycle: int) -> Dict:
        """Get realistic sensor values for a given cycle."""

        # Start from the initial sensors (user's custom values), not always OPTIMAL
        sensors = self._initial_sensors.copy()

        # For cycle 1, return the initial sensors with minimal noise (no jump)
        if cycle <= 1:
            # Add tiny noise but keep very close to initial values
            sensors['s_3'] = self._initial_sensors.get('s_3', OPTIMAL_SENSORS['s_3']) + random.gauss(0, 1)
            sensors['s_7'] = self._initial_sensors.get('s_7', OPTIMAL_SENSORS['s_7']) + random.gauss(0, 0.5)
            sensors['s_11'] = self._initial_sensors.get('s_11', OPTIMAL_SENSORS['s_11']) + random.gauss(0, 5)
            sensors['s_15'] = self._initial_sensors.get('s_15', OPTIMAL_SENSORS['s_15']) + random.gauss(0, 0.005)
            self._current_sensors = sensors
            self._last_cycle = cycle
            return sensors

        # === 1. ACCUMULATED WEAR (only increases over time) ===
        # Calculate wear increment based on cycles since simulation started
        max_life = 180
        life_fraction = min(1.0, cycle / max_life)

        # Bathtub curve: slow early, steady middle, accelerating late
        if life_fraction < 0.25:
            wear_increment = 0.002 + life_fraction * 0.003
        elif life_fraction < 0.65:
            wear_increment = 0.004 + (life_fraction - 0.25) * 0.005
        else:
            wear_increment = 0.006 + (life_fraction - 0.65) * 0.015

        # Add small random variation to wear increment
        wear_increment *= random.uniform(0.7, 1.3)
        
        # APPLY USER STRESS FACTOR (Speed up or slow down degradation)
        wear_increment *= self._stress_multiplier
        
        self._accumulated_wear = min(1.0, self._accumulated_wear + wear_increment)
        
        # === 2. MAINTENANCE EVENTS (slows degradation temporarily, doesn't reverse it) ===
        cycles_since_maintenance = cycle - self._last_maintenance_cycle
        
        # Maintenance can slow down degradation but NOT reverse accumulated damage significantly
        if cycles_since_maintenance > 30 and random.random() < 0.04:
            self._last_maintenance_cycle = cycle
            
            # Chance to fix developing fault (this is the main benefit)
            if self._fault_active and random.random() < 0.5:
                self._fault_active = False
                self._fault_sensor = None
                self._fault_severity = 0.0
                print(f"    [MAINTENANCE] Cycle {cycle}: Fault repaired")
            else:
                print(f"    [MAINTENANCE] Cycle {cycle}: Routine service")
        
        # Base wear is simply the accumulated wear (no reversal)
        self._base_wear = self._accumulated_wear
        
        # === 3. OPERATING MODE CHANGES (gradual transitions) ===
        if random.random() < 0.03:
            old_mode = self._operating_mode
            self._operating_mode = random.choices(
                ['light', 'normal', 'heavy'],
                weights=[0.25, 0.55, 0.20]
            )[0]
            mode_factors = {'light': 0.85, 'normal': 1.0, 'heavy': 1.2}
            self._target_mode_factor = mode_factors[self._operating_mode]
            if old_mode != self._operating_mode:
                print(f"    [OPERATING] Cycle {cycle}: Mode {old_mode} -> {self._operating_mode}")
        
        # Gradually transition current_mode_factor toward target (smooth, not instant)
        transition_speed = 0.15  # 15% per cycle toward target
        self._current_mode_factor += (self._target_mode_factor - self._current_mode_factor) * transition_speed
        
        # === 4. FAULT DEVELOPMENT ===
        if not self._fault_active and random.random() < (0.005 + self._base_wear * 0.03):
            self._fault_active = True
            self._fault_sensor = random.choice(['s_3', 's_7', 's_11', 's_15'])
            self._fault_severity = random.uniform(0.03, 0.12)
            print(f"    [FAULT] Cycle {cycle}: Developing issue in {self._fault_sensor}")
        
        if self._fault_active:
            self._fault_severity = min(0.8, self._fault_severity + random.uniform(0.003, 0.015))
        
        # === 5. CALCULATE SENSOR VALUES ===
        # Effective wear is the INCREMENTAL wear since simulation started (not total wear)
        # This ensures RUL continues from where user left off, not jump
        incremental_wear = self._accumulated_wear - self._initial_wear
        effective_wear = min(1.0, incremental_wear * self._current_mode_factor)

        # Add fault effect
        if self._fault_active:
            effective_wear = min(1.0, effective_wear + self._fault_severity * 0.15)

        # Get initial sensor values (what user set)
        init_s3 = self._initial_sensors.get('s_3', OPTIMAL_SENSORS['s_3'])
        init_s4 = self._initial_sensors.get('s_4', OPTIMAL_SENSORS['s_4'])
        init_s7 = self._initial_sensors.get('s_7', OPTIMAL_SENSORS['s_7'])
        init_s11 = self._initial_sensors.get('s_11', OPTIMAL_SENSORS['s_11'])
        init_s15 = self._initial_sensors.get('s_15', OPTIMAL_SENSORS['s_15'])

        # Temperature (s_3) - increases with wear from initial value
        temp_range = CRITICAL_SENSORS['s_3'] - init_s3  # Room to degrade from initial
        self._sensor_noise['s_3'] = 0.8 * self._sensor_noise['s_3'] + 0.2 * random.gauss(0, 4)
        sensors['s_3'] = init_s3 + effective_wear * max(0, temp_range) + self._sensor_noise['s_3']

        # Nozzle temp (s_4)
        temp_range_s4 = CRITICAL_SENSORS['s_4'] - init_s4
        self._sensor_noise['s_4'] = 0.8 * self._sensor_noise['s_4'] + 0.2 * random.gauss(0, 3)
        sensors['s_4'] = init_s4 + effective_wear * max(0, temp_range_s4) + self._sensor_noise['s_4']

        # Pressure (s_7)
        pressure_range = CRITICAL_SENSORS['s_7'] - init_s7
        self._sensor_noise['s_7'] = 0.8 * self._sensor_noise['s_7'] + 0.2 * random.gauss(0, 2.5)
        sensors['s_7'] = init_s7 + effective_wear * max(0, pressure_range) + self._sensor_noise['s_7']

        # Fan speed (s_11)
        speed_range = CRITICAL_SENSORS['s_11'] - init_s11
        self._sensor_noise['s_11'] = 0.8 * self._sensor_noise['s_11'] + 0.2 * random.gauss(0, 15)
        sensors['s_11'] = init_s11 + effective_wear * max(0, speed_range) + self._sensor_noise['s_11']

        # Bypass ratio (s_15) - decreases with wear
        bypass_range = init_s15 - CRITICAL_SENSORS['s_15']
        self._sensor_noise['s_15'] = 0.8 * self._sensor_noise['s_15'] + 0.2 * random.gauss(0, 0.015)
        sensors['s_15'] = init_s15 - effective_wear * max(0, bypass_range) + self._sensor_noise['s_15']
        
        # Apply fault effects (additive, on top of wear)
        if self._fault_active and self._fault_sensor:
            if self._fault_sensor == 's_3':
                sensors['s_3'] += self._fault_severity * 25
            elif self._fault_sensor == 's_7':
                sensors['s_7'] += self._fault_severity * 18
            elif self._fault_sensor == 's_11':
                sensors['s_11'] += self._fault_severity * 250
            elif self._fault_sensor == 's_15':
                sensors['s_15'] -= self._fault_severity * 0.25
        
        # === 6. OCCASIONAL GOOD CYCLES (favorable conditions - small effect) ===
        if random.random() < 0.08:
            sensors['s_3'] -= random.uniform(3, 8)
            sensors['s_7'] -= random.uniform(1, 4)
            sensors['s_11'] -= random.uniform(15, 50)
            sensors['s_15'] += random.uniform(0.01, 0.04)
        
        # Clamp to realistic ranges (use initial sensors as lower bound, not optimal)
        sensors['s_3'] = max(init_s3 - 15, min(CRITICAL_SENSORS['s_3'] + 20, sensors['s_3']))
        sensors['s_4'] = max(init_s4 - 12, min(CRITICAL_SENSORS['s_4'] + 15, sensors['s_4']))
        sensors['s_7'] = max(init_s7 - 10, min(CRITICAL_SENSORS['s_7'] + 10, sensors['s_7']))
        sensors['s_11'] = max(init_s11 - 80, min(CRITICAL_SENSORS['s_11'] + 200, sensors['s_11']))
        sensors['s_15'] = max(CRITICAL_SENSORS['s_15'] - 0.15, min(init_s15 + 0.08, sensors['s_15']))
        
        self._current_sensors = sensors
        self._last_cycle = cycle
        return sensors


# ============================================================================
# ML PREDICTOR CLASS
# ============================================================================

class HybridMLPredictor:
    def __init__(self):
        self.model = None
        self.scaler = None
        self.features = None
        self.data = None
        self.rul_data = None
        self.model_loaded = False
        self._rul_cache = {}
        self._last_rul = {}
        
        # Realistic simulator for custom engine
        self._engine_simulator = RealisticEngineSimulator()
        
        self._load_model()
        self._load_data()
    
    def _load_model(self):
        try:
            import tensorflow as tf
            import joblib
            
            model_path = os.path.join(MODEL_DIR, "hybrid_model.keras")
            scaler_path = os.path.join(MODEL_DIR, "hybrid_scaler.save")
            features_path = os.path.join(MODEL_DIR, "hybrid_features.json")
            
            if os.path.exists(model_path):
                self.model = tf.keras.models.load_model(model_path)
                print(f"✓ Loaded hybrid model")
                
                if os.path.exists(scaler_path):
                    self.scaler = joblib.load(scaler_path)
                    print(f"✓ Loaded scaler")
                
                if os.path.exists(features_path):
                    with open(features_path, 'r') as f:
                        self.features = json.load(f)
                    print(f"✓ Loaded {len(self.features)} features")
                
                self.model_loaded = True
            else:
                print(f"✗ Model not found - using physics simulation")
        except Exception as e:
            print(f"✗ Error loading model: {e}")
    
    def _load_data(self):
        try:
            cols = ['unit_nr', 'time_cycles'] + [f'op_{i}' for i in range(1, 4)] + [f's_{i}' for i in range(1, 22)]
            
            test_path = os.path.join(DATA_DIR, "test_FD004.txt")
            if os.path.exists(test_path):
                self.data = pd.read_csv(test_path, sep=r'\s+', header=None, names=cols)
                print(f"✓ Loaded test data: {len(self.data)} rows, {self.data['unit_nr'].nunique()} engines")
            
            rul_path = os.path.join(DATA_DIR, "RUL_FD004.txt")
            if os.path.exists(rul_path):
                rul_values = pd.read_csv(rul_path, header=None, names=['RUL'])
                
                self.rul_data = {}
                for engine_id in self.data['unit_nr'].unique():
                    engine_data = self.data[self.data['unit_nr'] == engine_id]
                    max_cycle = engine_data['time_cycles'].max()
                    final_rul = int(rul_values.iloc[engine_id - 1]['RUL'])
                    
                    self.rul_data[engine_id] = {
                        'max_cycle': max_cycle,
                        'final_rul': final_rul,
                    }
                
                print(f"✓ Loaded RUL data for {len(self.rul_data)} engines")
            else:
                print(f"✗ RUL file not found at {rul_path}")
                
        except Exception as e:
            print(f"✗ Error loading data: {e}")
            import traceback
            traceback.print_exc()
    
    def reset_custom_engine(self, initial_sensors: Dict = None):
        """Reset the custom engine simulator, optionally starting from given sensor values."""
        self._engine_simulator.reset(initial_sensors)
        
    def update_custom_engine(self, sensors: Dict):
        """Update the running state of the custom engine without resetting."""
        self._engine_simulator.update_state(sensors)
    
    def _calculate_physics_features(self, sensors: Dict) -> Dict:
        physics = {}

        # Use OPTIMAL values as defaults (not degraded values)
        s3 = sensors.get('s_3', OPTIMAL_SENSORS['s_3'])   # 1545.0
        s4 = sensors.get('s_4', OPTIMAL_SENSORS['s_4'])   # 1370.0
        s7 = sensors.get('s_7', OPTIMAL_SENSORS['s_7'])   # 515.0
        s11 = sensors.get('s_11', OPTIMAL_SENSORS['s_11']) # 7820.0
        s15 = sensors.get('s_15', OPTIMAL_SENSORS['s_15']) # 8.58
        
        s3_celsius = (s3 - 459.67) * 5/9
        s4_celsius = (s4 - 459.67) * 5/9
        
        physics['thermal_ratio'] = min(1.5, s3_celsius / ANSYS_PHYSICS['chamber_temp_max'])
        physics['thermal_margin'] = max(0, (ANSYS_PHYSICS['chamber_temp_max'] - s3_celsius) / ANSYS_PHYSICS['chamber_temp_max'])
        
        p_min, p_max = 95, 600
        pressure_norm = max(0, min(1, (s7 - p_min) / (p_max - p_min)))
        stress_range = ANSYS_PHYSICS['stress_max_mpa'] - ANSYS_PHYSICS['stress_min_mpa']
        physics['stress_estimate_mpa'] = ANSYS_PHYSICS['stress_min_mpa'] + pressure_norm * stress_range
        physics['stress_intensity'] = physics['stress_estimate_mpa'] / ANSYS_PHYSICS['stress_max_mpa']
        
        t_norm = max(0, min(1, (s3 - 1400) / (1650 - 1400)))
        physics['deformation_estimate_mm'] = (0.6 * pressure_norm + 0.4 * t_norm) * ANSYS_PHYSICS['deformation_max_mm']
        
        speed_norm = max(0, min(1, (s11 - 7800) / (9500 - 7800)))
        bypass_norm = max(0, min(1, (s15 - 8.2) / (8.6 - 8.2)))
        
        physics['vibration_index'] = speed_norm * (1 - 0.2 * bypass_norm)
        
        if physics['vibration_index'] < 0.05:
            physics['vibration_index'] = 0.05 + (pressure_norm * 0.1)
        
        physics['physics_degradation'] = (
            physics['thermal_ratio'] * 0.35 + 
            physics['stress_intensity'] * 0.35 + 
            physics['vibration_index'] * 0.30
        )
        
        return physics
    
    def get_engine_data(self, engine_id: int) -> Optional[Dict]:
        if engine_id == 0:
            # Reset simulator for new custom engine
            self._engine_simulator.reset()
            return {
                'total_cycles': 300, 
                'max_cycle': 300, 
                'min_cycle': 1, 
                'start_cycle': 1,
                'is_custom': True
            }
        
        if self.data is None:
            return None
        
        engine_data = self.data[self.data['unit_nr'] == engine_id]
        if len(engine_data) == 0:
            return None
        
        min_cycle = int(engine_data['time_cycles'].min())
        max_cycle = int(engine_data['time_cycles'].max())
        
        start_cycle = random.randint(
            min_cycle + int((max_cycle - min_cycle) * 0.3),
            min_cycle + int((max_cycle - min_cycle) * 0.7)
        )
        
        if engine_id in self._rul_cache:
            del self._rul_cache[engine_id]
        if engine_id in self._last_rul:
            del self._last_rul[engine_id]
        
        result = {
            'total_cycles': len(engine_data),
            'max_cycle': max_cycle,
            'min_cycle': min_cycle,
            'start_cycle': start_cycle,
            'is_custom': False
        }
        
        if self.rul_data and engine_id in self.rul_data:
            result['final_rul'] = self.rul_data[engine_id]['final_rul']
        
        return result
    
    def get_sensors_at_cycle(self, engine_id: int, cycle: int) -> Dict:
        if engine_id == 0:
            return OPTIMAL_SENSORS.copy()
        
        if self.data is None:
            return OPTIMAL_SENSORS.copy()
        
        engine_data = self.data[self.data['unit_nr'] == engine_id]
        if len(engine_data) == 0:
            return OPTIMAL_SENSORS.copy()
        
        cycle_data = engine_data[engine_data['time_cycles'] == cycle]
        if len(cycle_data) == 0:
            closest_idx = (engine_data['time_cycles'] - cycle).abs().idxmin()
            cycle_data = engine_data.loc[[closest_idx]]
        
        row = cycle_data.iloc[0]
        sensors = {f's_{i}': float(row[f's_{i}']) for i in range(1, 22)}
        sensors.update({f'op_{i}': float(row[f'op_{i}']) for i in range(1, 4)})
        return sensors
    
    def get_real_engine_rul(self, engine_id: int, cycle: int) -> float:
        if self.rul_data is None or engine_id not in self.rul_data:
            return float(max(0, 125 - cycle * 0.5))
        
        info = self.rul_data[engine_id]
        max_cycle = int(info['max_cycle'])
        final_rul = int(info['final_rul'])
        
        rul = final_rul + (max_cycle - cycle)
        
        return float(max(0, min(RUL_CLIP, rul)))
    
    def simulate_degradation(self, base_sensors: Dict, cycle: int, max_cycle: int = 150) -> Dict:
        """Use realistic engine simulator."""
        return self._engine_simulator.get_sensors_for_cycle(cycle)
    
    def predict_with_model(self, engine_id: int, cycle: int) -> Optional[float]:
        if not self.model_loaded or self.model is None:
            return None
        
        if self.data is None or self.scaler is None or self.features is None:
            return None
        
        try:
            engine_data = self.data[self.data['unit_nr'] == engine_id].copy()
            if len(engine_data) == 0:
                return None
            
            max_available_cycle = int(engine_data['time_cycles'].max())
            
            if cycle > max_available_cycle:
                if self.rul_data and engine_id in self.rul_data:
                    final_rul = self.rul_data[engine_id]['final_rul']
                    rul = max(0, final_rul - (cycle - max_available_cycle))
                    return float(rul)
                else:
                    return 0.0
            
            engine_data = engine_data[engine_data['time_cycles'] <= cycle]
            if len(engine_data) < SEQ_LEN:
                first_row = engine_data.iloc[0:1]
                padding_needed = SEQ_LEN - len(engine_data)
                padding = first_row.loc[first_row.index.repeat(padding_needed)].reset_index(drop=True)
                engine_data = pd.concat([padding, engine_data], ignore_index=True)
            
            engine_data = engine_data.tail(SEQ_LEN)
            engine_data = self._add_physics_features_to_df(engine_data)
            
            available_features = [f for f in self.features if f in engine_data.columns]
            if len(available_features) < len(self.features):
                print(f"Warning: Missing features: {set(self.features) - set(available_features)}")
            
            X = engine_data[available_features].values
            X = X.reshape(1, SEQ_LEN, len(available_features))
            
            X_scaled = np.zeros_like(X)
            for i in range(X.shape[0]):
                X_scaled[i] = self.scaler.transform(X[i])
            
            prediction = self.model.predict(X_scaled, verbose=0)
            
            rul = float(prediction[0][0]) * RUL_CLIP
            rul = max(0, min(RUL_CLIP, rul))
            
            return rul
            
        except Exception as e:
            print(f"ML prediction error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def predict_with_extrapolated_data(self, engine_id: int, max_cycle: int, extra_cycles: int, extrapolated_sensors: Dict) -> Optional[float]:
        if not self.model_loaded or self.model is None:
            return None
        
        if self.data is None or self.scaler is None or self.features is None:
            return None
        
        try:
            engine_data = self.data[self.data['unit_nr'] == engine_id].copy()
            if len(engine_data) == 0:
                return None
            
            engine_data = engine_data[engine_data['time_cycles'] <= max_cycle]
            
            num_extrapolated = min(extra_cycles, SEQ_LEN - 10)
            num_real = SEQ_LEN - num_extrapolated
            
            real_data = engine_data.tail(num_real).copy()
            
            extrapolated_rows = []
            for i in range(num_extrapolated):
                row = {}
                row['unit_nr'] = engine_id
                row['time_cycles'] = max_cycle + i + 1
                
                progress = (i + 1) / num_extrapolated
                for key, value in extrapolated_sensors.items():
                    if key in ['s_3', 's_4', 's_7', 's_11']:
                        last_value = real_data[key].iloc[-1] if key in real_data.columns else value
                        row[key] = last_value + progress * (value - last_value)
                    elif key == 's_15':
                        last_value = real_data[key].iloc[-1] if key in real_data.columns else value
                        row[key] = last_value + progress * (value - last_value)
                    else:
                        row[key] = value
                
                for col in real_data.columns:
                    if col not in row:
                        row[col] = real_data[col].iloc[-1]
                
                extrapolated_rows.append(row)
            
            if extrapolated_rows:
                extrapolated_df = pd.DataFrame(extrapolated_rows)
                combined_data = pd.concat([real_data, extrapolated_df], ignore_index=True)
            else:
                combined_data = real_data
            
            if len(combined_data) < SEQ_LEN:
                first_row = combined_data.iloc[0:1]
                padding_needed = SEQ_LEN - len(combined_data)
                padding = first_row.loc[first_row.index.repeat(padding_needed)].reset_index(drop=True)
                combined_data = pd.concat([padding, combined_data], ignore_index=True)
            
            combined_data = combined_data.tail(SEQ_LEN)
            combined_data = self._add_physics_features_to_df(combined_data)
            
            available_features = [f for f in self.features if f in combined_data.columns]
            
            X = combined_data[available_features].values
            X = X.reshape(1, SEQ_LEN, len(available_features))
            
            X_scaled = np.zeros_like(X)
            for i in range(X.shape[0]):
                X_scaled[i] = self.scaler.transform(X[i])
            
            prediction = self.model.predict(X_scaled, verbose=0)
            
            rul = float(prediction[0][0]) * RUL_CLIP
            rul = max(0, min(RUL_CLIP, rul))
            
            return rul
            
        except Exception as e:
            print(f"Extrapolated prediction error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _add_physics_features_to_df(self, df):
        df = df.copy()
        
        if 's_3' in df.columns:
            s3_celsius = (df['s_3'] - 459.67) * 5/9
            df['thermal_ratio'] = s3_celsius / ANSYS_PHYSICS['chamber_temp_max']
            df['thermal_margin'] = (ANSYS_PHYSICS['chamber_temp_max'] - s3_celsius) / ANSYS_PHYSICS['chamber_temp_max']
            df['thermal_margin'] = df['thermal_margin'].clip(lower=0)
        
        if 's_4' in df.columns:
            s4_celsius = (df['s_4'] - 459.67) * 5/9
            df['nozzle_thermal_ratio'] = s4_celsius / ANSYS_PHYSICS['nozzle_temp_max']
        
        if 's_7' in df.columns:
            p_min, p_max = df['s_7'].min(), df['s_7'].max()
            if p_max > p_min:
                pressure_norm = (df['s_7'] - p_min) / (p_max - p_min + 1e-6)
            else:
                pressure_norm = 0.5
            stress_range = ANSYS_PHYSICS['stress_max_mpa'] - ANSYS_PHYSICS['stress_min_mpa']
            df['stress_estimate_mpa'] = ANSYS_PHYSICS['stress_min_mpa'] + pressure_norm * stress_range
            df['stress_intensity'] = df['stress_estimate_mpa'] / ANSYS_PHYSICS['stress_max_mpa']
        
        if 's_7' in df.columns and 's_3' in df.columns:
            s7_min, s7_max = df['s_7'].min(), df['s_7'].max()
            s3_min, s3_max = df['s_3'].min(), df['s_3'].max()
            p_norm = (df['s_7'] - s7_min) / (s7_max - s7_min + 1e-6) if s7_max > s7_min else 0.5
            t_norm = (df['s_3'] - s3_min) / (s3_max - s3_min + 1e-6) if s3_max > s3_min else 0.5
            df['deformation_estimate_mm'] = (0.6 * p_norm + 0.4 * t_norm) * ANSYS_PHYSICS['deformation_max_mm']
        
        if 's_11' in df.columns and 's_15' in df.columns:
            s11_min, s11_max = df['s_11'].min(), df['s_11'].max()
            s15_min, s15_max = df['s_15'].min(), df['s_15'].max()
            speed_norm = (df['s_11'] - s11_min) / (s11_max - s11_min + 1e-6) if s11_max > s11_min else 0.5
            bypass_norm = (df['s_15'] - s15_min) / (s15_max - s15_min + 1e-6) if s15_max > s15_min else 0.5
            df['vibration_index'] = speed_norm * (1 - 0.3 * bypass_norm)
        
        if 'stress_intensity' in df.columns:
            df['fatigue_damage'] = df['stress_intensity'].cumsum()
            max_fatigue = df['fatigue_damage'].max()
            if max_fatigue > 0:
                df['fatigue_damage'] = df['fatigue_damage'] / max_fatigue
        
        physics_cols = ['thermal_ratio', 'stress_intensity', 'vibration_index', 'fatigue_damage']
        available = [c for c in physics_cols if c in df.columns]
        if available:
            df['physics_degradation'] = df[available].mean(axis=1)
        
        sensor_cols = [f's_{i}' for i in range(1, 22)]
        for col in sensor_cols:
            if col in df.columns:
                df[f'{col}_ma5'] = df[col].rolling(window=5, min_periods=1).mean()
                df[f'{col}_std5'] = df[col].rolling(window=5, min_periods=1).std().fillna(0)
        
        df = df.fillna(0)
        return df
    
    def predict(self, engine_id: int, cycle: int, sensors: Dict = None, is_simulation: bool = False) -> Dict:
        """Make prediction based on sensor inputs."""
        
        # CUSTOM ENGINE (ID = 0)
        if engine_id == 0:
            # Use OPTIMAL_SENSORS if no sensors provided or empty dict
            if sensors is None or not sensors:
                sensors = OPTIMAL_SENSORS.copy()
            
            if is_simulation:
                sensors = self.simulate_degradation(sensors, cycle)
            elif self._engine_simulator._last_cycle > 1:
                # PAUSED STATE (Cycle > 1):
                # Update stress multiplier based on new inputs
                self._engine_simulator.update_state(sensors)
                # Apply existing wear to these new inputs so RUL doesn't reset to "New"
                sensors = self._engine_simulator.apply_wear_to_inputs(sensors)
            
            physics = self._calculate_physics_features(sensors)
            
            thermal = physics.get('thermal_ratio', 0.99)
            stress = physics.get('stress_intensity', 0.9)
            vibration = physics.get('vibration_index', 0.1)
            
            # Tuned health scores: Relaxed baselines to ensure initial state is ~1.0 (RUL 125)
            # Even if input sensors are slightly above optimal (noise/slider defaults), 
            # we want the starting condition to register as Healthy.
            
            # Thermal: Optimal ~0.96. Relaxed baseline to 1.00. 
            # Anything below 1.00 ratio counts as perfect health.
            thermal_health = max(0, min(1, (1.15 - thermal) / (1.15 - 1.00)))
            
            # Stress: Optimal ~0.83. Relaxed baseline to 0.90.
            # Anything below 0.90 stress counts as perfect health.
            stress_health = max(0, min(1, (1.10 - stress) / (1.10 - 0.90)))
            
            # Vibration: Optimal ~0.01. Relaxed baseline to 0.10.
            vibration_health = max(0, min(1, (1.0 - vibration) / (1.0 - 0.10)))
            
            overall_health = (
                thermal_health * 0.40 +
                stress_health * 0.40 +
                vibration_health * 0.20
            )
            
            rul = overall_health * RUL_CLIP
            rul = max(0, min(RUL_CLIP, rul))
            
            print(f"    [Custom] Cycle {cycle}: s3={sensors.get('s_3', 0):.1f}, s7={sensors.get('s_7', 0):.1f}, s11={sensors.get('s_11', 0):.0f}, s15={sensors.get('s_15', 0):.2f}")
            print(f"            T={thermal:.3f}({thermal_health:.2f}) S={stress:.3f}({stress_health:.2f}) V={vibration:.3f}({vibration_health:.2f}) -> RUL={rul:.1f}")
        
        # REAL ENGINES (1-248)
        else:
            engine_info = self.rul_data.get(engine_id, {})
            max_cycle = engine_info.get('max_cycle', 150)
            final_rul = engine_info.get('final_rul', 0)
            
            if cycle <= max_cycle:
                sensors = self.get_sensors_at_cycle(engine_id, cycle)
                physics = self._calculate_physics_features(sensors)
                
                ml_rul = self.predict_with_model(engine_id, cycle)
                
                if ml_rul is not None:
                    rul = ml_rul
                    if cycle == max_cycle:
                        self._last_rul[engine_id] = rul
                    print(f"    [ML] Engine {engine_id}, Cycle {cycle}: RUL={rul:.1f}")
                else:
                    progress = (cycle - 1) / max(1, max_cycle - 1)
                    rul = RUL_CLIP - progress * (RUL_CLIP - final_rul)
                    rul = max(0, min(RUL_CLIP, rul))
                    if cycle == max_cycle:
                        self._last_rul[engine_id] = rul
                    print(f"    [Interp] Engine {engine_id}, Cycle {cycle}: RUL={rul:.1f}")
            else:
                extra_cycles = cycle - max_cycle
                
                if engine_id not in self._last_rul:
                    last_ml_rul = self.predict_with_model(engine_id, max_cycle)
                    self._last_rul[engine_id] = last_ml_rul if last_ml_rul else final_rul
                
                last_rul_at_max = self._last_rul[engine_id]
                last_sensors = self.get_sensors_at_cycle(engine_id, max_cycle)
                
                degradation_progress = extra_cycles / max(1, final_rul)
                degradation_progress = min(1.5, degradation_progress)
                
                sensors = last_sensors.copy()
                sensors['s_3'] = last_sensors.get('s_3', 1580) + degradation_progress * 70
                sensors['s_4'] = last_sensors.get('s_4', 1400) + degradation_progress * 55
                sensors['s_7'] = last_sensors.get('s_7', 550) + degradation_progress * 50
                sensors['s_11'] = last_sensors.get('s_11', 8000) + degradation_progress * 500
                sensors['s_15'] = max(7.0, last_sensors.get('s_15', 8.5) - degradation_progress * 1.0)
                sensors['s_2'] = last_sensors.get('s_2', 642) + degradation_progress * 10
                sensors['s_9'] = last_sensors.get('s_9', 9046) + degradation_progress * 300
                sensors['s_14'] = last_sensors.get('s_14', 8130) + degradation_progress * 400
                
                physics = self._calculate_physics_features(sensors)
                
                ml_rul = self.predict_with_extrapolated_data(engine_id, max_cycle, extra_cycles, sensors)
                
                if ml_rul is not None:
                    rul = min(ml_rul, last_rul_at_max)
                    rul = max(0, rul)
                    print(f"    [Predict] Engine {engine_id}, Cycle {cycle}: RUL={rul:.1f} (capped from {ml_rul:.1f})")
                else:
                    rul = max(0, final_rul - extra_cycles)
                    print(f"    [Fallback] Engine {engine_id}, Cycle {cycle}: RUL={rul:.1f}")
        
        drul = -0.4 - physics['stress_intensity'] * 0.3 - physics['vibration_index'] * 0.2
        status = determine_status(rul)
        
        return {
            'rul': float(round(rul, 1)),
            'drul': float(round(drul, 3)),
            'status': str(status),
            'temperature': float(round(physics['thermal_ratio'] * ANSYS_PHYSICS['chamber_temp_max'], 1)),
            'pressure': float(round(physics['stress_intensity'], 3)),
            'vibration': float(round(physics['vibration_index'], 3)),
            'stress_mpa': float(round(physics['stress_estimate_mpa'], 1)),
            'deformation_mm': float(round(physics['deformation_estimate_mm'], 5)),
            'physics_degradation': float(round(physics['physics_degradation'], 3)),
            'thermal_margin': float(round(physics['thermal_margin'], 3)),
        }
    
    def get_all_engines(self) -> List[int]:
        engines = [0]
        if self.data is not None:
            engines.extend(sorted(self.data['unit_nr'].unique().tolist()))
        else:
            engines.extend(list(range(1, 249)))
        return engines


# ============================================================================
# BLENDER CLIENT
# ============================================================================

class BlenderClient:
    def __init__(self):
        self.host = BLENDER_HOST
        self.port = BLENDER_PORT
        self._socket = None
        self._connected = False
        self._lock = asyncio.Lock()
    
    @property
    def connected(self):
        return self._connected
    
    def _connect_sync(self) -> bool:
        try:
            if self._socket:
                try:
                    self._socket.close()
                except:
                    pass
            
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(10)
            self._socket.connect((self.host, self.port))
            self._connected = True
            print(f"✓ Connected to Blender at {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"✗ Blender connection failed: {e}")
            self._connected = False
            return False
    
    def _recv_exact_sync(self, n: int) -> Optional[bytes]:
        data = b''
        while len(data) < n:
            try:
                chunk = self._socket.recv(n - len(data))
                if not chunk:
                    return None
                data += chunk
            except:
                return None
        return data
    
    def _send_command_sync(self, command: dict) -> Optional[bytes]:
        try:
            if not self._connected:
                if not self._connect_sync():
                    return None
            
            message = json.dumps(command).encode('utf-8')
            header = struct.pack('<I', len(message))
            self._socket.sendall(header + message)
            
            length_data = self._recv_exact_sync(4)
            if not length_data:
                self._connected = False
                return None
            
            response_length = struct.unpack('<I', length_data)[0]
            response_data = self._recv_exact_sync(response_length)
            
            if not response_data:
                self._connected = False
                return None
            
            return response_data
            
        except Exception as e:
            print(f"Blender error: {e}")
            self._connected = False
            return None
    
    async def send_command(self, command: dict) -> Optional[bytes]:
        async with self._lock:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(executor, self._send_command_sync, command)
    
    async def update_and_render(self, temperature: float, pressure: float, 
                               rul: float, vibration: float, frame: int) -> Optional[bytes]:
        command = {
            "action": "update_and_render",
            "data": {
                "Temperature": temperature,
                "Pressure": pressure,
                "RUL": rul,
                "vibration_intensity": vibration,
                "frame": frame
            }
        }
        return await self.send_command(command)
    
    async def send_camera_command(self, camera_action: str) -> Optional[bytes]:
        command = {
            "action": "camera",
            "camera_action": camera_action,
            "render": True
        }
        return await self.send_command(command)


# ============================================================================
# CONNECTION MANAGER
# ============================================================================

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.animation_state: Dict = {}
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.animation_state[id(websocket)] = {
            "playing": False, "speed": 1, "frame": 0, "simulation_mode": False
        }
        print("✓ WebSocket connected")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        ws_id = id(websocket)
        if ws_id in self.animation_state:
            del self.animation_state[ws_id]
        print("WebSocket disconnected")
    
    def get_state(self, websocket: WebSocket) -> Dict:
        return self.animation_state.get(id(websocket), {
            "playing": False, "speed": 1, "frame": 0, "simulation_mode": False
        })
    
    def set_state(self, websocket: WebSocket, key: str, value):
        ws_id = id(websocket)
        if ws_id in self.animation_state:
            self.animation_state[ws_id][key] = value


# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(title="Hybrid Digital Twin Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ml_predictor = HybridMLPredictor()
blender_client = BlenderClient()
manager = ConnectionManager()

@app.get("/")
async def root():
    return {"status": "running", "rul_data_loaded": ml_predictor.rul_data is not None}

@app.get("/engine/{engine_id}")
async def get_engine_info(engine_id: int):
    return ml_predictor.get_engine_data(engine_id)

@app.get("/predict/{engine_id}/{cycle}")
async def predict_endpoint(engine_id: int, cycle: int):
    return ml_predictor.predict(engine_id, cycle)


# ============================================================================
# WEBSOCKET ENDPOINT
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    
    try:
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
            except Exception as e:
                print(f"Receive error: {e}")
                break
            
            action = message.get("action") or message.get("type", "")
            
            if action in ["update", "get_frame", "start_stream"]:
                msg_data = message.get("data", {})
                engine_id = msg_data.get("engine_id", message.get("engine_id", 1))
                cycle = msg_data.get("cycle", message.get("cycle", 1))
                sensors = msg_data.get("sensors", message.get("sensors"))
                is_simulation = message.get("simulation_mode", False)
                
                if engine_id != 0:
                    sensors = None
                
                prediction = ml_predictor.predict(engine_id, cycle, sensors, is_simulation)
                
                print(f"  Engine {engine_id}, Cycle {cycle} -> RUL: {prediction['rul']}, Status: {prediction['status']}")
                
                await websocket.send_json({
                    "type": "prediction",
                    "rul": prediction["rul"],
                    "drul": prediction["drul"],
                    "status": prediction["status"],
                    "temperature": prediction["temperature"],
                    "pressure": prediction["pressure"],
                    "vibration": prediction["vibration"],
                    "stress_mpa": prediction["stress_mpa"],
                    "deformation_mm": prediction["deformation_mm"],
                    "physics_degradation": prediction["physics_degradation"],
                    "thermal_margin": prediction["thermal_margin"],
                })
                
                frame_num = manager.get_state(websocket)["frame"]
                image_data = await blender_client.update_and_render(
                    temperature=prediction["temperature"],
                    pressure=prediction["pressure"],
                    rul=prediction["rul"],
                    vibration=prediction["vibration"],
                    frame=frame_num
                )
                
                if image_data and len(image_data) > 100:
                    if image_data[:2] == b'\xff\xd8' or image_data[:4] == b'\x89PNG':
                        width, height = 640, 480
                        header = struct.pack('<II', width, height)
                        await websocket.send_bytes(header + image_data)
                        print(f"  ✓ Sent frame: {len(image_data)} bytes")
                    else:
                        print(f"  ✗ Invalid image data")
                else:
                    print(f"  ✗ No image from Blender")
            
            elif action == "get_engine_info":
                engine_id = message.get("engine_id", 0)
                engine_info = ml_predictor.get_engine_data(engine_id)
                
                if engine_info:
                    await websocket.send_json({
                        "type": "engine_info",
                        "engine_id": engine_id,
                        **engine_info
                    })
                    print(f"  Engine {engine_id} info: start_cycle={engine_info.get('start_cycle')}, max_cycle={engine_info.get('max_cycle')}")
                else:
                    await websocket.send_json({
                        "type": "engine_info",
                        "engine_id": engine_id,
                        "error": "Engine not found"
                    })
            
            elif action == "start_lifecycle_simulation":
                manager.set_state(websocket, "playing", True)
                manager.set_state(websocket, "simulation_mode", True)
                manager.set_state(websocket, "frame", 0)
                
                msg_data = message.get("data", {})
                engine_id = message.get("engine_id", msg_data.get("engine_id", 0))
                base_sensors = msg_data.get("sensors", OPTIMAL_SENSORS)
                speed = message.get("speed", 0.5)
                start_cycle = message.get("start_cycle", 1)
                
                if engine_id == 0:
                    max_cycles = 200
                    
                    if start_cycle > 1:
                         # RESUME: Update state, don't reset
                         print(f"Resuming Custom Engine from cycle {start_cycle} with updated sensors")
                         if base_sensors:
                             ml_predictor.update_custom_engine(base_sensors)
                    else:
                        # START FRESH
                        start_cycle = 1
                        if base_sensors and base_sensors != OPTIMAL_SENSORS:
                            ml_predictor.reset_custom_engine(base_sensors)
                        else:
                            ml_predictor.reset_custom_engine(None)
                else:
                    engine_info = ml_predictor.get_engine_data(engine_id)
                    max_cycles = engine_info['max_cycle'] if engine_info else 150
                
                print(f"Starting lifecycle simulation: Engine {engine_id}, start_cycle={start_cycle}, max_cycles={max_cycles}")
                
                asyncio.create_task(run_lifecycle_simulation(
                    websocket, engine_id, base_sensors, speed, start_cycle, max_cycles
                ))
            
            elif action == "stop_simulation":
                manager.set_state(websocket, "playing", False)
                manager.set_state(websocket, "simulation_mode", False)
                print("Simulation stopped")
            
            elif action in ["rotate_camera", "set_camera_preset", "camera"]:
                if action == "set_camera_preset":
                    preset = message.get("preset", "front")
                    camera_action = f"preset_{preset}"
                elif action == "rotate_camera":
                    dx = message.get("delta_x", 0)
                    camera_action = "rotate_right" if dx > 0 else "rotate_left"
                else:
                    camera_action = message.get("camera_action", "")
                
                image_data = await blender_client.send_camera_command(camera_action)
                
                if image_data and len(image_data) > 100:
                    if image_data[:2] == b'\xff\xd8' or image_data[:4] == b'\x89PNG':
                        width, height = 640, 480
                        header = struct.pack('<II', width, height)
                        await websocket.send_bytes(header + image_data)
            
            elif action == "zoom_camera":
                pass
            
            elif action == "set_animation":
                playing = message.get("playing", False)
                speed = message.get("speed", 1)
                manager.set_state(websocket, "playing", playing)
                manager.set_state(websocket, "speed", speed)
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        manager.disconnect(websocket)


async def run_lifecycle_simulation(websocket: WebSocket, engine_id: int, 
                                   base_sensors: Dict, speed: float, start_cycle: int, max_cycles: int):
    """Run lifecycle simulation until RUL reaches 0."""
    cycle = start_cycle
    max_simulation_cycles = max_cycles + 150
    
    while manager.get_state(websocket).get("playing", False) and cycle <= max_simulation_cycles:
        manager.set_state(websocket, "frame", cycle)
        
        is_simulation = (engine_id == 0)
        sensors = base_sensors if engine_id == 0 else None
        
        prediction = ml_predictor.predict(engine_id, cycle, sensors, is_simulation)
        
        try:
            await websocket.send_json({
                "type": "prediction",
                "cycle": cycle,
                "rul": prediction["rul"],
                "drul": prediction["drul"],
                "status": prediction["status"],
                "temperature": prediction["temperature"],
                "pressure": prediction["pressure"],
                "vibration": prediction["vibration"],
                "stress_mpa": prediction["stress_mpa"],
                "deformation_mm": prediction["deformation_mm"],
                "physics_degradation": prediction["physics_degradation"],
                "thermal_margin": prediction["thermal_margin"],
            })
            
            image_data = await blender_client.update_and_render(
                temperature=prediction["temperature"],
                pressure=prediction["pressure"],
                rul=prediction["rul"],
                vibration=prediction["vibration"],
                frame=cycle
            )
            
            if image_data and len(image_data) > 100:
                if image_data[:2] == b'\xff\xd8' or image_data[:4] == b'\x89PNG':
                    width, height = 640, 480
                    header = struct.pack('<II', width, height)
                    await websocket.send_bytes(header + image_data)
            
            if prediction["rul"] <= 0:
                await websocket.send_json({
                    "type": "simulation_complete",
                    "final_cycle": cycle,
                    "message": "Engine reached end of life"
                })
                break
            
            cycle += 1
            
        except Exception as e:
            print(f"Simulation error: {e}")
            break
        
        await asyncio.sleep(0.1 / speed)
    
    manager.set_state(websocket, "playing", False)
    manager.set_state(websocket, "simulation_mode", False)
    print(f"Lifecycle simulation ended at cycle {cycle}")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("  HYBRID DIGITAL TWIN - BACKEND SERVER")
    print("="*60)
    print(f"\n  Custom Engine (ID 0) Simulation Features:")
    print(f"    ✓ Starts at maximum RUL (~125)")
    print(f"    ✓ Realistic random sensor fluctuations")
    print(f"    ✓ Maintenance events (RUL can improve)")
    print(f"    ✓ Operating mode changes (light/normal/heavy)")
    print(f"    ✓ Fault development patterns")
    print(f"    ✓ Non-linear degradation (bathtub curve)")
    print(f"\n  Real Engines (1-248): ML model + ground truth")
    print(f"\n  Backend: http://localhost:{BACKEND_PORT}")
    print(f"  Blender: {BLENDER_HOST}:{BLENDER_PORT}")
    print("\n" + "="*60 + "\n")
    
    uvicorn.run(app, host=BACKEND_HOST, port=BACKEND_PORT)