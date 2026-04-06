import { Gauge, Thermometer, Waves, TrendingDown, Zap, Move, ShieldAlert, Activity } from 'lucide-react';
import type { PredictionData } from '@/types/digitalTwin';

interface MetricsDisplayProps {
  prediction: PredictionData | null;
}

interface MetricItemProps {
  icon: React.ElementType;
  label: string;
  value: number | string;
  unit?: string;
  highlight?: boolean;
  warning?: boolean;
  info?: string;
}

function MetricItem({ icon: Icon, label, value, unit, highlight, warning, info }: MetricItemProps) {
  return (
    <div className="flex items-center gap-3 p-3 bg-secondary/50 rounded-lg">
      <div className={`p-2 rounded-lg ${warning ? 'bg-red-500/20' : 'bg-primary/20'}`}>
        <Icon className={`w-4 h-4 ${warning ? 'text-red-400' : 'text-primary'}`} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-muted-foreground truncate">{label}</p>
        <div className="flex items-baseline gap-1">
          <span className={`text-sm font-semibold ${highlight ? 'text-primary' : ''} ${warning ? 'text-red-400' : ''}`}>
            {typeof value === 'number' ? value.toFixed(2) : value}
          </span>
          {unit && <span className="text-xs text-muted-foreground">{unit}</span>}
        </div>
        {info && <p className="text-[10px] text-muted-foreground mt-0.5">{info}</p>}
      </div>
    </div>
  );
}

export function MetricsDisplay({ prediction }: MetricsDisplayProps) {
  const rul = prediction?.rul ?? 0;
  const drul = prediction?.drul ?? 0;
  const temp = prediction?.temperature ?? 0;
  const pressure = prediction?.pressure ?? 0;
  const vibration = prediction?.vibration ?? 0;
  
  // Physics features
  const stressMpa = prediction?.stress_mpa ?? 0;
  const deformationMm = prediction?.deformation_mm ?? 0;
  const physicsDegradation = prediction?.physics_degradation ?? 0;
  const thermalMargin = prediction?.thermal_margin ?? 0;

  return (
    <div className="space-y-4">
      {/* RUL Section */}
      <div className="space-y-2">
        <h3 className="text-xs text-muted-foreground uppercase tracking-wider flex items-center gap-2">
          <Activity className="w-3 h-3" />
          RUL Prediction
        </h3>
        <div className="space-y-2">
          <MetricItem
            icon={Gauge}
            label="Remaining Useful Life"
            value={rul}
            unit="cycles"
            highlight
            warning={rul < 20}
          />
          <MetricItem
            icon={TrendingDown}
            label="Degradation Rate"
            value={drul}
            unit="/cycle"
          />
        </div>
      </div>

      {/* Sensor Metrics */}
      <div className="space-y-2">
        <h3 className="text-xs text-muted-foreground uppercase tracking-wider">Sensor Indices</h3>
        <div className="space-y-2">
          <MetricItem
            icon={Thermometer}
            label="Temperature"
            value={temp}
            unit="°C"
            warning={temp > 550}
          />
          <MetricItem
            icon={Gauge}
            label="Pressure Index"
            value={pressure}
          />
          <MetricItem
            icon={Waves}
            label="Vibration Index"
            value={vibration}
            warning={vibration > 0.8}
          />
        </div>
      </div>

      {/* ANSYS Physics */}
      <div className="space-y-2">
        <h3 className="text-xs text-muted-foreground uppercase tracking-wider flex items-center gap-2">
          ANSYS Physics
          <span className="text-[9px] bg-blue-500/20 text-blue-400 px-1.5 py-0.5 rounded">Hybrid</span>
        </h3>
        <div className="space-y-2">
          <MetricItem
            icon={Zap}
            label="Von Mises Stress"
            value={stressMpa}
            unit="MPa"
            warning={stressMpa > 2500}
            info="Max: 3,544 MPa"
          />
          <MetricItem
            icon={Move}
            label="Deformation"
            value={(deformationMm * 1000).toFixed(1)}
            unit="μm"
            info="Max: 189 μm"
          />
          <div className="grid grid-cols-2 gap-2">
            <MetricItem
              icon={Thermometer}
              label="Thermal Margin"
              value={(thermalMargin * 100).toFixed(1)}
              unit="%"
              warning={thermalMargin < 0.1}
            />
            <MetricItem
              icon={ShieldAlert}
              label="Degradation"
              value={(physicsDegradation * 100).toFixed(1)}
              unit="%"
              warning={physicsDegradation > 0.7}
            />
          </div>
        </div>
      </div>
    </div>
  );
}