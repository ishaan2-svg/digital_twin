import { useState, useEffect, useCallback, useRef } from 'react';
import type { PredictionData, WebSocketMessage } from '@/types/digitalTwin';

interface EngineInfo {
  engine_id: number;
  total_cycles: number;
  max_cycle: number;
  min_cycle: number;
  start_cycle: number;
  is_custom: boolean;
  final_rul?: number;
}

interface UseWebSocketOptions {
  url: string;
  onPrediction?: (data: PredictionData) => void;
  onFrame?: (frameData: string, width: number, height: number) => void;
  onSimulationComplete?: (data: { final_cycle: number; message: string }) => void;
  onCycleUpdate?: (cycle: number) => void;
  onEngineInfo?: (info: EngineInfo) => void;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

interface UseWebSocketReturn {
  isConnected: boolean;
  isConnecting: boolean;
  fps: number;
  latency: number;
  send: (message: WebSocketMessage) => void;
  connect: () => void;
  disconnect: () => void;
}

export function useWebSocket({
  url,
  onPrediction,
  onFrame,
  onSimulationComplete,
  onCycleUpdate,
  onEngineInfo,
  reconnectInterval = 3000,
  maxReconnectAttempts = 5,
}: UseWebSocketOptions): UseWebSocketReturn {
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [fps, setFps] = useState(0);
  const [latency, setLatency] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const frameCountRef = useRef(0);
  const lastFpsUpdateRef = useRef(Date.now());
  const lastMessageTimeRef = useRef(Date.now());

  const clearReconnectTimeout = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  const disconnect = useCallback(() => {
    clearReconnectTimeout();
    reconnectAttemptsRef.current = maxReconnectAttempts;
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
    setIsConnecting(false);
  }, [clearReconnectTimeout, maxReconnectAttempts]);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    clearReconnectTimeout();
    setIsConnecting(true);
    reconnectAttemptsRef.current = 0;

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;
      ws.binaryType = 'arraybuffer';

      ws.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        setIsConnecting(false);
        reconnectAttemptsRef.current = 0;
      };

      ws.onclose = (event) => {
        console.log('WebSocket closed:', event.code);
        setIsConnected(false);
        setIsConnecting(false);
        wsRef.current = null;

        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttemptsRef.current++;
            console.log(`Reconnecting ${reconnectAttemptsRef.current}/${maxReconnectAttempts}`);
            connect();
          }, reconnectInterval);
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setIsConnecting(false);
      };

      ws.onmessage = (event) => {
        const now = Date.now();
        setLatency(now - lastMessageTimeRef.current);
        lastMessageTimeRef.current = now;

        // Binary = image frame
        if (event.data instanceof ArrayBuffer) {
          const view = new DataView(event.data);
          const width = view.getUint32(0, true);
          const height = view.getUint32(4, true);
          const imageData = new Uint8Array(event.data, 8);
          const blob = new Blob([imageData], { type: 'image/jpeg' });
          const imageUrl = URL.createObjectURL(blob);

          onFrame?.(imageUrl, width, height);

          frameCountRef.current++;
          if (now - lastFpsUpdateRef.current >= 1000) {
            setFps(frameCountRef.current);
            frameCountRef.current = 0;
            lastFpsUpdateRef.current = now;
          }
          return;
        }

        // JSON messages
        try {
          const message = JSON.parse(event.data);

          if (message.type === 'prediction') {
            // Update cycle if provided (lifecycle simulation)
            if (message.cycle !== undefined) {
              onCycleUpdate?.(message.cycle);
            }

            // Determine status from RUL if not provided or invalid
            let status = message.status;
            const rul = message.rul ?? 0;
            
            if (!status || !['HEALTHY', 'DEGRADED', 'WARNING', 'CRITICAL'].includes(status)) {
              if (rul > 70) status = 'HEALTHY';
              else if (rul > 40) status = 'DEGRADED';
              else if (rul > 15) status = 'WARNING';
              else status = 'CRITICAL';
            }

            onPrediction?.({
              rul: message.rul ?? 0,
              drul: message.drul ?? 0,
              status: status,
              temperature: message.temperature ?? 0,
              pressure: message.pressure ?? 0,
              vibration: message.vibration ?? 0,
              stress_mpa: message.stress_mpa,
              deformation_mm: message.deformation_mm,
              physics_degradation: message.physics_degradation,
              thermal_margin: message.thermal_margin,
            });
          } else if (message.type === 'engine_info') {
            // Handle engine info response with start_cycle
            onEngineInfo?.({
              engine_id: message.engine_id,
              total_cycles: message.total_cycles,
              max_cycle: message.max_cycle,
              min_cycle: message.min_cycle,
              start_cycle: message.start_cycle,
              is_custom: message.is_custom,
              final_rul: message.final_rul,
            });
          } else if (message.type === 'simulation_complete') {
            onSimulationComplete?.({
              final_cycle: message.final_cycle,
              message: message.message,
            });
          }
        } catch (e) {
          console.error('Parse error:', e);
        }
      };
    } catch (error) {
      console.error('WebSocket creation failed:', error);
      setIsConnecting(false);
    }
  }, [url, onPrediction, onFrame, onSimulationComplete, onCycleUpdate, onEngineInfo, clearReconnectTimeout, reconnectInterval, maxReconnectAttempts]);

  const send = useCallback((message: WebSocketMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      const backendMessage: Record<string, unknown> = { ...message };
      if (message.type && !backendMessage.action) {
        backendMessage.action = message.type;
      }
      console.log('Sending:', backendMessage.action || backendMessage.type);
      wsRef.current.send(JSON.stringify(backendMessage));
    } else {
      console.warn('WebSocket not connected');
    }
  }, []);

  useEffect(() => {
    return () => {
      clearReconnectTimeout();
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [clearReconnectTimeout]);

  return {
    isConnected,
    isConnecting,
    fps,
    latency,
    send,
    connect,
    disconnect,
  };
}