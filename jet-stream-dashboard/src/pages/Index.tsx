import { useState, useCallback, useEffect, useRef } from 'react';
import { Header } from '@/components/dashboard/Header';
import { ControlPanel } from '@/components/dashboard/ControlPanel';
import { StreamViewer } from '@/components/dashboard/StreamViewer';
import { PredictionPanel } from '@/components/dashboard/PredictionPanel';
import { useWebSocket } from '@/hooks/useWebSocket';
import { RULGraph } from '@/components/dashboard/RULgraph';
import { useToast } from '@/hooks/use-toast';
import type { 
  EngineState, 
  SensorData, 
  PredictionData, 
  ViewMode, 
  CameraPreset 
} from '@/types/digitalTwin';
import { OPTIMAL_SENSORS } from '@/types/digitalTwin';

const DEFAULT_SENSORS: SensorData = { ...OPTIMAL_SENSORS };

const DEFAULT_ENGINE_STATE: EngineState = {
  engineId: 0,
  cycle: 1,
  maxCycle: 150,
  sensors: DEFAULT_SENSORS,
  prediction: null,
  isCustom: true,
};

const WS_URL = 'ws://localhost:8000/ws';

export default function Index() {
  const { toast } = useToast();
  
  // Engine state
  const [engineState, setEngineState] = useState<EngineState>(DEFAULT_ENGINE_STATE);
  const [previousSensors, setPreviousSensors] = useState<SensorData | null>(null);
  const [prediction, setPrediction] = useState<PredictionData | null>(null);
  const [graphData, setGraphData] = useState<{ cycle: number; drul: number }[]>([]);

  // View mode
  const [viewMode, setViewMode] = useState<ViewMode>('lifecycle');
  const [isAutoPlaying, setIsAutoPlaying] = useState(false);
  const [autoPlaySpeed, setAutoPlaySpeed] = useState(0.5);
  const [isSimulating, setIsSimulating] = useState(false);

  // Stream state
  const [frameUrl, setFrameUrl] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [animationSpeed, setAnimationSpeed] = useState(1);
  const [autoRotate, setAutoRotate] = useState(false);

  const autoRotateRef = useRef<ReturnType<typeof setInterval> | null>(null);

// WebSocket
  // WebSocket
  const { 
    isConnected, 
    isConnecting, 
    fps, 
    latency, 
    send, 
    connect, 
    disconnect 
  } = useWebSocket({
    url: WS_URL,
    onPrediction: (data) => {
      setPrediction(data);

      setGraphData(prev => {
        const raw = data as any;
        
        // 1. Try to get cycle from backend
        let currentCycle = raw.cycle;

        // 2. CRITICAL FIX: If backend cycle is missing or undefined,
        //    calculate it based on the LAST point in the graph + 1.
        //    This completely bypasses the stale 'engineState' variable.
        if (currentCycle === undefined || currentCycle === null) {
            currentCycle = prev.length > 0 ? prev[prev.length - 1].cycle + 1 : 1;
        }

        // Prevent adding the same cycle twice (deduplication)
        if (prev.length > 0 && prev[prev.length - 1].cycle === currentCycle) {
            return prev;
        }

        const newHistory = [...prev, { cycle: currentCycle, drul: raw.drul }];
        
        // Keep graph buffer size managed (150 points)
        if (newHistory.length > 150) {
          return newHistory.slice(newHistory.length - 150);
        }
        return newHistory;
      });
    },
    // ... keep the rest of your handlers (onFrame, onSimulationComplete, etc.) the same ...
    onFrame: (frameData) => {
      if (frameUrl) URL.revokeObjectURL(frameUrl);
      setFrameUrl(frameData);
    },
    onSimulationComplete: (data) => {
      setIsSimulating(false);
      toast({ title: "Simulation Complete", description: `End of life at cycle ${data.final_cycle}` });
    },
    onCycleUpdate: (cycle) => setEngineState(prev => ({ ...prev, cycle })),
    onEngineInfo: (info) => {
      setEngineState(prev => ({
        ...prev,
        cycle: info.start_cycle,
        maxCycle: 150,
        isCustom: info.is_custom,
      }));
    },
  }); // Only trigger on connection change

  // =========================================================================
  // FIXED: Request frame when engine/cycle/sensors change (NON-SIMULATION)
  // This works for BOTH 'single' (manual) AND 'lifecycle' modes
  // =========================================================================
  useEffect(() => {
    // Don't send if not connected
    if (!isConnected) return;
    
    // Don't send during active simulation (it sends its own frames)
    if (isSimulating) return;
    
    // Don't send during autoplay (it has its own interval)
    if (isAutoPlaying && viewMode === 'autoplay') return;

    console.log('[Index] Engine/cycle changed, requesting frame:', {
      engineId: engineState.engineId,
      cycle: engineState.cycle,
      viewMode,
      isSimulating,
    });

    send({
      type: 'get_frame',
      engine_id: engineState.engineId,
      cycle: engineState.cycle,
      sensors: engineState.sensors,
    });
  }, [engineState.engineId, engineState.cycle, JSON.stringify(engineState.sensors), isConnected, isSimulating, isAutoPlaying, viewMode, send]);

  // =========================================================================
  // FIXED: Also request frame when switching view modes (if not simulating)
  // =========================================================================
  useEffect(() => {
    if (isConnected && !isSimulating && !isAutoPlaying) {
      console.log('[Index] View mode changed to:', viewMode);
      send({
        type: 'get_frame',
        engine_id: engineState.engineId,
        cycle: engineState.cycle,
        sensors: engineState.sensors,
      });
    }
  }, [viewMode]);

  // Auto-play logic (for autoplay mode, not lifecycle)
  useEffect(() => {
    if (!isAutoPlaying || viewMode !== 'autoplay' || !isConnected) return;

    const interval = setInterval(() => {
      setEngineState((prev) => {
        const nextCycle = prev.cycle + 1;
        if (nextCycle >= prev.maxCycle) {
          setIsAutoPlaying(false);
          return prev;
        }
        
        send({
          type: 'get_frame',
          engine_id: prev.engineId,
          cycle: nextCycle,
          sensors: prev.sensors,
        });
        
        return { ...prev, cycle: nextCycle };
      });
    }, 1000 / autoPlaySpeed);

    return () => clearInterval(interval);
  }, [isAutoPlaying, autoPlaySpeed, viewMode, isConnected, send]);

  // Auto-rotate
  useEffect(() => {
    if (autoRotate && isConnected) {
      autoRotateRef.current = setInterval(() => {
        send({
          type: 'rotate_camera',
          delta_x: 2,
          delta_y: 0,
        });
      }, 100);
    }

    return () => {
      if (autoRotateRef.current) {
        clearInterval(autoRotateRef.current);
        autoRotateRef.current = null;
      }
    };
  }, [autoRotate, isConnected, send]);

  // Handlers
  const handleEngineIdChange = useCallback((id: number) => {
    const isCustom = id === 0;
    console.log('[Index] Engine changed to:', id, isCustom ? '(custom)' : '(real)');
    
    // Update engine ID immediately
    setEngineState((prev) => ({ 
      ...prev, 
      engineId: id,
      isCustom,
      sensors: isCustom ? { ...OPTIMAL_SENSORS } : prev.sensors,
    }));
    
    // Clear graph history on engine change
    setGraphData([]);
    
    // Request engine info from backend to get random start_cycle
    if (isConnected) {
      send({
        type: 'get_engine_info',
        action: 'get_engine_info',
        engine_id: id,
      });
    }
  }, [isConnected, send]);

  const handleCycleChange = useCallback((cycle: number) => {
    console.log('[Index] Cycle changed to:', cycle);
    setEngineState((prev) => ({ ...prev, cycle }));
  }, []);

  const handleSensorChange = useCallback((key: keyof SensorData, value: number) => {
    setEngineState((prev) => {
      setPreviousSensors(prev.sensors);
      return {
        ...prev,
        sensors: { ...prev.sensors, [key]: value },
      };
    });
  }, []);

  const handleViewModeChange = useCallback((mode: ViewMode) => {
    console.log('[Index] View mode changing to:', mode);
    // Stop any running simulation/autoplay when switching modes
    if (isSimulating) {
      setIsSimulating(false);
      send({ type: 'stop_simulation', action: 'stop_simulation' });
    }
    if (isAutoPlaying) {
      setIsAutoPlaying(false);
    }
    setViewMode(mode);
  }, [isSimulating, isAutoPlaying, send]);

  const handleReset = useCallback(() => {
    setEngineState(DEFAULT_ENGINE_STATE);
    setPreviousSensors(null);
    setPrediction(null);
    setGraphData([]);
    setIsSimulating(false);
    setIsAutoPlaying(false);
  }, []);

  const handleStartLifecycle = useCallback(() => {
    if (!isConnected) return;
    
    console.log('[Index] Starting lifecycle simulation from cycle:', engineState.cycle);
    setIsSimulating(true);
    
    send({
      type: 'start_lifecycle_simulation',
      action: 'start_lifecycle_simulation',
      engine_id: engineState.engineId,
      speed: autoPlaySpeed,
      start_cycle: engineState.cycle,  // Start from current cycle
      max_cycles: engineState.maxCycle,
      data: {
        sensors: engineState.sensors,
      },
    });
  }, [isConnected, engineState, autoPlaySpeed, send]);

  const handleStopSimulation = useCallback(() => {
    console.log('[Index] Stopping simulation...');
    setIsSimulating(false);
    send({
      type: 'stop_simulation',
      action: 'stop_simulation',
    });
  }, [send]);

  const handleRotateCamera = useCallback((deltaX: number, deltaY: number) => {
    send({
      type: 'rotate_camera',
      delta_x: deltaX,
      delta_y: deltaY,
    });
  }, [send]);

  const handleZoomCamera = useCallback((delta: number) => {
    send({
      type: 'zoom_camera',
      delta,
    });
  }, [send]);

  const handlePanCamera = useCallback((deltaX: number, deltaY: number) => {
    send({
      type: 'pan_camera',
      delta_x: deltaX,
      delta_y: deltaY,
    });
  }, [send]);

  const handleCameraPreset = useCallback((preset: CameraPreset) => {
    send({
      type: 'set_camera_preset',
      preset,
    });
  }, [send]);

  const handlePlayToggle = useCallback(() => {
    const newPlaying = !isPlaying;
    setIsPlaying(newPlaying);
    send({
      type: 'set_animation',
      playing: newPlaying,
      speed: animationSpeed,
    });
  }, [isPlaying, animationSpeed, send]);

  const handleAnimationSpeedChange = useCallback((speed: number) => {
    setAnimationSpeed(speed);
    send({
      type: 'set_animation',
      playing: isPlaying,
      speed,
    });
  }, [isPlaying, send]);

  const handleAutoRotateToggle = useCallback(() => {
    setAutoRotate((prev) => !prev);
  }, []);

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Header
        isConnected={isConnected}
        isConnecting={isConnecting}
        fps={fps}
        latency={latency}
        isCustomEngine={engineState.isCustom}
        isSimulating={isSimulating}
      />

      <main className="flex-1 flex gap-4 p-4 overflow-hidden">
        {/* Left Panel - Controls */}
        <aside className="w-[300px] flex-shrink-0">
          <ControlPanel
            engineState={engineState}
            onEngineIdChange={handleEngineIdChange}
            onCycleChange={handleCycleChange}
            onSensorChange={handleSensorChange}
            viewMode={viewMode}
            onViewModeChange={handleViewModeChange}
            isAutoPlaying={isAutoPlaying}
            autoPlaySpeed={autoPlaySpeed}
            onAutoPlayToggle={() => setIsAutoPlaying((prev) => !prev)}
            onAutoPlaySpeedChange={setAutoPlaySpeed}
            onReset={handleReset}
            onStartLifecycle={handleStartLifecycle}
            onStopSimulation={handleStopSimulation}
            isSimulating={isSimulating}
          />
        </aside>

        {/* Center Panel - Stream Viewer */}
        {/* Center Panel - Stream Viewer & Graph */}
        <section className="flex-1 min-w-0 flex flex-col gap-4 overflow-y-auto">
          
          {/* Stream Viewer */}
          <div className="flex-shrink-0"> 
            <StreamViewer
              frameUrl={frameUrl}
              fps={fps}
              latency={latency}
              isConnected={isConnected}
              isConnecting={isConnecting}
              isPlaying={isPlaying}
              animationSpeed={animationSpeed}
              autoRotate={autoRotate}
              onConnect={connect}
              onRotateCamera={handleRotateCamera}
              onZoomCamera={handleZoomCamera}
              onPanCamera={handlePanCamera}
              onCameraPreset={handleCameraPreset}
              onPlayToggle={handlePlayToggle}
              onAnimationSpeedChange={handleAnimationSpeedChange}
              onAutoRotateToggle={handleAutoRotateToggle}
            />
          </div>

          {/* RUL Graph - Takes available space or fixed height */}
          <div className="flex-shrink-0">
            <RULGraph data={graphData} />
          </div>
          
        </section>

        {/* Right Panel - Predictions */}
        <aside className="w-[320px] flex-shrink-0">
          <PredictionPanel
            prediction={prediction}
            sensors={engineState.sensors}
            previousSensors={previousSensors}
            engineId={engineState.engineId}
            cycle={engineState.cycle}
            isCustomEngine={engineState.isCustom}
          />
        </aside>
      </main>
    </div>
  );
}