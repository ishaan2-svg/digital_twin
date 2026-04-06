import { Wifi, WifiOff, Loader2 } from 'lucide-react';

interface ConnectionStatusProps {
  isConnected: boolean;
  isConnecting: boolean;
  fps?: number;
  latency?: number;
}

export function ConnectionStatus({ isConnected, isConnecting, fps, latency }: ConnectionStatusProps) {
  return (
    <div className="flex items-center gap-4 px-4 py-2 bg-card/50 border-b border-border">
      <div className="flex items-center gap-2">
        {isConnecting ? (
          <Loader2 className="w-4 h-4 text-primary animate-spin" />
        ) : isConnected ? (
          <Wifi className="w-4 h-4 text-emerald-400" />
        ) : (
          <WifiOff className="w-4 h-4 text-red-400" />
        )}
        <span className="text-sm">
          {isConnecting ? 'Connecting...' : isConnected ? 'Connected' : 'Disconnected'}
        </span>
      </div>
      
      {isConnected && (
        <>
          <div className="h-4 w-px bg-border" />
          <span className="font-mono text-xs text-muted-foreground">
            {fps} FPS
          </span>
          <span className="font-mono text-xs text-muted-foreground">
            {latency}ms latency
          </span>
        </>
      )}
    </div>
  );
}
