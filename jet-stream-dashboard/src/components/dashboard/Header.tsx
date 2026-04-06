import { Cpu, Wifi, WifiOff, Sparkles, FlaskConical } from 'lucide-react';

interface HeaderProps {
  isConnected: boolean;
  isConnecting: boolean;
  fps: number;
  latency: number;
  isCustomEngine?: boolean;
  isSimulating?: boolean;
}

export function Header({ 
  isConnected, 
  isConnecting, 
  fps, 
  latency,
  isCustomEngine,
  isSimulating,
}: HeaderProps) {
  return (
    <header className="h-14 border-b border-border bg-card/50 backdrop-blur-sm flex items-center justify-between px-6">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <Cpu className="w-6 h-6 text-primary" />
          <h1 className="text-lg font-bold">
            Digital Twin
            <span className="text-primary ml-1">Dashboard</span>
          </h1>
        </div>
        
        {/* Custom Engine Badge */}
        {isCustomEngine && (
          <div className="flex items-center gap-1.5 px-2 py-1 bg-primary/10 rounded-full">
            <Sparkles className="w-3.5 h-3.5 text-primary" />
            <span className="text-xs font-medium text-primary">Custom Engine</span>
          </div>
        )}
        
        {/* Simulation Badge */}
        {isSimulating && (
          <div className="flex items-center gap-1.5 px-2 py-1 bg-blue-500/10 rounded-full animate-pulse">
            <FlaskConical className="w-3.5 h-3.5 text-blue-400" />
            <span className="text-xs font-medium text-blue-400">Simulating...</span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-6">
        {/* Stats */}
        {isConnected && (
          <div className="flex items-center gap-4 text-sm">
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground">FPS:</span>
              <span className="font-mono text-primary">{fps}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground">Latency:</span>
              <span className="font-mono text-primary">{latency}ms</span>
            </div>
          </div>
        )}

        {/* Connection Status */}
        <div className="flex items-center gap-2">
          {isConnected ? (
            <>
              <Wifi className="w-4 h-4 text-emerald-400" />
              <span className="text-sm text-emerald-400">Connected</span>
            </>
          ) : isConnecting ? (
            <>
              <Wifi className="w-4 h-4 text-yellow-400 animate-pulse" />
              <span className="text-sm text-yellow-400">Connecting...</span>
            </>
          ) : (
            <>
              <WifiOff className="w-4 h-4 text-red-400" />
              <span className="text-sm text-red-400">Disconnected</span>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
