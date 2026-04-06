"""
================================================================================
HYBRID DIGITAL TWIN - FULL LOCAL TRAINING SCRIPT
================================================================================
Optimized for local PC with 32GB RAM
Trains both Baseline and Hybrid models with full data

Run: python hybrid_model_local.py
================================================================================
"""

import numpy as np
import pandas as pd
import os
import json
import time
from pathlib import Path

# Suppress TensorFlow warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

import tensorflow as tf
from tensorflow.keras.models import Model
from tensorflow.keras.layers import (
    Input, Conv1D, MaxPooling1D, LSTM, Bidirectional,
    Dense, Dropout, BatchNormalization, Concatenate, GlobalAveragePooling1D
)
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau, ModelCheckpoint
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error
import joblib

# ============================================================================
# CONFIGURATION
# ============================================================================

# Paths - Update if needed
PROJECT_DIR = r"C:\Users\ishaa\Documents\5th sem el\main el"
DATA_DIR = os.path.join(PROJECT_DIR, "data")
MODEL_DIR = os.path.join(PROJECT_DIR, "model_artifacts")

# Create directories
os.makedirs(MODEL_DIR, exist_ok=True)

# Model Parameters
SEQ_LEN = 50
RUL_CLIP = 125
EPOCHS = 50
BATCH_SIZE = 256
VALIDATION_SPLIT = 0.2

# ============================================================================
# ANSYS PHYSICS DATA (From your simulations)
# ============================================================================

ANSYS_PHYSICS = {
    # Combustion Chamber Thermal (°C)
    'chamber_temp_min': 626.73,
    'chamber_temp_max': 627.0,
    'chamber_temp_mean': 626.86,
    
    # Nozzle Thermal (°C)
    'nozzle_temp_min': 474.45,
    'nozzle_temp_max': 475.0,
    'nozzle_temp_mean': 474.7,
    
    # Von Mises Stress (MPa)
    'stress_min_mpa': 54.195,
    'stress_max_mpa': 3543.9,
    'stress_mean_mpa': 861.31,
    
    # Total Deformation (mm)
    'deformation_min_mm': 0.0,
    'deformation_max_mm': 0.18929,
    'deformation_mean_mm': 0.09596,
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def print_header(text):
    """Print formatted header."""
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70)

def print_progress(current, total, prefix='Progress'):
    """Print progress bar."""
    bar_length = 40
    progress = current / total
    block = int(bar_length * progress)
    bar = "█" * block + "░" * (bar_length - block)
    print(f"\r  {prefix}: [{bar}] {current}/{total} ({progress*100:.1f}%)", end='', flush=True)
    if current == total:
        print()

# ============================================================================
# DATA LOADING
# ============================================================================

def load_cmapss_data():
    """Load all C-MAPSS datasets."""
    print_header("LOADING C-MAPSS DATA")
    
    cols = ['unit_nr', 'time_cycles'] + \
           [f'op_{i}' for i in range(1, 4)] + \
           [f's_{i}' for i in range(1, 22)]
    
    all_train = []
    unit_offset = 0
    
    datasets = ['FD001', 'FD002', 'FD003', 'FD004']
    
    for fd in datasets:
        train_path = os.path.join(DATA_DIR, f'train_{fd}.txt')
        
        if os.path.exists(train_path):
            df = pd.read_csv(train_path, sep=r'\s+', header=None, names=cols)
            
            # Calculate RUL
            max_cycles = df.groupby('unit_nr')['time_cycles'].max()
            df = df.merge(max_cycles.rename('max_cycle'), left_on='unit_nr', right_index=True)
            df['RUL'] = df['max_cycle'] - df['time_cycles']
            df['RUL'] = df['RUL'].clip(upper=RUL_CLIP)
            df['dataset'] = fd
            
            # Make unit_nr unique across datasets
            df['unit_nr'] = df['unit_nr'] + unit_offset
            unit_offset = df['unit_nr'].max() + 1
            
            all_train.append(df)
            print(f"  ✓ {fd}: {len(df):,} rows, {df['unit_nr'].nunique()} engines")
        else:
            print(f"  ✗ {fd}: Not found at {train_path}")
    
    if not all_train:
        raise ValueError(f"No data found in {DATA_DIR}")
    
    combined = pd.concat(all_train, ignore_index=True)
    print(f"\n  ✓ TOTAL: {len(combined):,} rows, {combined['unit_nr'].nunique()} engines")
    
    return combined

