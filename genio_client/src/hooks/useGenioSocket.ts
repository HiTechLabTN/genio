import { useCallback, useEffect, useRef, useState } from "react";
import type {
  ChatEvent,
  GenioEvent,
  ServerNode,
  SocketStatus,
  TelemetrySnapshot,
  UseGenioSocket,
} from "../lib/types";
import { GenioSocket, isChatEvent, streamTelemetry } from "../lib/ws";

export function useGenioSocket(): UseGenioSocket {
  const [status, setStatus] = useState<SocketStatus>({ kind: "idle" });
  const [telemetry, setTelemetry] = useState<TelemetrySnapshot | null>(null);
  const [chat, setChat] = useState<ChatEvent[]>([]);
  const [screen, setScreen] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);

  const socketRef = useRef<GenioSocket | null>(null);
  const sseRef = useRef<AbortController | null>(null);
  const activeRef = useRef<ServerNode | null>(null);

  const send = useCallback((payload: Record<string, unknown>) => {
    const ws = socketRef.current;
    if (!ws) return false;
    const clean: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(payload)) {
      if (v !== undefined && v !== "") clean[k] = v;
    }
    return ws.send(clean);
  }, []);

  const requestScreenshot = useCallback(() => send({ action: "screenshot" }), [send]);
  const toggleScreenStream = useCallback(
    (active: boolean) => {
      const ok = send({ action: "screen_stream", active });
      if (ok) setStreaming(active);
      return ok;
    },
    [send],
  );

  const disconnect = useCallback(() => {
    socketRef.current?.disconnect();
    sseRef.current?.abort();
    socketRef.current = null;
    activeRef.current = null;
    setStatus({ kind: "idle" });
    setTelemetry(null);
    setScreen(null);
    setStreaming(false);
  }, []);

  const connect = useCallback(
    async (target: ServerNode): Promise<boolean> => {
      disconnect();
      setStatus({ kind: "connecting" });

      const socket = new GenioSocket(
        () => setStatus({ kind: "connected", node: target.host }),
        (event: GenioEvent) => {
          if (event.type === "screen" || event.type === "browser_view") {
            setScreen(event.data_b64);
            return;
          }
          if (event.type === "telemetry") {
            setTelemetry(event as unknown as TelemetrySnapshot);
            return;
          }
          if (isChatEvent(event)) {
            setChat((prev) => [...prev.slice(-299), event]);
          }
        },
        () => setStatus({ kind: "error", message: `WebSocket error on ${target.host}` }),
        () => {
          if (activeRef.current) {
            setStatus({ kind: "idle" });
            setTelemetry(null);
            setScreen(null);
            setStreaming(false);
          }
        },
      );
      socketRef.current = socket;
      activeRef.current = target;

      try {
        await socket.connect(target);
      } catch {
        setStatus({ kind: "error", message: `cannot reach ws://${target.host}:${target.port}` });
        return false;
      }

      const controller = new AbortController();
      sseRef.current = controller;
      streamTelemetry(target, setTelemetry, controller.signal).catch(() => {
        /* telemetry is best-effort */
      });

      setChat((prev) => [
        ...prev.slice(-299),
        { type: "answer", text: `Connected to ${target.host}:${target.port}` },
      ]);
      return true;
    },
    [disconnect],
  );

  useEffect(() => () => disconnect(), [disconnect]);

  return {
    status,
    socket: socketRef.current as GenioSocket | null,
    telemetry,
    chat,
    screen,
    streaming,
    addChat: setChat,
    connect,
    disconnect,
    send,
    requestScreenshot,
    toggleScreenStream,
    error: status.kind === "error" ? status.message : undefined,
  };
}