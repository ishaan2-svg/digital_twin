import { Slider } from '@/components/ui/slider';
import type { SensorConfig } from '@/types/digitalTwin';

interface SensorSliderProps {
  config: SensorConfig;
  value: number;
  onChange: (value: number) => void;
  disabled?: boolean;
  showOptimal?: boolean;
}

export function SensorSlider({ config, value, onChange, disabled, showOptimal }: SensorSliderProps) {
  const { key, label, unit, min, max, optimal, description } = config;
  
  // Calculate how far from optimal (for custom engine indicator)
  const deviationFromOptimal = optimal ? Math.abs(value - optimal) / (max - min) : 0;
  const isNearOptimal = deviationFromOptimal < 0.1;
  
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm">{label}</span>
          {showOptimal && isNearOptimal && (
            <span className="text-[10px] bg-green-500/20 text-green-400 px-1.5 py-0.5 rounded">
              Optimal
            </span>
          )}
        </div>
        <span className="font-mono text-sm text-primary">
          {value.toFixed(1)}{unit}
        </span>
      </div>
      
      <div className="relative">
        <Slider
          value={[value]}
          min={min}
          max={max}
          step={(max - min) / 100}
          onValueChange={(v) => onChange(v[0])}
          disabled={disabled}
          className={disabled ? 'opacity-50' : ''}
        />
        
        {/* Optimal marker for custom engine */}
        {showOptimal && optimal && (
          <div 
            className="absolute top-1/2 -translate-y-1/2 w-0.5 h-4 bg-green-500/50 pointer-events-none"
            style={{ 
              left: `${((optimal - min) / (max - min)) * 100}%`,
            }}
            title={`Optimal: ${optimal}${unit}`}
          />
        )}
      </div>
      
      <div className="flex justify-between text-[10px] text-muted-foreground">
        <span>{min}{unit}</span>
        {showOptimal && optimal && (
          <span className="text-green-400/70">⬆ {optimal}{unit}</span>
        )}
        <span>{max}{unit}</span>
      </div>
    </div>
  );
}
