import { useState } from 'react';
import { ChevronDown, ChevronUp, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import type { SensorData } from '@/types/digitalTwin';
import { SENSOR_CONFIGS } from '@/types/digitalTwin';

interface SensorDashboardProps {
  sensors: SensorData;
  previousSensors?: SensorData | null;
}

function getTrendIcon(current: number, previous: number | undefined) {
  if (previous === undefined) return <Minus className="w-3 h-3 text-muted-foreground" />;
  
  const diff = current - previous;
  if (Math.abs(diff) < 0.1) return <Minus className="w-3 h-3 text-muted-foreground" />;
  if (diff > 0) return <TrendingUp className="w-3 h-3 text-red-400" />;
  return <TrendingDown className="w-3 h-3 text-emerald-400" />;
}

function getValueColor(value: number, min: number, max: number): string {
  const percentage = (value - min) / (max - min);
  if (percentage > 0.9) return 'text-red-400';
  if (percentage > 0.7) return 'text-orange-400';
  if (percentage > 0.5) return 'text-yellow-400';
  return 'text-emerald-400';
}

export function SensorDashboard({ sensors, previousSensors }: SensorDashboardProps) {
  const [isOpen, setIsOpen] = useState(true);

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger asChild>
        <Button
          variant="ghost"
          className="w-full flex items-center justify-between p-0 h-auto hover:bg-transparent"
        >
          <h3 className="text-xs text-muted-foreground uppercase tracking-wider">Sensor Readings</h3>
          {isOpen ? (
            <ChevronUp className="w-4 h-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="w-4 h-4 text-muted-foreground" />
          )}
        </Button>
      </CollapsibleTrigger>
      
      <CollapsibleContent className="pt-3">
        <div className="grid grid-cols-2 gap-2">
          {SENSOR_CONFIGS.map((config) => {
            const value = sensors[config.key];
            const prevValue = previousSensors?.[config.key];
            const valueColor = getValueColor(value, config.min, config.max);
            
            return (
              <div
                key={config.key}
                className="p-2 bg-secondary/50 rounded-lg"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] text-muted-foreground uppercase">
                    {config.key}
                  </span>
                  {getTrendIcon(value, prevValue)}
                </div>
                <div className="flex items-baseline gap-1">
                  <span className={`font-mono text-sm font-semibold ${valueColor}`}>
                    {value.toFixed(1)}
                  </span>
                  <span className="text-[10px] text-muted-foreground">{config.unit}</span>
                </div>
              </div>
            );
          })}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
