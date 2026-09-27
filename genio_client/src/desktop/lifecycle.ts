/**
 * Desktop lifecycle — launch→bootstrap→runtime detection→connect→ready.
 * States are explicit; READY requires real health checks (never claimed).
 */
export type LifecycleState =
  | "launch" | "bootstrap" | "detecting-runtime" | "connecting"
  | "ready" | "degraded" | "failed";

export interface LifecycleSnapshot {
  state: LifecycleState;
  shell: "web" | "tauri";
  apiOk: boolean;
  wsOk: boolean;
  detail: string;
}

export async function probeRuntime(apiBase: string, timeoutMs = 6000): Promise<{ apiOk: boolean; wsOk: boolean; detail: string }> {
  let apiOk = false;
  try {
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(), timeoutMs);
    const r = await fetch(`${apiBase}/health`, { signal: ctl.signal });
    apiOk = r.status === 200;
    clearTimeout(t);
  } catch { apiOk = false; }
  // WS probe: real handshake attempt, short timeout, closed immediately.
  let wsOk = false;
  try {
    const wsUrl = apiBase.replace(/^http/, "ws") + "/ws/agent";
    await new Promise<void>((resolve) => {
      let done = false;
      const finish = (ok: boolean) => { if (!done) { done = true; wsOk = ok; resolve(); } };
      const ws = new WebSocket(wsUrl);
      const t = setTimeout(() => { try { ws.close(); } catch { /* ignore */ } finish(false); }, timeoutMs);
      ws.onopen = () => { clearTimeout(t); try { ws.close(); } catch { /* ignore */ } finish(true); };
      ws.onerror = () => { clearTimeout(t); finish(false); };
    });
  } catch { wsOk = false; }
  const detail = apiOk && wsOk ? "runtime healthy"
    : apiOk ? "API up, WebSocket unreachable"
    : "runtime unreachable";
  return { apiOk, wsOk, detail };
}

export function lifecycleFromProbes(_shell: "web" | "tauri", apiOk: boolean, wsOk: boolean): LifecycleState {
  if (apiOk && wsOk) return "ready";
  if (apiOk || wsOk) return "degraded";
  return "failed";
}
