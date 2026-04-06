import { useState } from 'react';
import { AlertTriangle, AlertOctagon, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { PredictionData } from '@/types/digitalTwin';

interface AlertSystemProps {
  prediction: PredictionData | null;
}

interface AlertItem {
  id: string;
  type: 'critical' | 'warning';
  message: string;
  icon: React.ElementType;
}

export function AlertSystem({ prediction }: AlertSystemProps) {
  const [dismissedAlerts, setDismissedAlerts] = useState<Set<string>>(new Set());

  const rul = prediction?.rul ?? 100;
  
  const alerts: AlertItem[] = [];
  
  if (rul < 20) {
    alerts.push({
      id: 'critical-rul',
      type: 'critical',
      message: '🚨 CRITICAL: Immediate maintenance required! RUL below 20 cycles.',
      icon: AlertOctagon,
    });
  } else if (rul < 50) {
    alerts.push({
      id: 'warning-rul',
      type: 'warning',
      message: '⚠️ WARNING: Schedule maintenance soon. RUL below 50 cycles.',
      icon: AlertTriangle,
    });
  }

  const activeAlerts = alerts.filter((alert) => !dismissedAlerts.has(alert.id));

  const dismissAlert = (id: string) => {
    setDismissedAlerts((prev) => new Set([...prev, id]));
  };

  if (activeAlerts.length === 0) return null;

  return (
    <div className="space-y-2">
      {activeAlerts.map((alert) => (
        <div
          key={alert.id}
          className={alert.type === 'critical' ? 'alert-critical' : 'alert-warning'}
        >
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-start gap-2">
              <alert.icon className="w-5 h-5 mt-0.5 flex-shrink-0" />
              <p className="text-sm font-medium">{alert.message}</p>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 hover:bg-white/10"
              onClick={() => dismissAlert(alert.id)}
            >
              <X className="w-4 h-4" />
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
}