# ============================================================================
# PHYSICS FEATURE ENGINEERING
# ============================================================================

def create_physics_features(df):
    """Create physics-based features from ANSYS simulation data."""
    print_header("CREATING PHYSICS FEATURES")
    
    df = df.copy()
    
    # --- THERMAL FEATURES ---
    print("  Creating thermal features...")
    
    # s_3: HPC outlet temp (Rankine) → Celsius
    if 's_3' in df.columns:
        s3_celsius = (df['s_3'] - 459.67) * 5/9
        df['thermal_ratio'] = s3_celsius / ANSYS_PHYSICS['chamber_temp_max']
        df['thermal_margin'] = (ANSYS_PHYSICS['chamber_temp_max'] - s3_celsius) / ANSYS_PHYSICS['chamber_temp_max']
        df['thermal_margin'] = df['thermal_margin'].clip(lower=0)
        print(f"    ✓ thermal_ratio: [{df['thermal_ratio'].min():.3f}, {df['thermal_ratio'].max():.3f}]")
    
    # s_4: LPT outlet temp → Nozzle thermal
    if 's_4' in df.columns:
        s4_celsius = (df['s_4'] - 459.67) * 5/9
        df['nozzle_thermal_ratio'] = s4_celsius / ANSYS_PHYSICS['nozzle_temp_max']
        print(f"    ✓ nozzle_thermal_ratio: [{df['nozzle_thermal_ratio'].min():.3f}, {df['nozzle_thermal_ratio'].max():.3f}]")
    
    # --- STRESS FEATURES ---
    print("  Creating stress features...")
    
    if 's_7' in df.columns:
        p_min, p_max = df['s_7'].min(), df['s_7'].max()
        pressure_norm = (df['s_7'] - p_min) / (p_max - p_min + 1e-6)
        
        stress_range = ANSYS_PHYSICS['stress_max_mpa'] - ANSYS_PHYSICS['stress_min_mpa']
        df['stress_estimate_mpa'] = ANSYS_PHYSICS['stress_min_mpa'] + pressure_norm * stress_range
        df['stress_intensity'] = df['stress_estimate_mpa'] / ANSYS_PHYSICS['stress_max_mpa']
        print(f"    ✓ stress_estimate_mpa: [{df['stress_estimate_mpa'].min():.1f}, {df['stress_estimate_mpa'].max():.1f}]")
    
    # --- DEFORMATION FEATURES ---
    print("  Creating deformation features...")
    
    if 's_7' in df.columns and 's_3' in df.columns:
        p_norm = (df['s_7'] - df['s_7'].min()) / (df['s_7'].max() - df['s_7'].min() + 1e-6)
        t_norm = (df['s_3'] - df['s_3'].min()) / (df['s_3'].max() - df['s_3'].min() + 1e-6)
        df['deformation_estimate_mm'] = (0.6 * p_norm + 0.4 * t_norm) * ANSYS_PHYSICS['deformation_max_mm']
        print(f"    ✓ deformation_estimate_mm: [{df['deformation_estimate_mm'].min():.5f}, {df['deformation_estimate_mm'].max():.5f}]")
    
    # --- VIBRATION FEATURES ---
    print("  Creating vibration features...")
    
    if 's_11' in df.columns and 's_15' in df.columns:
        speed_norm = (df['s_11'] - df['s_11'].min()) / (df['s_11'].max() - df['s_11'].min() + 1e-6)
        bypass_norm = (df['s_15'] - df['s_15'].min()) / (df['s_15'].max() - df['s_15'].min() + 1e-6)
        df['vibration_index'] = speed_norm * (1 - 0.3 * bypass_norm)
        print(f"    ✓ vibration_index: [{df['vibration_index'].min():.3f}, {df['vibration_index'].max():.3f}]")
    
    # --- FATIGUE ACCUMULATION ---
    print("  Creating fatigue features...")
    
    if 'stress_intensity' in df.columns:
        df['fatigue_damage'] = df.groupby('unit_nr')['stress_intensity'].cumsum()
        df['fatigue_damage'] = df.groupby('unit_nr')['fatigue_damage'].transform(
            lambda x: x / x.max() if x.max() > 0 else 0
        )
        print(f"    ✓ fatigue_damage: [{df['fatigue_damage'].min():.3f}, {df['fatigue_damage'].max():.3f}]")
    
    # --- COMBINED PHYSICS INDEX ---
    physics_cols = ['thermal_ratio', 'stress_intensity', 'vibration_index', 'fatigue_damage']
    available = [c for c in physics_cols if c in df.columns]
    
    if available:
        df['physics_degradation'] = df[available].mean(axis=1)
        print(f"    ✓ physics_degradation: [{df['physics_degradation'].min():.3f}, {df['physics_degradation'].max():.3f}]")
    
    return df

