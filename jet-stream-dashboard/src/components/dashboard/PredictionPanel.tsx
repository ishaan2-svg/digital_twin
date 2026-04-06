import { Activity, Download, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { StatusCard } from './StatusCard';
import { MetricsDisplay } from './MetricsDisplay';
import { AlertSystem } from './AlertSystem';
import { SensorDashboard } from './SensorDashboard';
import type { PredictionData, SensorData } from '@/types/digitalTwin';

interface PredictionPanelProps {
  prediction: PredictionData | null;
  sensors: SensorData;
  previousSensors?: SensorData | null;
  engineId: number;
  cycle: number;
  isCustomEngine?: boolean;
}

export function PredictionPanel({
  prediction,
  sensors,
  previousSensors,
  engineId,
  cycle,
  isCustomEngine,
}: PredictionPanelProps) {
  const handleExport = () => {
    const data = {
      timestamp: new Date().toISOString(),
      engineId,
      engineType: isCustomEngine ? 'custom' : 'real',
      cycle,
      sensors,
      prediction,
    };
    
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${isCustomEngine ? 'custom' : `engine-${engineId}`}-cycle-${cycle}-prediction.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="panel h-full flex flex-col">
      <div className="panel-header">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-primary" />
          <span className="font-semibold text-sm">Predictions</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            {isCustomEngine ? (
              <>
                <Sparkles className="w-3 h-3 text-primary" />
                <span>Custom</span>
              </>
            ) : (
              <span>Engine #{engineId}</span>
            )}
            <span>•</span>
            <span>Cycle {cycle}</span>
          </div>
          <Button variant="ghost" size="icon" onClick={handleExport} className="h-7 w-7">
            <Download className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>
      
      <div className="panel-content flex-1 overflow-y-auto space-y-4">
        {/* Status Card */}
        <StatusCard prediction={prediction} />
        
        {/* Alerts */}
        <AlertSystem prediction={prediction} />
        
        {/* Metrics */}
        <MetricsDisplay prediction={prediction} />
        
        {/* Sensor Dashboard */}
        <SensorDashboard sensors={sensors} previousSensors={previousSensors} />
      </div>
    </div>
  );
}
