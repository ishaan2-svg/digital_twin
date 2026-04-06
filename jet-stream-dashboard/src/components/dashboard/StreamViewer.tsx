import { useRef, useEffect, useState, useCallback } from 'react';
import { 
  Maximize2, 
  RotateCw, 
  Play, 
  Pause, 
  Loader2, 
  WifiOff, 
  RefreshCw,
  Video,
  VideoOff
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Slider } from '@/components/ui/slider';
import type { CameraPreset } from '@/types/digitalTwin';

interface StreamViewerProps {
  frameUrl: string | null;
  fps: number;
  latency: number;
  isConnected: boolean;
  isConnecting: boolean;
  isPlaying: boolean;
  animationSpeed: number;
  autoRotate: boolean;
  onConnect: () => void;
  onRotateCamera: (deltaX: number, deltaY: number) => void;
  onZoomCamera: (delta: number) => void;
  onPanCamera: (deltaX: number, deltaY: number) => void;
  onCameraPreset: (preset: CameraPreset) => void;
  onPlayToggle: () => void;
  onAnimationSpeedChange: (speed: number) => void;
  onAutoRotateToggle: () => void;
}

const CAMERA_PRESETS: { label: string; preset: CameraPreset }[] = [
  { label: 'Front', preset: 'front' },
  { label: 'Side', preset: 'side' },
  { label: 'Top', preset: 'top' },
  { label: 'Iso', preset: 'isometric' },
  { label: 'Reset', preset: 'default' },
];

