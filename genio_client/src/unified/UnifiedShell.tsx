import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import PresenceAvatar from "../presence/PresenceAvatar";
import { resolvePresence, layoutModeFor } from "../presence/resolve";
import { loadPrefs, savePrefs, type Density } from "../presence/preferences";
import type { GenioPresenceState } from "../presence/types";

/** Minimal chat-event view (real fields only; timestamps optional). */
export interface ChatLike {
  type: string;
  text?: string;
  message?: string;
  command?: string;
  timestamp?: number;
}

export interface TelemetryLike {
  cpu_percent?: number;
  ram_percent?: number;
  gpu_percent?: number;
  net_up_kbs?: number;
  net_down_kbs?: number;
  model?: string;
  provider?: string;
  tokens_per_s?: number;
}

export interface UnifiedProps {
  chat: ChatLike[];
  agentStatusKind: string;
  socketState: "idle" | "connecting" | "connected" | "error" | "disconnected";
  streaming: boolean;
  typing?: boolean;
  connected: boolean;
  online?: boolean;
  error?: string;
  telemetry: TelemetryLike | null;
  taskActive: boolean;
  currentTool?: string;
  onReconnect?: () => void;
  onCancelTask?: () => void;
  onSend?: (text: string) => void;
}

const LEVEL1: Record<string, string> = {
  idle: "Genio is ready",
  greeting: "Genio is ready",
  listening: "Genio is listening",
  understanding: "Genio is understanding your request",
  thinking: "Genio is thinking",
  planning: "Genio is planning your request",
  explaining: "Genio is answering",
  executing: "Genio is working on your task",
  waiting: "Genio is waiting for the service",
  asking_user: "Genio needs your input",
  success: "Task completed",
  warning: "Attention needed",
  error: "Something went wrong",
  recovering: "Genio is recovering",
  celebrating: "Task completed",
  sleeping: "Genio is idle",
  disconnected: "Connection lost",
  attention: "Genio needs your attention",
};

function fmtTime(ts?: number): string {
  if (!ts) return "";
  try {
    return new Date(ts).toLocaleTimeString();
  } catch {
    return "";
  }
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-2 py-1">
      <span className="text-white/50">{label}</span>
      <span className="font-mono text-white/90">{value}</span>
    </div>
  );
}

export function ResourcePanel({ telemetry, compact }: { telemetry: TelemetryLike | null; compact?: boolean }) {
  const v = (x: number | undefined, unit: string) =>
    x === undefined || x === null || Number.isNaN(x) ? "Unavailable" : `${x}${unit}`;
  return (
    <section aria-label="Resources" className="rounded-[var(--g5-radius-m)] border border-[var(--g5-border)] bg-[var(--g5-carbon)] p-3 text-xs">
      <h3 className="font-bold text-white">Resources</h3>
      <div className="mt-1">
        <Metric label="CPU" value={v(telemetry?.cpu_percent, "%")} />
        <Metric label="RAM" value={v(telemetry?.ram_percent, "%")} />
        <Metric label="GPU" value={v(telemetry?.gpu_percent, "%")} />
        {!compact && (
          <>
            <Metric label="Net ↑" value={v(telemetry?.net_up_kbs, " KB/s")} />
            <Metric label="Net ↓" value={v(telemetry?.net_down_kbs, " KB/s")} />
            <Metric label="Model" value={telemetry?.model ?? "Unavailable"} />
            <Metric label="Throughput" value={telemetry?.tokens_per_s !== undefined ? `${telemetry.tokens_per_s} tok/s` : "Unavailable"} />
          </>
        )}
      </div>
    </section>
  );
}

export function TaskPanel({ chat, taskActive, currentTool, onCancelTask, runElapsedMs }: {
  chat: ChatLike[]; taskActive: boolean; currentTool?: string;
  onCancelTask?: () => void; runElapsedMs: number | null;
}) {
  const steps = useMemo(() => chat.filter((e) => e.type === "thought" || e.type === "tool_call" || e.type === "tool_result"), [chat]);
  const lastTool = useMemo(() => {
    for (let i = chat.length - 1; i >= 0; i--) {
      if (chat[i].type === "tool_call") return chat[i].command || "tool";
    }
    return currentTool;
  }, [chat, currentTool]);
  return (
    <section aria-label="Current task" className="rounded-[var(--g5-radius-m)] border border-[var(--g5-border)] bg-[var(--g5-carbon)] p-3 text-xs">
      <div className="flex items-center justify-between">
        <h3 className="font-bold text-white">Current task</h3>
        {taskActive && onCancelTask && (
          <button type="button" onClick={onCancelTask} className="g5-focusable rounded-full border border-rose-400/40 px-2.5 py-1 text-[11px] text-rose-300 hover:bg-rose-400/10">
            Cancel
          </button>
        )}
      </div>
      {!taskActive && steps.length === 0 && <p className="mt-1 text-white/50">No active task. Send a message to start.</p>}
      <ul className="mt-1 space-y-1">
        {steps.slice(-6).map((s, i) => (
          <li key={i} className="text-white/75">
            <span className="font-mono text-cyan-300">[{s.type}]</span> {(s.text || s.command || "").slice(0, 120)}
          </li>
        ))}
      </ul>
      {(taskActive || lastTool) && (
        <div className="mt-2 border-t border-[var(--g5-border)] pt-2 text-white/60">
          {lastTool && <p>Tool: <span className="font-mono text-white/85">{lastTool.slice(0, 80)}</span></p>}
          {runElapsedMs !== null && <p>Elapsed (client-observed): <span className="font-mono">{(runElapsedMs / 1000).toFixed(1)}s</span></p>}
        </div>
      )}
    </section>
  );
}