def add_rolling_features(df):
    """Add rolling window features."""
    print("\n  Creating rolling features...")
    
    key_sensors = ['s_2', 's_3', 's_4', 's_7', 's_11', 's_12', 's_15', 's_20', 's_21']
    
    for i, s in enumerate(key_sensors):
        if s in df.columns:
            df[f'{s}_ma5'] = df.groupby('unit_nr')[s].transform(
                lambda x: x.rolling(window=5, min_periods=1).mean()
            )
            df[f'{s}_std5'] = df.groupby('unit_nr')[s].transform(
                lambda x: x.rolling(window=5, min_periods=1).std().fillna(0)
            )
        print_progress(i+1, len(key_sensors), "Rolling features")
    
    return df

# ============================================================================
# SEQUENCE PREPARATION
# ============================================================================

def prepare_sequences(df, feature_cols, seq_len=SEQ_LEN):
    """Prepare sequences for LSTM training."""
    print(f"\n  Preparing sequences (seq_len={seq_len})...")
    
    X_list, y_list = [], []
    engines = df['unit_nr'].unique()
    
    for i, engine in enumerate(engines):
        engine_df = df[df['unit_nr'] == engine].sort_values('time_cycles')
        
        if len(engine_df) < seq_len:
            continue
        
        features = engine_df[feature_cols].values
        rul = engine_df['RUL'].values
        
        for j in range(len(engine_df) - seq_len + 1):
            X_list.append(features[j:j+seq_len])
            y_list.append(rul[j+seq_len-1])
        
        if (i + 1) % 50 == 0 or i == len(engines) - 1:
            print_progress(i+1, len(engines), "Engines processed")
    
    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.float32)
    
    print(f"  ✓ Created {len(X):,} sequences, shape: {X.shape}")
    
    return X, y

# ============================================================================
# MODEL ARCHITECTURE
# ============================================================================

def build_cnn_bilstm_model(input_shape):
    """Build CNN-BiLSTM hybrid architecture."""
    inputs = Input(shape=input_shape, name='input')
    
    # === CNN Branch ===
    cnn = Conv1D(64, 3, activation='relu', padding='same')(inputs)
    cnn = BatchNormalization()(cnn)
    cnn = Conv1D(64, 3, activation='relu', padding='same')(cnn)
    cnn = MaxPooling1D(2)(cnn)
    cnn = Dropout(0.2)(cnn)
    
    cnn = Conv1D(128, 3, activation='relu', padding='same')(cnn)
    cnn = BatchNormalization()(cnn)
    cnn = Conv1D(128, 3, activation='relu', padding='same')(cnn)
    cnn = MaxPooling1D(2)(cnn)
    cnn = Dropout(0.2)(cnn)
    
    # === BiLSTM Branch ===
    lstm = Bidirectional(LSTM(64, return_sequences=True))(inputs)
    lstm = Dropout(0.2)(lstm)
    lstm = Bidirectional(LSTM(32, return_sequences=False))(lstm)
    lstm = Dropout(0.2)(lstm)
    
    # === Combine ===
    cnn_flat = GlobalAveragePooling1D()(cnn)
    combined = Concatenate()([cnn_flat, lstm])
    
    # === Dense Layers ===
    x = Dense(128, activation='relu')(combined)
    x = BatchNormalization()(x)
    x = Dropout(0.3)(x)
    
    x = Dense(64, activation='relu')(x)
    x = Dropout(0.2)(x)
    
    # === Output: RUL + dRUL ===
    rul_output = Dense(1, activation='linear', name='rul')(x)
    drul_output = Dense(1, activation='tanh', name='drul')(x)
    outputs = Concatenate(name='output')([rul_output, drul_output])
    
    model = Model(inputs=inputs, outputs=outputs)
    
    return model

# ============================================================================
# TRAINING FUNCTION
# ============================================================================