export function StreamViewer({
  frameUrl,
  fps,
  latency,
  isConnected,
  isConnecting,
  isPlaying,
  animationSpeed,
  autoRotate,
  onConnect,
  onRotateCamera,
  onZoomCamera,
  onPanCamera,
  onCameraPreset,
  onPlayToggle,
  onAnimationSpeedChange,
  onAutoRotateToggle,
}: StreamViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [dragButton, setDragButton] = useState<number | null>(null);
  const lastMousePos = useRef({ x: 0, y: 0 });
  const throttleRef = useRef<NodeJS.Timeout | null>(null);

  // Draw frame to canvas
  useEffect(() => {
    if (!frameUrl || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const img = new Image();
    img.onload = () => {
      canvas.width = img.width;
      canvas.height = img.height;
      ctx.drawImage(img, 0, 0);
      URL.revokeObjectURL(frameUrl);
    };
    img.src = frameUrl;
  }, [frameUrl]);

  // Throttled mouse move handler
  const throttledSendCommand = useCallback((callback: () => void) => {
    if (throttleRef.current) return;
    callback();
    throttleRef.current = setTimeout(() => {
      throttleRef.current = null;
    }, 100); // Max 10 commands per second
  }, []);

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
    setDragButton(e.button);
    lastMousePos.current = { x: e.clientX, y: e.clientY };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;

    const deltaX = e.clientX - lastMousePos.current.x;
    const deltaY = e.clientY - lastMousePos.current.y;
    lastMousePos.current = { x: e.clientX, y: e.clientY };

    throttledSendCommand(() => {
      if (dragButton === 0) {
        // Left click - rotate
        onRotateCamera(deltaX, deltaY);
      } else if (dragButton === 2) {
        // Right click - pan
        onPanCamera(deltaX, deltaY);
      }
    });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
    setDragButton(null);
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    throttledSendCommand(() => {
      onZoomCamera(e.deltaY > 0 ? -1 : 1);
    });
  };

  const handleMiddleClick = (e: React.MouseEvent) => {
    if (e.button === 1) {
      e.preventDefault();
      onCameraPreset('default');
    }
  };

  const toggleFullscreen = () => {
    if (!containerRef.current) return;

    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen();
      setIsFullscreen(false);
    }
  };

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code === 'Space') {
        e.preventDefault();
        onPlayToggle();
      } else if (e.code === 'KeyR') {
        onCameraPreset('default');
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onPlayToggle, onCameraPreset]);

  return (
    <div className="panel h-full flex flex-col">
      <div className="panel-header">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            {isConnected ? (
              <Video className="w-4 h-4 text-primary" />
            ) : (
              <VideoOff className="w-4 h-4 text-muted-foreground" />
            )}
            <span className="font-semibold text-sm">3D Stream Viewer</span>
          </div>
          <div className="flex items-center gap-2">
            <div className={`connection-dot ${isConnected ? 'connected' : 'disconnected'}`} />
            <span className="text-xs text-muted-foreground">
              {isConnected ? 'Connected' : isConnecting ? 'Connecting...' : 'Disconnected'}
            </span>
          </div>
        </div>
        
        <div className="flex items-center gap-4">
          {isConnected && (
            <>
              <span className="font-mono text-xs text-muted-foreground">
                {fps} FPS
              </span>
              <span className="font-mono text-xs text-muted-foreground">
                {latency}ms
              </span>
            </>
          )}
          <Button variant="ghost" size="icon" onClick={toggleFullscreen} className="h-7 w-7">
            <Maximize2 className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>

      <div className="flex-1 p-4 flex flex-col gap-4">
        {/* Stream Container */}
        <div 
          ref={containerRef}
          className="stream-container flex-1 relative cursor-grab active:cursor-grabbing"
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onWheel={handleWheel}
          onContextMenu={(e) => e.preventDefault()}
          onAuxClick={handleMiddleClick}
        >
          {isConnected && frameUrl ? (
            <canvas
              ref={canvasRef}
              className="w-full h-full object-contain"
            />
          ) : (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-4">
              {isConnecting ? (
                <>
                  <Loader2 className="w-10 h-10 text-primary animate-spin" />
                  <span className="text-sm text-muted-foreground">Connecting to stream...</span>
                </>
              ) : (
                <>
                  <WifiOff className="w-10 h-10 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">Stream disconnected</span>
                  <Button onClick={onConnect} size="sm" className="gap-2">
                    <RefreshCw className="w-4 h-4" />
                    Reconnect
                  </Button>
                </>
              )}
            </div>
          )}

          {/* FPS Overlay */}
          {isConnected && (
            <div className="absolute top-3 left-3 bg-black/60 backdrop-blur-sm px-2 py-1 rounded text-xs font-mono">
              {fps} FPS • {latency}ms
            </div>
          )}

          {/* Controls hint */}
          {isConnected && (
            <div className="absolute bottom-3 left-3 bg-black/60 backdrop-blur-sm px-2 py-1 rounded text-[10px] text-muted-foreground">
              🖱️ Drag: Rotate • Scroll: Zoom • Right-drag: Pan • Middle: Reset
            </div>
          )}
        </div>

        {/* Camera Presets */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Views:</span>
          <div className="flex gap-1">
            {CAMERA_PRESETS.map(({ label, preset }) => (
              <button
                key={preset}
                onClick={() => onCameraPreset(preset)}
                className="preset-btn"
                disabled={!isConnected}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Animation Controls */}
        <div className="flex items-center justify-between gap-4 p-3 bg-secondary/50 rounded-lg">
          <div className="flex items-center gap-3">
            <Button
              variant={isPlaying ? 'default' : 'secondary'}
              size="sm"
              onClick={onPlayToggle}
              disabled={!isConnected}
              className="gap-2"
            >
              {isPlaying ? (
                <>
                  <Pause className="w-4 h-4" />
                  Pause
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  Play
                </>
              )}
            </Button>

            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Speed:</span>
              <div className="w-24">
                <Slider
                  value={[animationSpeed]}
                  min={0.5}
                  max={2}
                  step={0.5}
                  onValueChange={(v) => onAnimationSpeedChange(v[0])}
                  disabled={!isConnected}
                />
              </div>
              <span className="font-mono text-xs w-8">{animationSpeed}x</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Switch
              id="auto-rotate"
              checked={autoRotate}
              onCheckedChange={onAutoRotateToggle}
              disabled={!isConnected}
            />
            <Label htmlFor="auto-rotate" className="text-xs flex items-center gap-1 cursor-pointer">
              <RotateCw className={`w-3 h-3 ${autoRotate ? 'animate-spin-slow text-primary' : ''}`} />
              Auto-Rotate
            </Label>
          </div>
        </div>
      </div>
    </div>
  );
}
