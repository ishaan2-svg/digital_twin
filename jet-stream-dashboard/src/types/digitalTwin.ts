export interface SensorData {
  s_2: number;
  s_3: number;
  s_4: number;
  s_7: number;
  s_11: number;
  s_15: number;
}

export interface FullSensorData extends SensorData {
  [key: string]: number;
}

export interface SensorConfig {
  key: keyof SensorData;
  label: string;
  unit: string;
  min: number;
  max: number;
  optimal: number;
  description: string;
}

export const SENSOR_CONFIGS: SensorConfig[] = [
  { key: 's_2', label: 'LPC Outlet Temp', unit: '°R', min: 525, max: 655, optimal: 642, description: 'Total Temperature at Low Pressure Compressor outlet' },
  { key: 's_3', label: 'HPC Outlet Temp', unit: '°R', min: 1200, max: 1650, optimal: 1580, description: 'Total Temperature at High Pressure Compressor outlet' },
  { key: 's_4', label: 'LPT Outlet Temp', unit: '°R', min: 995, max: 1455, optimal: 1400, description: 'Total Temperature at Low Pressure Turbine outlet' },
  { key: 's_7', label: 'HPC Pressure', unit: 'psia', min: 95, max: 600, optimal: 550, description: 'Total Pressure at High Pressure Compressor outlet' },
  { key: 's_11', label: 'Fan Speed', unit: 'rpm', min: 7000, max: 9500, optimal: 8000, description: 'Physical Fan Speed' },
  { key: 's_15', label: 'Bypass Ratio', unit: '', min: 8.0, max: 10.0, optimal: 8.5, description: 'Engine Bypass Ratio' },
];

export interface PredictionData {
  rul: number;
  drul: number;
  status: 'HEALTHY' | 'DEGRADED' | 'WARNING' | 'CRITICAL';
  temperature: number;
  pressure: number;
  vibration: number;
  stress_mpa?: number;
  deformation_mm?: number;
  physics_degradation?: number;
  thermal_margin?: number;
  cycle?: number;
}

export interface EngineState {
  engineId: number;
  cycle: number;
  maxCycle: number;
  sensors: SensorData;
  prediction: PredictionData | null;
  isCustom: boolean;
}

export type ViewMode = 'single' | 'autoplay' | 'comparison' | 'lifecycle';

export type CameraPreset = 'front' | 'side' | 'top' | 'isometric' | 'default';

export interface StreamState {
  isConnected: boolean;
  isStreaming: boolean;
  fps: number;
  latency: number;
  currentFrame: string | null;
}

export interface WebSocketMessage {
  type?: string;
  action?: string;
  [key: string]: unknown;
}

export interface UpdateMessage extends WebSocketMessage {
  type: 'update';
  data: {
    engine_id: number;
    cycle: number;
    sensors: SensorData;
  };
}

export interface CameraMessage extends WebSocketMessage {
  type: 'rotate_camera' | 'zoom_camera' | 'pan_camera' | 'set_camera_preset';
}

export interface AnimationMessage extends WebSocketMessage {
  type: 'set_animation';
  playing: boolean;
  speed: number;
}

// Optimal sensors for brand new engine
export const OPTIMAL_SENSORS: SensorData = {
  s_2: 642.0,
  s_3: 1580.0,
  s_4: 1400.0,
  s_7: 550.0,
  s_11: 8000.0,
  s_15: 8.5,
};
