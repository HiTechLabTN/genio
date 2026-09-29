import type { ChatEvent, GenioEvent, ServerNode, TelemetrySnapshot } from "./types";

export const CHAT_EVENT_TYPES = new Set([
  "thought",
  "answer",
  "tool_call",
  "tool_result",
  "stats",
  "error",
  "attached",
  "killed",
  "armed",
  "artifact",
  "session",
  "user",
]);

export function isChatEvent(event: GenioEvent): event is ChatEvent {
  // Tolerant: missing type or unknown types are NOT chat events — caller handles generically
  return typeof (event as Record<string, unknown>).type === "string" &&
    CHAT_EVENT_TYPES.has((event as Record<string, unknown>).type as string);
}

export function buildWsUrl(target: ServerNode): string {
  const host = target.host.trim().replace(/^ws:\/\//, "").replace(/^wss:\/\//, "");
  const qs = target.key ? `?key=${encodeURIComponent(target.key)}` : "";
  // P4: HiTech Cloud = same-origin wss://genio.hitech.tn/ws/agent (nginx proxies /ws → pop-os)
  if (host === "genio.hitech.tn" || target.id === "hitech-cloud") {
    const proto = typeof window !== "undefined" && window.location.protocol === "https:" ? "wss" : "wss";
    // omit :443 for standard https
    return `${proto}://${host}/ws/agent${qs}`;
  }
  // Local preview/dev page + local target → same-origin /ws/agent so the
  // browser never touches :8000 directly (CSP-safe). The local Vite
  // server proxies /ws → 127.0.0.1:8000; production nginx does the same.
  // Cloud and explicit remote targets keep their direct URLs below.
  if (isLocalPage() && LOCAL_DAEMON_HOSTS.has(host)) {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    return `${proto}://${window.location.host}/ws/agent${qs}`;
  }
  const proto = "ws";
  return `${proto}://${host}:${target.port}/ws/agent${qs}`;
}

/** True when the frontend page itself is served from this machine. */
export function isLocalPage(): boolean {
  try {
    const h = window.location.hostname;
    return h === "localhost" || h === "127.0.0.1";
  } catch {
    return false;
  }
}

/** Daemon hostnames that live on this machine (Tailscale/DNS or loopback). */
const LOCAL_DAEMON_HOSTS = new Set(["tn", "pop", "pop-os", "localhost", "127.0.0.1"]);

const PING_INTERVAL_MS = 15_000;

/** Lightweight WebSocket layer: classification, reconnect, callbacks. */
export class GenioSocket {
  private ws: WebSocket | null = null;
  private readonly pings = new Set<number>();

  constructor(
    private readonly onOpen: () => void,
    private readonly onEvent: (event: GenioEvent) => void,
    private readonly onSocketError: (message: string) => void,
    private readonly onClose: () => void,
  ) {}

  get readyState(): number {
    return this.ws ? this.ws.readyState : WebSocket.CLOSED;
  }
  get isOpen(): boolean {
    return this.readyState === WebSocket.OPEN;
  }

  connect(target: ServerNode): Promise<boolean> {
    return new Promise((resolve, reject) => {
      const socket = new WebSocket(buildWsUrl(target));
      this.ws = socket;

      socket.onopen = () => {
        this.startHeartbeat();
        this.onOpen();
        this.send({ action: "ping" });
        resolve(true);
      };
      socket.onerror = () => {
        if (socket.readyState !== WebSocket.OPEN) {
          this.onSocketError("WebSocket error");
          reject(new Error("WebSocket connection failed"));
        }
      };
      socket.onclose = () => {
        this.stopHeartbeat();
        this.ws = null;
        this.onClose();
      };
      socket.onmessage = (event) => {
        try {
          const parsed = JSON.parse(String(event.data)) as GenioEvent;
          // Tolerant: ensure type is string, coerce missing/invalid to error-like event
          if (!parsed || typeof (parsed as Record<string, unknown>).type !== "string") {
            this.onEvent({ type: "error", message: "malformed event (missing type)", raw: String(event.data) } as unknown as GenioEvent);
            return;
          }
          this.onEvent(parsed);
        } catch {
          // non-JSON frames are surfaced as tolerant error, not dropped
          this.onEvent({ type: "error", message: "non-JSON frame", raw: String(event.data) } as unknown as GenioEvent);
        }
      };
    });
  }

  send(payload: Record<string, unknown>): boolean {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return false;
    this.ws.send(JSON.stringify(payload));
    return true;
  }

  disconnect(): void {
    this.stopHeartbeat();
    if (this.ws) {
      try {
        this.ws.close();
      } catch {
        /* noop */
      }
      this.ws = null;
    }
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    const id = window.setInterval(() => {
      // Paused while a prompt run is in flight (see setHeartbeatPaused):
      // fewer concurrent sends on a saturated link, resumed when the run ends.
      if (this.isOpen && !this.heartbeatPaused) this.send({ action: "ping" });
    }, PING_INTERVAL_MS);
    this.pings.add(id);
  }

  private heartbeatPaused = false;

  /** Pause/resume the 15s app-level ping (protocol keepalive is untouched). */
  setHeartbeatPaused(paused: boolean): void {
    this.heartbeatPaused = paused;
  }

  private stopHeartbeat(): void {
    for (const id of this.pings) window.clearInterval(id);
    this.pings.clear();
  }
}

/** Fetch-based SSE reader (auth via headers, unlike EventSource). */
export async function streamTelemetry(
  target: ServerNode,
  onSnapshot: (snapshot: TelemetrySnapshot) => void,
  signal: AbortSignal,
): Promise<void> {
  const headers: Record<string, string> = { Accept: "text/event-stream" };
  if (target.key) headers["X-API-Key"] = target.key;
  // P4: HiTech Cloud uses same-origin https://genio.hitech.tn/api/v1/telemetry (nginx proxies /api → pop-os)
  let url: string;
  if (target.host === "genio.hitech.tn" || target.id === "hitech-cloud") {
    url = `/api/v1/telemetry`;
    // if not same-origin (e.g., dev), fallback to https://genio.hitech.tn
    if (typeof window !== "undefined" && window.location.hostname !== "genio.hitech.tn") {
      url = `https://genio.hitech.tn/api/v1/telemetry`;
    }
  } else if (isLocalPage() && LOCAL_DAEMON_HOSTS.has(target.host.trim())) {
    // Local preview/dev page → same-origin /api (Vite proxies → 127.0.0.1:8000).
    url = `/api/v1/telemetry`;
  } else {
    url = `http://${target.host}:${target.port}/api/v1/telemetry`;
  }
  const response = await fetch(url, {
    headers,
    signal,
  });
  if (!response.ok) throw new Error(`telemetry HTTP ${response.status}`);
  if (!response.body) throw new Error("no response body");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop() ?? "";
      for (const block of events) {
        for (const line of block.split("\n")) {
          if (!line.startsWith("data:")) continue;
          try {
            onSnapshot(JSON.parse(line.slice(5).trim()) as TelemetrySnapshot);
          } catch {
            /* skip malformed frame */
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}