export function EventStream({ chat }: { chat: ChatLike[] }) {
  return (
    <section aria-label="Event stream" className="rounded-[var(--g5-radius-m)] border border-[var(--g5-border)] bg-black/40 p-3 font-mono text-[11px]">
      <h3 className="font-bold text-white">Events</h3>
      {chat.length === 0 && <p className="mt-1 text-white/40">No events yet.</p>}
      <ol className="mt-1 max-h-56 space-y-1 overflow-y-auto">
        {chat.map((e, i) => (
          <li key={i} className="text-white/70">
            <span className="text-white/35">#{i + 1}{e.timestamp ? ` ${fmtTime(e.timestamp)}` : ""}</span>{" "}
            <span className="text-cyan-300">{e.type}</span>{" "}
            {(e.text || e.message || e.command || "").slice(0, 140)}
          </li>
        ))}
      </ol>
    </section>
  );
}

export function DensitySettings({ density, onChange }: { density: Density; onChange: (d: Density) => void }) {
  return (
    <fieldset>
      <legend className="text-xs font-bold text-white">Information density</legend>
      <div className="mt-1 flex gap-2" role="radiogroup" aria-label="Information density">
        {(["simple", "detailed", "advanced"] as Density[]).map((d) => (
          <label key={d} className="flex items-center gap-1 text-xs text-white/75">
            <input
              type="radio"
              name="genio-density"
              checked={density === d}
              onChange={() => onChange(d)}
              className="accent-cyan-400"
            />
            {d[0].toUpperCase() + d.slice(1)}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export function AmbientSettings({ ambient, reduced, onAmbient, onReduced }: {
  ambient: boolean; reduced: boolean;
  onAmbient: (v: boolean) => void; onReduced: (v: boolean) => void;
}) {
  return (
    <fieldset>
      <legend className="text-xs font-bold text-white">Ambient effects</legend>
      <div className="mt-1 flex gap-4 text-xs text-white/75">
        <label className="flex items-center gap-1">
          <input type="checkbox" checked={ambient} onChange={(e) => onAmbient(e.target.checked)} className="accent-cyan-400" />
          Glow/particles
        </label>
        <label className="flex items-center gap-1">
          <input type="checkbox" checked={reduced} onChange={(e) => onReduced(e.target.checked)} className="accent-cyan-400" />
          Reduced motion
        </label>
      </div>
      <p className="mt-1 text-[11px] text-white/40">Security alerts, task state and errors are never disabled by these settings.</p>
    </fieldset>
  );
}

export default function UnifiedShell(props: UnifiedProps) {
  const [prefs, setPrefs] = useState(loadPrefs);
  const [runStart, setRunStart] = useState<number | null>(null);
  const [now, setNow] = useState(Date.now());
  const mountRef = useRef(Date.now());
  const wasActive = useRef(false);

  const save = (p: typeof prefs) => { setPrefs(p); savePrefs(p); };
  const osReduced = typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  useEffect(() => {
    if (props.taskActive && !wasActive.current) setRunStart(Date.now());
    if (!props.taskActive) setRunStart(null);
    wasActive.current = props.taskActive;
  }, [props.taskActive]);
  useEffect(() => {
    if (runStart === null) return;
    const id = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(id);
  }, [runStart === null]);

  const presence: GenioPresenceState = resolvePresence({
    socket: props.connected ? "connected" : props.socketState,
    agent: props.agentStatusKind,
    streaming: props.streaming,
    typing: false,
    taskActive: props.taskActive,
    needsInput: props.agentStatusKind === "awaiting_input",
    error: props.error,
    lastOutcome: undefined,
    // Real client-observed session age (mount time) — greeting shows on fresh loads.
    sessionAgeMin: (Date.now() - mountRef.current) / 60000,
  });
  const advanced = prefs.density === "advanced";
  const detailed = advanced || prefs.density === "detailed";

  const lastAnswer = [...props.chat].reverse().find((e) => e.type === "answer");
  const lastThought = [...props.chat].reverse().find((e) => e.type === "thought");
  const offline = props.online === false || (!props.connected && props.socketState === "disconnected");
  const failed = presence.semanticState === "error" || presence.semanticState === "disconnected";

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto p-3 sm:p-4" data-layout-mode={layoutModeFor(presence, advanced)}>
      {/* Level 1 — what is happening (live region, single, polite) */}
      <section aria-label="Status" className="rounded-[var(--g5-radius-m)] border border-[var(--g5-border)] bg-[var(--g5-carbon)] p-4">
        <div className="flex items-center gap-3">
          <div className="shrink-0">
            <PresenceAvatar presence={presence} compact={prefs.mascotSize === "compact"} />
          </div>
          <div className="min-w-0 flex-1">
            <p role="status" aria-live="polite" className="text-base font-bold text-white sm:text-lg">
              {LEVEL1[presence.semanticState] ?? "Genio"}
            </p>
            {/* Level 2 — what now */}
            {(lastThought?.text || props.currentTool) && (
              <p className="mt-0.5 truncate text-xs text-white/60">
                {props.currentTool ? `Tool: ${props.currentTool.slice(0, 60)}` : (lastThought?.text ?? "").slice(0, 90)}
              </p>
            )}
          </div>
        </div>
        {offline && (
          <p role="alert" className="mt-2 rounded-lg border border-amber-400/30 bg-amber-400/10 p-2 text-xs text-amber-200">
            Offline — navigation, docs, settings and preferences stay usable. AI features need a connection.
          </p>
        )}
        {failed && (
          <div role="alert" className="mt-2 rounded-lg border border-rose-400/30 bg-rose-400/10 p-2 text-xs">
            <p className="font-bold text-rose-200">Connection lost{props.error ? `: ${props.error.slice(0, 160)}` : ""}</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {props.onReconnect && (
                <button type="button" onClick={props.onReconnect} className="g5-focusable rounded-full bg-cyan-400 px-3 py-1 font-bold text-slate-900">Reconnect</button>
              )}
              <Link to="/docs" className="g5-focusable rounded-full border border-white/15 px-3 py-1 text-white/80">Details in docs</Link>
            </div>
          </div>
        )}
      </section>

      {/* Level 3 — result summary */}
      {lastAnswer?.text && !props.taskActive && (
        <section aria-label="Result" className="rounded-[var(--g5-radius-m)] border border-[var(--g5-border)] bg-[var(--g5-carbon)] p-3 text-xs text-white/80">
          <h3 className="font-bold text-white">Result</h3>
          <p className="mt-1 line-clamp-4">{lastAnswer.text}</p>
        </section>
      )}

      {/* Adaptive panels: attention target decides order */}
      <div className="grid gap-3 lg:grid-cols-2">
        <div className={presence.attentionTarget === "task" ? "order-1" : "order-2 lg:order-1"}>
          <TaskPanel
            chat={props.chat}
            taskActive={props.taskActive}
            currentTool={props.currentTool}
            onCancelTask={props.onCancelTask}
            runElapsedMs={runStart === null ? null : now - runStart}
          />
        </div>
        <div className={presence.attentionTarget === "task" ? "order-2 lg:order-2" : "order-1 lg:order-2"}>
          <ResourcePanel telemetry={props.telemetry} compact={!detailed} />
        </div>
      </div>

      {/* Level 4 — technical details, opt-in */}
      <details className="rounded-[var(--g5-radius-m)] border border-[var(--g5-border)] bg-black/30 p-3 text-xs">
        <summary className="g5-focusable cursor-pointer font-bold text-white">
          Technical details {advanced ? "(advanced on)" : "(opt-in)"}
        </summary>
        <div className="mt-2 grid gap-3">
          <button
            type="button"
            onClick={() => save({ ...prefs, density: advanced ? "simple" : "advanced" })}
            aria-pressed={advanced}
            className="g5-focusable w-fit rounded-full border border-white/15 px-3 py-1 text-white/80"
          >
            {advanced ? "Hide advanced" : "Show advanced"}
          </button>
          {(detailed) && <EventStream chat={props.chat} />}
          <p className="font-mono text-[11px] text-white/50">
            presence={presence.semanticState} attention={presence.attentionTarget} intensity={presence.intensity} gesture={presence.gesture}
          </p>
        </div>
      </details>

      <section aria-label="Experience settings" className="rounded-[var(--g5-radius-m)] border border-[var(--g5-border)] bg-[var(--g5-carbon)] p-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <DensitySettings density={prefs.density} onChange={(density) => save({ ...prefs, density })} />
          <AmbientSettings
            ambient={prefs.ambient}
            reduced={prefs.animation !== "on" || osReduced}
            onAmbient={(ambient) => save({ ...prefs, ambient })}
            onReduced={(v) => save({ ...prefs, animation: v ? "reduced" : "on" })}
          />
        </div>
      </section>
    </div>
  );
}
