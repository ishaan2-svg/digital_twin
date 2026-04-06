import { Settings, Play, Pause, RotateCcw, Sparkles, FlaskConical } from 'lucide-react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { SensorSlider } from './SensorSlider';
import type { EngineState, SensorData, ViewMode } from '@/types/digitalTwin';
import { SENSOR_CONFIGS, OPTIMAL_SENSORS } from '@/types/digitalTwin';

interface ControlPanelProps {
  engineState: EngineState;
  onEngineIdChange: (id: number) => void;
  onCycleChange: (cycle: number) => void;
  onSensorChange: (key: keyof SensorData, value: number) => void;
  viewMode: ViewMode;
  onViewModeChange: (mode: ViewMode) => void;
  isAutoPlaying: boolean;
  autoPlaySpeed: number;
  onAutoPlayToggle: () => void;
  onAutoPlaySpeedChange: (speed: number) => void;
  onReset: () => void;
  onStartLifecycle: () => void;
  onStopSimulation: () => void;
  isSimulating: boolean;
}

export function ControlPanel({
  engineState,
  onEngineIdChange,
  onCycleChange,
  onSensorChange,
  viewMode,
  onViewModeChange,
  isAutoPlaying,
  autoPlaySpeed,
  onAutoPlayToggle,
  onAutoPlaySpeedChange,
  onReset,
  onStartLifecycle,
  onStopSimulation,
  isSimulating,
}: ControlPanelProps) {
  // Engine IDs: 0 = Custom, 1-248 = Real engines
  const engineOptions = [
    { id: 0, label: '✨ Custom Engine (New)' },
    ...Array.from({ length: 248 }, (_, i) => ({ 
      id: i + 1, 
      label: `Engine #${i + 1}` 
    }))
  ];

  const isCustomEngine = engineState.engineId === 0;

  const handleResetToOptimal = () => {
    // Reset sensors to optimal values
    Object.entries(OPTIMAL_SENSORS).forEach(([key, value]) => {
      if (key in engineState.sensors) {
        onSensorChange(key as keyof SensorData, value);
      }
    });
  };
  
  return (
    <div className="panel h-full flex flex-col">
      <div className="panel-header">
        <div className="flex items-center gap-2">
          <Settings className="w-4 h-4 text-primary" />
          <span className="font-semibold text-sm">Controls</span>
        </div>
        <Button variant="ghost" size="icon" onClick={onReset} className="h-7 w-7">
          <RotateCcw className="w-3.5 h-3.5" />
        </Button>
      </div>
      
      <div className="panel-content flex-1 overflow-y-auto space-y-6">
        {/* Mode Selection */}
        <div className="space-y-2">
          <Label className="text-xs text-muted-foreground uppercase tracking-wider">Mode</Label>
          <Tabs value={viewMode} onValueChange={(v) => onViewModeChange(v as ViewMode)}>
            <TabsList className="grid w-full grid-cols-3 h-8">
              <TabsTrigger value="single" className="text-xs">Manual</TabsTrigger>
              <TabsTrigger value="autoplay" className="text-xs">Auto</TabsTrigger>
              <TabsTrigger value="lifecycle" className="text-xs">Lifecycle</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>

        {/* Engine Selection */}
        <div className="space-y-3">
          <Label className="text-xs text-muted-foreground uppercase tracking-wider">Engine Selection</Label>
          
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm">Engine</span>
              <span className="font-mono text-sm text-primary">
                {isCustomEngine ? '✨ Custom' : `#${engineState.engineId}`}
              </span>
            </div>
            <Select 
              value={String(engineState.engineId)} 
              onValueChange={(v) => onEngineIdChange(Number(v))}
              disabled={isSimulating}
            >
              <SelectTrigger className="h-9">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="max-h-[250px]">
                {engineOptions.map((opt) => (
                  <SelectItem key={opt.id} value={String(opt.id)}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Custom Engine Badge */}
          {isCustomEngine && (
            <div className="p-2 bg-primary/10 border border-primary/20 rounded-lg">
              <div className="flex items-center gap-2 text-xs text-primary">
                <Sparkles className="w-3.5 h-3.5" />
                <span>Custom engine - adjust sensors below</span>
              </div>
            </div>
          )}

          {/* Cycle Control */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm">Cycle</span>
              <span className="font-mono text-sm text-primary">{engineState.cycle}</span>
            </div>
            <Slider
              value={[engineState.cycle]}
              min={1}
              max={engineState.maxCycle}
              step={1}
              onValueChange={(v) => onCycleChange(v[0])}
              disabled={isSimulating || (viewMode === 'autoplay' && isAutoPlaying)}
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>1</span>
              <span>{engineState.maxCycle}</span>
            </div>
          </div>
        </div>

        {/* Lifecycle Simulation Controls */}
        {viewMode === 'lifecycle' && (
          <div className="space-y-3 p-3 bg-gradient-to-br from-blue-500/10 to-purple-500/10 border border-blue-500/20 rounded-lg">
            <div className="flex items-center gap-2">
              <FlaskConical className="w-4 h-4 text-blue-400" />
              <Label className="text-xs text-blue-400 uppercase tracking-wider">Lifecycle Simulation</Label>
            </div>
            
            <p className="text-xs text-muted-foreground">
              {isCustomEngine 
                ? "Simulate how your custom engine degrades from cycle 1 to failure."
                : "Watch this engine's recorded degradation from start to end."
              }
            </p>
            
            <div className="flex gap-2">
              {!isSimulating ? (
                <Button 
                  onClick={onStartLifecycle}
                  className="flex-1 gap-2 bg-blue-600 hover:bg-blue-700"
                  size="sm"
                >
                  <Play className="w-4 h-4" />
                  Start Simulation
                </Button>
              ) : (
                <Button 
                  onClick={onStopSimulation}
                  variant="destructive"
                  className="flex-1 gap-2"
                  size="sm"
                >
                  <Pause className="w-4 h-4" />
                  Stop
                </Button>
              )}
            </div>
          </div>
        )}

        {/* Auto-Play Controls (non-lifecycle) */}
        {viewMode === 'autoplay' && (
          <div className="space-y-3 p-3 bg-secondary/50 rounded-lg">
            <Label className="text-xs text-muted-foreground uppercase tracking-wider">Auto-Play</Label>
            
            <div className="flex items-center gap-2">
              <Button 
                variant={isAutoPlaying ? 'default' : 'secondary'} 
                size="sm" 
                onClick={onAutoPlayToggle}
                className="flex-1"
              >
                {isAutoPlaying ? (
                  <>
                    <Pause className="w-4 h-4 mr-2" />
                    Pause
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4 mr-2" />
                    Play
                  </>
                )}
              </Button>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm">Speed</span>
                <span className="font-mono text-sm text-primary">{autoPlaySpeed}x</span>
              </div>
              <div className="flex gap-1">
                {[0.5, 1, 2, 5].map((speed) => (
                  <Button
                    key={speed}
                    variant={autoPlaySpeed === speed ? 'default' : 'secondary'}
                    size="sm"
                    className="flex-1 h-7 text-xs"
                    onClick={() => onAutoPlaySpeedChange(speed)}
                  >
                    {speed}x
                  </Button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Sensor Controls */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Label className="text-xs text-muted-foreground uppercase tracking-wider">Sensor Inputs</Label>
            {isCustomEngine && (
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={handleResetToOptimal}
                className="h-6 text-xs"
                disabled={isSimulating}
              >
                Reset to Optimal
              </Button>
            )}
          </div>
          
          <div className="space-y-4">
            {SENSOR_CONFIGS.map((config) => (
              <SensorSlider
                key={config.key}
                config={config}
                value={engineState.sensors[config.key]}
                onChange={(value) => onSensorChange(config.key, value)}
                disabled={isSimulating || (viewMode === 'autoplay' && isAutoPlaying) || (!isCustomEngine && viewMode !== 'single')}
                showOptimal={isCustomEngine}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}