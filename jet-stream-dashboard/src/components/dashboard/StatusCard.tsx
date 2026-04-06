import { AlertTriangle, CheckCircle, AlertOctagon, AlertCircle } from 'lucide-react';
import type { PredictionData } from '@/types/digitalTwin';

interface StatusCardProps {
  prediction: PredictionData | null;
}

const STATUS_CONFIG = {
  HEALTHY: {
    icon: CheckCircle,
    label: 'HEALTHY',
    bgClass: 'bg-emerald-500/10 border-emerald-500/30',
    iconColor: 'text-emerald-400',
    barColor: 'bg-emerald-500',
    description: 'Engine operating normally',
  },
  DEGRADED: {
    icon: AlertCircle,
    label: 'DEGRADED',
    bgClass: 'bg-yellow-500/10 border-yellow-500/30',
    iconColor: 'text-yellow-400',
    barColor: 'bg-yellow-500',
    description: 'Minor degradation detected',
  },
  WARNING: {
    icon: AlertTriangle,
    label: 'WARNING',
    bgClass: 'bg-orange-500/10 border-orange-500/30',
    iconColor: 'text-orange-400',
    barColor: 'bg-orange-500',
    description: 'Schedule maintenance soon',
  },
  CRITICAL: {
    icon: AlertOctagon,
    label: 'CRITICAL',
    bgClass: 'bg-red-500/10 border-red-500/30',
    iconColor: 'text-red-400',
    barColor: 'bg-red-500',
    description: 'Immediate attention required',
  },
};

export function StatusCard({ prediction }: StatusCardProps) {
  // Get RUL value
  const rul = prediction?.rul ?? 125;
  
  // Use status from prediction, or compute from RUL as fallback
  let status = prediction?.status;
  
  // Validate status is one of the expected values
  if (!status || !['HEALTHY', 'DEGRADED', 'WARNING', 'CRITICAL'].includes(status)) {
    // Compute from RUL as fallback
    if (rul <= 15) status = 'CRITICAL';
    else if (rul <= 40) status = 'WARNING';
    else if (rul <= 70) status = 'DEGRADED';
    else status = 'HEALTHY';
  }

  const config = STATUS_CONFIG[status as keyof typeof STATUS_CONFIG];
  const Icon = config.icon;

  // Debug log
  console.log('[StatusCard] RUL:', rul, 'Status:', status);

  return (
    <div className={`p-4 rounded-lg border-2 ${config.bgClass} transition-colors duration-300`}>
      <div className="flex items-center gap-3">
        <div className={`p-2.5 rounded-full ${config.bgClass}`}>
          <Icon className={`w-8 h-8 ${config.iconColor}`} />
        </div>
        <div className="flex-1">
          <p className="text-xs text-muted-foreground uppercase tracking-wider">Engine Status</p>
          <p className={`text-2xl font-bold ${config.iconColor}`}>{config.label}</p>
          <p className="text-xs text-muted-foreground mt-0.5">{config.description}</p>
        </div>
      </div>
      
      {/* RUL Progress Bar */}
      <div className="mt-4">
        <div className="flex justify-between text-xs mb-1">
          <span className="text-muted-foreground">Remaining Useful Life</span>
          <span className={`font-mono font-bold ${config.iconColor}`}>{rul.toFixed(1)} cycles</span>
        </div>
        <div className="h-2 bg-secondary rounded-full overflow-hidden">
          <div 
            className={`h-full transition-all duration-500 ${config.barColor}`}
            style={{ width: `${Math.min(100, (rul / 125) * 100)}%` }}
          />
        </div>
        <div className="flex justify-between text-[10px] text-muted-foreground mt-1">
          <span>0</span>
          <span>125 cycles</span>
        </div>
      </div>
    </div>
  );
}