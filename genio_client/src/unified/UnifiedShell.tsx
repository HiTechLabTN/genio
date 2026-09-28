import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import Mascot from "./Mascot";
import { resolvePresence, layoutModeFor } from "../presence/resolve";
import { resolveEngine } from "../presence/engine";
import { buildTaskModel, sanitizeToolText } from "./taskModel";
import { loadPrefs, savePrefs, type Density } from "../presence/preferences";
import type { GenioPresenceState } from "../presence/types";
import { t, useLang, type Lang } from "../lib/lang";

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

const LEVEL1_KEY: Record<string, string> = {
  idle: "shell.ready",
  greeting: "shell.greeting",
  listening: "shell.listening",
  understanding: "shell.understanding",
  thinking: "shell.thinking",
  planning: "shell.planning",
  explaining: "shell.explaining",
  executing: "shell.executing",
  waiting: "shell.waiting",
  asking_user: "shell.asking",
  success: "shell.success",
  warning: "shell.warning",
  error: "shell.error",
  recovering: "shell.recovering",
  celebrating: "shell.celebrating",
  sleeping: "shell.sleeping",
  disconnected: "shell.disconnected",
  attention: "shell.attention",
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

export function ResourcePanel({ telemetry, compact, lang }: { telemetry: TelemetryLike | null; compact?: boolean; lang: Lang }) {
  const v = (x: number | undefined, unit: string) =>
    x === undefined || x === null || Number.isNaN(x) ? t(lang, "shell.unavailable") : `${x}${unit}`;
  return (
    <section aria-label={t(lang, "shell.resources")} className="rounded-[var(--g5-radius-m)] border border-[var(--g5-border)] bg-[var(--g5-carbon)] p-3 text-xs">
      <h3 className="font-bold text-white">{t(lang, "shell.resources")}</h3>
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

export function TaskPanel({ chat, taskActive, currentTool, onCancelTask, runElapsedMs, lang }: {
  chat: ChatLike[]; taskActive: boolean; currentTool?: string;
  onCancelTask?: () => void; runElapsedMs: number | null; lang: Lang;
}) {
  const steps = useMemo(() => chat.filter((e) => e.type === "thought" || e.type === "tool_call" || e.type === "tool_result"), [chat]);
  const lastTool: string | null = useMemo(() => {
    for (let i = chat.length - 1; i >= 0; i--) {
      if (chat[i].type === "tool_call") return chat[i].command || "tool";
    }
    return currentTool ?? null;
  }, [chat, currentTool]);
  return (
    <section aria-label={t(lang, "shell.current_task")} className="rounded-[var(--g5-radius-m)] border border-[var(--g5-border)] bg-[var(--g5-carbon)] p-3 text-xs">
      <div className="flex items-center justify-between">
        <h3 className="font-bold text-white">{t(lang, "shell.current_task")}</h3>
        {taskActive && onCancelTask && (
          <button type="button" onClick={onCancelTask} className="g5-focusable rounded-full border border-rose-400/40 px-2.5 py-1 text-[11px] text-rose-300 hover:bg-rose-400/10">
            {t(lang, "shell.cancel")}
          </button>
        )}
      </div>
      {!taskActive && steps.length === 0 && <p className="mt-1 text-white/50">{t(lang, "shell.no_task")}</p>}
      <ul className="mt-1 space-y-1">
        {steps.slice(-6).map((s, i) => (
          <li key={i} className="text-white/75">
            <span className="font-mono text-cyan-300">[{s.type}]</span> {(s.text || s.command || "").slice(0, 120)}
          </li>
        ))}
      </ul>
      {(taskActive || lastTool) && (
        <div className="mt-2 border-t border-[var(--g5-border)] pt-2 text-white/60">
          {lastTool && <p>{t(lang, "task.tool")}: <span className="font-mono text-white/85">{lastTool.slice(0, 80)}</span></p>}
          {runElapsedMs !== null && <p>{t(lang, "task.elapsed")}: <span className="font-mono">{(runElapsedMs / 1000).toFixed(1)}s</span></p>}
        </div>
      )}
    </section>
  );
}

/** Tool activity — real tool_call/result events only, sanitized. */
export function ToolActivity({ chat, lang }: { chat: ChatLike[]; lang: Lang }) {
  const items = chat.filter((e) => e.type === "tool_call" || e.type === "tool_result").slice(-5);
  if (items.length === 0) return null;
  return (
    <section aria-label={t(lang, "tool.activity")} className="rounded-[var(--g5-radius-m)] border border-[var(--g5-border)] bg-[var(--g5-carbon)] p-3 text-xs">
      <h3 className="font-bold text-white">{t(lang, "tool.activity")}</h3>
      <ul className="mt-1 space-y-1">
        {items.map((e, i) => (
          <li key={i} className="text-white/75">
            <span className="font-mono text-cyan-300">[{e.type}]</span>{" "}
            {sanitizeToolText(e.command || e.text || e.message || "tool").slice(0, 120)}
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Evidence — only backend-provided artifacts; otherwise honest empty. */
export function EvidencePanel({ chat, lang }: { chat: ChatLike[]; lang: Lang }) {
  const items = chat.filter((e) => (e as { artifact?: string }).artifact);
  return (
    <section aria-label={t(lang, "evidence")} className="rounded-[var(--g5-radius-m)] border border-[var(--g5-border)] bg-[var(--g5-carbon)] p-3 text-xs">
      <h3 className="font-bold text-white">{t(lang, "evidence")}</h3>
      {items.length === 0 ? (
        <p className="mt-1 text-white/50">{t(lang, "tool.evidence_unavailable")}</p>
      ) : (
        <ul className="mt-1 space-y-1">
          {items.map((e, i) => (
            <li key={i} className="font-mono text-[11px] text-white/75">
              {sanitizeToolText(String((e as { artifact?: string }).artifact)).slice(0, 160)}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function EventStream({ chat, lang }: { chat: ChatLike[]; lang: Lang }) {  return (
    <section aria-label={t(lang, "shell.events")} className="rounded-[var(--g5-radius-m)] border border-[var(--g5-border)] bg-black/40 p-3 font-mono text-[11px]">
      <h3 className="font-bold text-white">{t(lang, "shell.events")}</h3>
      {chat.length === 0 && <p className="mt-1 text-white/40">{t(lang, "events.empty")}</p>}
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

export function DensitySettings({ density, onChange, lang }: { density: Density; onChange: (d: Density) => void; lang: Lang }) {
  const names: Record<Density, string> = {
    simple: t(lang, "density.simple"),
    detailed: t(lang, "density.detailed"),
    advanced: t(lang, "density.advanced"),
  };
  return (
    <fieldset>
      <legend className="text-xs font-bold text-white">{t(lang, "settings.density")}</legend>
      <div className="mt-1 flex gap-2" role="radiogroup" aria-label={t(lang, "settings.density")}>
        {(["simple", "detailed", "advanced"] as Density[]).map((d) => (
          <label key={d} className="flex items-center gap-1 text-xs text-white/75">
            <input
              type="radio"
              name="genio-density"
              checked={density === d}
              onChange={() => onChange(d)}
              className="accent-cyan-400"
            />
            {names[d]}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export function AmbientSettings({ ambient, reduced, onAmbient, onReduced, lang }: {
  ambient: boolean; reduced: boolean;
  onAmbient: (v: boolean) => void; onReduced: (v: boolean) => void; lang: Lang;
}) {
  return (
    <fieldset>
      <legend className="text-xs font-bold text-white">{t(lang, "settings.ambient")}</legend>
      <div className="mt-1 flex gap-4 text-xs text-white/75">
        <label className="flex items-center gap-1">
          <input type="checkbox" checked={ambient} onChange={(e) => onAmbient(e.target.checked)} className="accent-cyan-400" />
          {t(lang, "ambient.glow")}
        </label>
        <label className="flex items-center gap-1">
          <input type="checkbox" checked={reduced} onChange={(e) => onReduced(e.target.checked)} className="accent-cyan-400" />
          {t(lang, "ambient.reduced")}
        </label>
      </div>
      <p className="mt-1 text-[11px] text-white/40">{t(lang, "ambient.note")}</p>
    </fieldset>
  );
}

export default function UnifiedShell(props: UnifiedProps) {
  const [prefs, setPrefs] = useState(loadPrefs);
  const [runStart, setRunStart] = useState<number | null>(null);
  const [now, setNow] = useState(Date.now());
  const mountRef = useRef(Date.now());
  const wasActive = useRef(false);
  const [lang] = useLang();

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

  const presence: GenioPresenceState = resolvePresence({    socket: props.connected ? "connected" : props.socketState,
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

  // Engine (G6-B): same facts → engine state + visual config. No duplicate machine.
  const engine = resolveEngine({
    online: props.online !== false,
    socket: props.connected ? "connected" : props.socketState,
    agent: props.agentStatusKind,
    streaming: props.streaming,
    typing: false,
    taskActive: props.taskActive,
    toolActive: props.chat.some((e) => e.type === "tool_call"),
    needsInput: props.agentStatusKind === "awaiting_input",
    error: props.error,
    lastOutcome: undefined,
    sessionAgeMin: (Date.now() - mountRef.current) / 60000,
  });
  // Typed task model from real chat events (progress UNKNOWN unless backend measures).
  const task = buildTaskModel({
    active: props.taskActive,
    result: [...props.chat].reverse().find((e) => e.type === "answer")?.text ?? "",
    error: props.error ?? null,
    cancelRequested: false,
    events: props.chat,
  });

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
            <Mascot presence={presence} engine={engine.engine} size={prefs.mascotSize === "compact" ? 56 : undefined} />
          </div>
          <div className="min-w-0 flex-1">
            <p role="status" aria-live="polite" className="text-base font-bold text-white sm:text-lg">
              {t(lang, LEVEL1_KEY[presence.semanticState] ?? "shell.ready")}
            </p>
            {/* Level 2 — what now */}
            {(lastThought?.text || props.currentTool) && (
              <p className="mt-0.5 truncate text-xs text-white/60">
                {props.currentTool ? `${t(lang, "task.tool")}: ${props.currentTool.slice(0, 60)}` : (lastThought?.text ?? "").slice(0, 90)}
              </p>
            )}
          </div>
        </div>
        {offline && (
          <p role="alert" className="mt-2 rounded-lg border border-amber-400/30 bg-amber-400/10 p-2 text-xs text-amber-200">
            {t(lang, "shell.offline")}
          </p>
        )}
        {failed && (
          <div role="alert" className="mt-2 rounded-lg border border-rose-400/30 bg-rose-400/10 p-2 text-xs">
            <p className="font-bold text-rose-200">{t(lang, "shell.connection_lost")}{props.error ? `: ${props.error.slice(0, 160)}` : ""}</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {props.onReconnect && (
                <button type="button" onClick={props.onReconnect} className="g5-focusable rounded-full bg-cyan-400 px-3 py-1 font-bold text-slate-900">{t(lang, "shell.reconnect")}</button>
              )}
              <Link to="/docs" className="g5-focusable rounded-full border border-white/15 px-3 py-1 text-white/80">{t(lang, "shell.details_docs")}</Link>
            </div>
          </div>
        )}
      </section>

      {/* Level 3 — result summary */}
      {lastAnswer?.text && !props.taskActive && (
        <section aria-label={t(lang, "shell.result")} className="rounded-[var(--g5-radius-m)] border border-[var(--g5-border)] bg-[var(--g5-carbon)] p-3 text-xs text-white/80">
          <h3 className="font-bold text-white">{t(lang, "shell.result")}</h3>
          <p className="mt-1 line-clamp-4">{lastAnswer.text}</p>
        </section>
      )}

      {/* Adaptive panels: attention target decides order */}
      <div className="grid gap-3 lg:grid-cols-2">
        <div className={presence.attentionTarget === "task" ? "order-1" : "order-2 lg:order-1"}>
          <TaskPanel
            chat={props.chat}
            taskActive={props.taskActive}
            currentTool={props.currentTool ? sanitizeToolText(props.currentTool) : task.tool ? sanitizeToolText(task.tool) : undefined}
            onCancelTask={props.onCancelTask}
            runElapsedMs={runStart === null ? null : now - runStart}
            lang={lang}
          />
          {detailed && <ToolActivity chat={props.chat} lang={lang} />}
          {detailed && <EvidencePanel chat={props.chat} lang={lang} />}
        </div>
        <div className={presence.attentionTarget === "task" ? "order-2 lg:order-2" : "order-1 lg:order-2"}>
          <ResourcePanel telemetry={props.telemetry} compact={!detailed} lang={lang} />
        </div>
      </div>

      {/* Level 4 — technical details, opt-in */}
      <details className="rounded-[var(--g5-radius-m)] border border-[var(--g5-border)] bg-black/30 p-3 text-xs">
        <summary className="g5-focusable cursor-pointer font-bold text-white">
          {t(lang, "shell.details")} {advanced ? `(${t(lang, "shell.advanced_on")})` : `(${t(lang, "shell.opt_in")})`}
        </summary>
        <div className="mt-2 grid gap-3">
          <button
            type="button"
            onClick={() => save({ ...prefs, density: advanced ? "simple" : "advanced" })}
            aria-pressed={advanced}
            className="g5-focusable w-fit rounded-full border border-white/15 px-3 py-1 text-white/80"
          >
            {advanced ? t(lang, "shell.hide_advanced") : t(lang, "shell.show_advanced")}
          </button>
          {(detailed) && <EventStream chat={props.chat} lang={lang} />}
          <p className="font-mono text-[11px] text-white/50">
            presence={presence.semanticState} attention={presence.attentionTarget} intensity={presence.intensity} gesture={presence.gesture}
          </p>
        </div>
      </details>

      <section aria-label={t(lang, "settings")} className="rounded-[var(--g5-radius-m)] border border-[var(--g5-border)] bg-[var(--g5-carbon)] p-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <DensitySettings density={prefs.density} onChange={(density) => save({ ...prefs, density })} lang={lang} />
          <AmbientSettings
            ambient={prefs.ambient}
            reduced={prefs.animation !== "on" || osReduced}
            onAmbient={(ambient) => save({ ...prefs, ambient })}
            onReduced={(v) => save({ ...prefs, animation: v ? "reduced" : "on" })}
            lang={lang}
          />
        </div>
      </section>
    </div>
  );
}
