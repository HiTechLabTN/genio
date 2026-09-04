import { useCallback, useEffect, useRef, useState } from "react";
import type {
  AgentStatus,
  Attachment,
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
  const [agentStatus, setAgentStatus] = useState<AgentStatus>({ kind: "idle" });
  const [telemetry, setTelemetry] = useState<TelemetrySnapshot | null>(null);
  const [telemetryStale, setTelemetryStale] = useState(false);
  const [chat, setChat] = useState<ChatEvent[]>([]);
  const [screen, setScreen] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);

  const socketRef = useRef<GenioSocket | null>(null);
  const sseRef = useRef<AbortController | null>(null);
  const activeRef = useRef<ServerNode | null>(null);
  const lastTelemetryAtRef = useRef<number>(0);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef<number | null>(null);
  const shouldReconnectRef = useRef(false);

  // flag telemetry as stale when no snapshot arrives within a window
  // (backend event loop blocked during heavy LLM / tool execution)
  useEffect(() => {
    const id = window.setInterval(() => {
      const staleThresholdMs = 5000;
      const last = lastTelemetryAtRef.current;
      if (last > 0 && Date.now() - last > staleThresholdMs) {
        setTelemetryStale(true);
      } else {
        setTelemetryStale(false);
      }
    }, 1500);
    return () => window.clearInterval(id);
  }, []);

  const send = useCallback((payload: Record<string, unknown>) => {
    const ws = socketRef.current;
    if (!ws) return false;
    const clean: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(payload)) {
      if (v !== undefined && v !== "") clean[k] = v;
    }
    // track agent lifecycle
    if (clean.action === "prompt") setAgentStatus({ kind: "thinking" });
    if (clean.action === "kill") setAgentStatus({ kind: "idle" });
    return ws.send(clean);
  }, []);

  const sendPrompt = useCallback(
    (text: string, attachments?: Attachment[]) => {
      const ws = socketRef.current;
      if (!ws) return false;
      const filePayload = attachments?.map((a) => ({
        name: a.name,
        content: a.content ?? (a.type.startsWith("image/") ? a.dataB64 : undefined),
      }));
      // render the user message immediately
      setChat((prev) => [
        ...prev.slice(-299),
        {
          type: "user",
          text,
          attachments: filePayload?.filter((f) => f.content !== undefined),
          timestamp: Date.now(),
        },
      ]);
      setAgentStatus({ kind: "thinking" });
      return send({ action: "prompt", text, attachments: filePayload?.length ? filePayload : undefined });
    },
    [send],
  );

  const kill = useCallback(() => send({ action: "kill", reason: "user stop" }), [send]);
  const continuePrompt = useCallback(
    (lastPrompt: string) => {
      if (!lastPrompt) return false;
      setChat((prev) => [
        ...prev.slice(-299),
        { type: "user", text: lastPrompt, timestamp: Date.now() },
      ]);
      setAgentStatus({ kind: "thinking" });
      return send({ action: "prompt", text: lastPrompt });
    },
    [send],
  );
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
    shouldReconnectRef.current = false;
    reconnectAttemptsRef.current = 0;
    if (reconnectTimerRef.current !== null) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    socketRef.current?.disconnect();
    sseRef.current?.abort();
    socketRef.current = null;
    activeRef.current = null;
    setStatus({ kind: "idle" });
    setAgentStatus({ kind: "idle" });
    setTelemetry(null);
    setTelemetryStale(false);
    lastTelemetryAtRef.current = 0;
    setScreen(null);
    setStreaming(false);
  }, []);

  const scheduleReconnect = useCallback((target: ServerNode) => {
    if (!shouldReconnectRef.current) return;
    if (document.hidden) return; // wait for visibilitychange
    const attempt = reconnectAttemptsRef.current;
    const delay = Math.min(30000, 1000 * Math.pow(2, attempt));
    reconnectAttemptsRef.current = attempt + 1;
    if (reconnectTimerRef.current !== null) clearTimeout(reconnectTimerRef.current);
    reconnectTimerRef.current = window.setTimeout(async () => {
      if (!shouldReconnectRef.current || document.hidden) return;
      // try reconnect
      try {
        // reuse internal connect without full disconnect reset of shouldReconnect
        shouldReconnectRef.current = true; // keep true
        // we call the same logic but avoid infinite recursion — directly attempt socket reconnect
        const prevTarget = activeRef.current || target;
        // clean old socket but keep activeRef
        socketRef.current?.disconnect();
        sseRef.current?.abort();
        const socket = new GenioSocket(
          () => {
            reconnectAttemptsRef.current = 0;
            setStatus({ kind: "connected", node: prevTarget.host });
          },
          (event: GenioEvent) => {
            const ev = event as Record<string, unknown>;
            if (ev.type === "screen" || ev.type === "browser_view") { setScreen(ev.data_b64 as string); return; }
            if (ev.type === "telemetry") { setTelemetry(event as unknown as TelemetrySnapshot); lastTelemetryAtRef.current = Date.now(); return; }
            if (isChatEvent(event)) {
              const chatEv = event as ChatEvent;
              setChat((prev) => [...prev.slice(-299), chatEv]);
              if ((chatEv as Record<string, unknown>).type === "tool_call") {
                const toolName = extractToolName((chatEv as { command: string }).command || "");
                setAgentStatus({ kind: "executing", tool: toolName });
              } else if (chatEv.type === "stats" || chatEv.type === "answer" || chatEv.type === "artifact") setAgentStatus({ kind: "completed" });
              else if (chatEv.type === "error" || chatEv.type === "killed") setAgentStatus({ kind: "idle" });
              return;
            }
            setChat((prev) => [...prev.slice(-299), event as unknown as ChatEvent]);
          },
          () => setStatus({ kind: "error", message: `WebSocket error on ${prevTarget.host}` }),
          () => {
            if (shouldReconnectRef.current) {
              setStatus({ kind: "idle" });
              setAgentStatus({ kind: "idle" });
              setTelemetry(null);
              setScreen(null);
              setStreaming(false);
              scheduleReconnect(prevTarget);
            }
          },
        );
        socketRef.current = socket;
        activeRef.current = prevTarget;
        await socket.connect(prevTarget);
        const controller = new AbortController();
        sseRef.current = controller;
        streamTelemetry(prevTarget, setTelemetry, controller.signal).catch(() => {});
        setStatus({ kind: "connected", node: prevTarget.host });
        reconnectAttemptsRef.current = 0;
      } catch {
        scheduleReconnect(target);
      }
    }, delay) as unknown as number;
  }, []);

  const connect = useCallback(
    async (target: ServerNode): Promise<boolean> => {
      shouldReconnectRef.current = true;
      reconnectAttemptsRef.current = 0;
      if (reconnectTimerRef.current !== null) { clearTimeout(reconnectTimerRef.current); reconnectTimerRef.current = null; }
      disconnect();
      shouldReconnectRef.current = true;
      reconnectAttemptsRef.current = 0;
      setStatus({ kind: "connecting" });

       const socket = new GenioSocket(
        () => setStatus({ kind: "connected", node: target.host }),
        (event: GenioEvent) => {
          const ev = event as Record<string, unknown>;
          if (ev.type === "screen" || ev.type === "browser_view") {
            setScreen(ev.data_b64 as string);
            return;
          }
          if (ev.type === "telemetry") {
            setTelemetry(event as unknown as TelemetrySnapshot);
            lastTelemetryAtRef.current = Date.now();
            return;
          }
          // tolerant: artifact/session are handled as chat but also generic fallback
          if (isChatEvent(event)) {
            // coerce unknown future types to ChatEvent via tolerant fallback
            const chatEv = event as ChatEvent;
            setChat((prev) => [...prev.slice(-299), chatEv]);
            // update agent status from chat events
            if ((chatEv as Record<string, unknown>).type === "tool_call") {
              const toolName = extractToolName((chatEv as { command: string }).command || "");
              setAgentStatus({ kind: "executing", tool: toolName });
            } else if (chatEv.type === "stats" || chatEv.type === "answer" || chatEv.type === "artifact") {
              setAgentStatus({ kind: "completed" });
            } else if (chatEv.type === "error") {
              setAgentStatus({ kind: "idle" });
            } else if (chatEv.type === "killed") {
              setAgentStatus({ kind: "idle" });
            }
            return;
          }
          // Unknown tolerant fallback: surface as chat so UI never loses message
          setChat((prev) => [...prev.slice(-299), event as unknown as ChatEvent]);
        },
        () => setStatus({ kind: "error", message: `WebSocket error on ${target.host}` }),
        () => {
          if (activeRef.current || shouldReconnectRef.current) {
            setStatus({ kind: "idle" });
            setAgentStatus({ kind: "idle" });
            setTelemetry(null);
            setScreen(null);
            setStreaming(false);
            if (shouldReconnectRef.current && activeRef.current) {
              scheduleReconnect(activeRef.current);
            }
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
      streamTelemetry(target, setTelemetry, controller.signal).catch(() => {});

      setChat((prev) => [
        ...prev.slice(-299),
        { type: "answer", text: `Connected to ${target.host}:${target.port}` },
      ]);
      return true;
    },
    [disconnect, scheduleReconnect],
  );

  // P3: WS reconnect on visibilitychange (when tab becomes visible again)
  useEffect(() => {
    const onVis = () => {
      if (!document.hidden && shouldReconnectRef.current && activeRef.current) {
        const s = socketRef.current;
        if (!s || s.readyState !== WebSocket.OPEN) {
          reconnectAttemptsRef.current = 0;
          scheduleReconnect(activeRef.current);
        }
      }
    };
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, [scheduleReconnect]);

  useEffect(() => () => disconnect(), [disconnect]);

  return {
    status,
    agentStatus,
    socket: socketRef.current as GenioSocket | null,
    telemetry,
    telemetryStale,
    chat,
    screen,
    streaming,
    addChat: setChat,
    connect,
    disconnect,
    send,
    sendPrompt,
    kill,
    continuePrompt,
    requestScreenshot,
    toggleScreenStream,
    error: status.kind === "error" ? status.message : undefined,
  };
}

function extractToolName(command: string): string {
  try {
    const obj = JSON.parse(command);
    return obj.tool ?? command.slice(0, 30);
  } catch {
    return command.split(/\s+/)[0].slice(0, 30);
  }
}