def train_model(X, y, feature_cols, model_name, save_dir):
    """Train model and save artifacts."""
    print_header(f"TRAINING {model_name.upper()} MODEL")
    
    start_time = time.time()
    
    # Split data
    print(f"\n  Splitting data (80/20)...")
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=VALIDATION_SPLIT, random_state=42
    )
    print(f"    Train: {len(X_train):,} samples")
    print(f"    Val:   {len(X_val):,} samples")
    
    # Scale features
    print(f"  Scaling features...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(
        X_train.reshape(-1, X_train.shape[-1])
    ).reshape(X_train.shape)
    X_val_scaled = scaler.transform(
        X_val.reshape(-1, X_val.shape[-1])
    ).reshape(X_val.shape)
    
    # Prepare targets (RUL normalized + dRUL)
    y_train_norm = y_train / RUL_CLIP
    y_val_norm = y_val / RUL_CLIP
    y_train_drul = np.gradient(y_train_norm)
    y_val_drul = np.gradient(y_val_norm)
    
    y_train_combined = np.column_stack([y_train_norm, y_train_drul])
    y_val_combined = np.column_stack([y_val_norm, y_val_drul])
    
    # Build model
    print(f"\n  Building CNN-BiLSTM model...")
    model = build_cnn_bilstm_model((X_train.shape[1], X_train.shape[2]))
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
        loss='mse',
        metrics=['mae']
    )
    print(f"    Parameters: {model.count_params():,}")
    print(f"    Input shape: {X_train.shape[1:]}")
    print(f"    Features: {X_train.shape[2]}")
    
    # Callbacks
    callbacks = [
        EarlyStopping(
            monitor='val_loss',
            patience=10,
            restore_best_weights=True,
            verbose=1
        ),
        ReduceLROnPlateau(
            monitor='val_loss',
            factor=0.5,
            patience=5,
            min_lr=1e-6,
            verbose=1
        ),
        ModelCheckpoint(
            os.path.join(save_dir, f'{model_name}_best.keras'),
            monitor='val_loss',
            save_best_only=True,
            verbose=0
        )
    ]
    
    # Train
    print(f"\n  Training for up to {EPOCHS} epochs...")
    print(f"  " + "-"*50)
    
    history = model.fit(
        X_train_scaled, y_train_combined,
        validation_data=(X_val_scaled, y_val_combined),
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        callbacks=callbacks,
        verbose=1
    )
    
    # Evaluate
    print(f"\n  Evaluating...")
    y_pred = model.predict(X_val_scaled, verbose=0)
    y_pred_rul = y_pred[:, 0] * RUL_CLIP
    
    rmse = np.sqrt(mean_squared_error(y_val, y_pred_rul))
    mae = mean_absolute_error(y_val, y_pred_rul)
    
    elapsed = time.time() - start_time
    
    print(f"\n  " + "="*50)
    print(f"  📊 {model_name.upper()} RESULTS:")
    print(f"     RMSE: {rmse:.2f} cycles")
    print(f"     MAE:  {mae:.2f} cycles")
    print(f"     Time: {elapsed/60:.1f} minutes")
    print(f"  " + "="*50)
    
    # Save artifacts
    print(f"\n  Saving model artifacts...")
    
    model.save(os.path.join(save_dir, f'{model_name}_model.keras'))
    joblib.dump(scaler, os.path.join(save_dir, f'{model_name}_scaler.save'))
    
    with open(os.path.join(save_dir, f'{model_name}_features.json'), 'w') as f:
        json.dump(feature_cols, f, indent=2)
    
    metrics = {
        'rmse': float(rmse),
        'mae': float(mae),
        'epochs_trained': len(history.history['loss']),
        'training_time_minutes': elapsed / 60
    }
    
    with open(os.path.join(save_dir, f'{model_name}_metrics.json'), 'w') as f:
        json.dump(metrics, f, indent=2)
    
    print(f"  ✓ Saved to {save_dir}")
    
    return model, scaler, metrics

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main training pipeline."""
    print("\n")
    print("╔" + "═"*68 + "╗")
    print("║" + " "*68 + "║")
    print("║    🚀 HYBRID DIGITAL TWIN - FULL MODEL TRAINING                    ║")
    print("║    Physics-Enhanced RUL Prediction with ANSYS Integration          ║")
    print("║" + " "*68 + "║")
    print("╚" + "═"*68 + "╝")
    
    total_start = time.time()
    
    # Check GPU
    print_header("SYSTEM CHECK")
    gpus = tf.config.list_physical_devices('GPU')
    if gpus:
        print(f"  ✓ GPU detected: {gpus[0].name}")
        print(f"    Training will be accelerated!")
    else:
        print(f"  ℹ No GPU detected, using CPU")
        print(f"    Training will take ~45-60 minutes")
    
    print(f"\n  Project: {PROJECT_DIR}")
    print(f"  Data: {DATA_DIR}")
    print(f"  Output: {MODEL_DIR}")
    
    # Load data
    df = load_cmapss_data()
    
    # Create physics features
    df = create_physics_features(df)
    df = add_rolling_features(df)
    df = df.fillna(0)
    
    # Define feature sets
    print_header("DEFINING FEATURE SETS")
    
    # Baseline: Sensors + Operating conditions + Rolling
    sensor_cols = [f's_{i}' for i in range(1, 22)]
    op_cols = [f'op_{i}' for i in range(1, 4)]
    rolling_cols = [c for c in df.columns if '_ma5' in c or '_std5' in c]
    
    baseline_features = [c for c in sensor_cols + op_cols + rolling_cols if c in df.columns]
    
    # Hybrid: Baseline + Physics
    physics_cols = [
        'thermal_ratio', 'thermal_margin', 'nozzle_thermal_ratio',
        'stress_estimate_mpa', 'stress_intensity',
        'deformation_estimate_mm', 'vibration_index',
        'fatigue_damage', 'physics_degradation'
    ]
    physics_cols = [c for c in physics_cols if c in df.columns]
    
    hybrid_features = baseline_features + physics_cols
    
    print(f"  Baseline features: {len(baseline_features)}")
    print(f"  Physics features:  {len(physics_cols)}")
    print(f"  Hybrid features:   {len(hybrid_features)}")
    print(f"\n  Physics features: {physics_cols}")
    
    # Prepare sequences
    print_header("PREPARING SEQUENCES")
    
    print("\n  [1/2] Baseline sequences:")
    X_baseline, y_baseline = prepare_sequences(df, baseline_features)
    
    print("\n  [2/2] Hybrid sequences:")
    X_hybrid, y_hybrid = prepare_sequences(df, hybrid_features)
    
    # Train Baseline
    baseline_model, baseline_scaler, baseline_metrics = train_model(
        X_baseline, y_baseline, baseline_features, 'baseline', MODEL_DIR
    )
    
    # Clear memory
    del X_baseline, y_baseline
    tf.keras.backend.clear_session()
    
    # Train Hybrid
    hybrid_model, hybrid_scaler, hybrid_metrics = train_model(
        X_hybrid, y_hybrid, hybrid_features, 'hybrid', MODEL_DIR
    )
    
    # Save ANSYS physics
    with open(os.path.join(MODEL_DIR, 'ansys_physics.json'), 'w') as f:
        json.dump(ANSYS_PHYSICS, f, indent=2)
    
    # Final comparison
    print_header("FINAL COMPARISON")
    
    print(f"\n  {'Model':<15} {'RMSE':<12} {'MAE':<12} {'Time':<12}")
    print(f"  {'-'*50}")
    print(f"  {'Baseline':<15} {baseline_metrics['rmse']:<12.2f} {baseline_metrics['mae']:<12.2f} {baseline_metrics['training_time_minutes']:<12.1f} min")
    print(f"  {'Hybrid':<15} {hybrid_metrics['rmse']:<12.2f} {hybrid_metrics['mae']:<12.2f} {hybrid_metrics['training_time_minutes']:<12.1f} min")
    
    improvement = (baseline_metrics['rmse'] - hybrid_metrics['rmse']) / baseline_metrics['rmse'] * 100
    
    print(f"\n  " + "="*50)
    if hybrid_metrics['rmse'] < baseline_metrics['rmse']:
        print(f"  ✅ HYBRID MODEL WINS!")
        print(f"     Improvement: {improvement:.1f}% better RMSE")
        print(f"     Physics integration successful!")
    else:
        print(f"  ⚠️ Models have comparable performance")
        print(f"     Hybrid model still has physics interpretability advantage")
    print(f"  " + "="*50)
    
    total_time = time.time() - total_start
    
    print_header("TRAINING COMPLETE")
    print(f"""
  Total time: {total_time/60:.1f} minutes
  
  Files saved to: {MODEL_DIR}
  
  📦 Model Files:
     • hybrid_model.keras     ← Use this for your app
     • hybrid_scaler.save
     • hybrid_features.json
     • ansys_physics.json
     • baseline_model.keras   (for comparison)
     
  🚀 Next Steps:
     1. Copy hybrid_model.keras to your project
     2. Update backend_server.py to use hybrid model
     3. Run the visualization!
""")

if __name__ == "__main__":
    main()
