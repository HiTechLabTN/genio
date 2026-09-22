import type { AgentStatus, ChatEvent, TelemetrySnapshot } from "../../lib/types";

/** Phase 4 v2.1 — Holographic HUD widget bar rendered when the agent is busy.
 *
 * Left pane: live multi-step Task Matrix (completed / pending tools).
 * Right pane: real-time telemetry gauges + artifact/code preview.
 */

export function HolographicHud({
  chat,
  agentStatus,
  telemetry,
}: {
  chat: ChatEvent[];
  agentStatus: AgentStatus;
  telemetry: TelemetrySnapshot | null;
}) {
  const busy = agentStatus.kind === "thinking" || agentStatus.kind === "executing";
  if (!busy) return null;

  const done = chat.filter((e) => e.type === "tool_result").length;
  const calls = chat.filter((e) => e.type === "tool_call").length;
  const next = Math.max(calls - done, 0);

  return (
    <div className="pointer-events-auto grid grid-cols-1 gap-3 px-4 pb-3 md:grid-cols-2">
      {/* Left: Task Matrix */}
      <TaskMatrix chat={chat} done={done} calls={calls} next={next} />
      {/* Right: Telemetry & Artifacts */}
      <TelemetryPane telemetry={telemetry} agentStatus={agentStatus} />
    </div>
  );
}

function TaskMatrix({
  chat,
  done,
  calls,
  next,
}: {
  chat: ChatEvent[];
  done: number;
  calls: number;
  next: number;
}) {
  const recent = chat.filter((e) => e.type === "tool_call" || e.type === "tool_result").slice(-12);
  return (
    <div className="rounded-2xl border border-neon/20 bg-carbon/70 p-3 backdrop-blur-md shadow-panel">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-widest text-neon/80">Task Matrix</span>
        <span className="font-mono text-[10px] text-slate-500">
          {done}/{calls} done · {next} pending
        </span>
      </div>
      <ul className="space-y-1 font-mono text-[11px]">
        {recent.map((e, i) => {
          const isResult = e.type === "tool_result";
          const text = isResult
            ? shortResult(e.result)
            : `${e.command?.slice(0, 60) ?? ""}`;
          return (
            <li key={`${i}-${e.type}`} className="flex items-center gap-2">
              {isResult ? (
                <span className="text-ok">▣</span>
              ) : (
                <span className="animate-pulse text-neon">◭</span>
              )}
              <span className={`truncate ${isResult ? "text-slate-500" : "text-slate-300"}`}>
                {text}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function shortResult(result: { stdout?: string; returncode?: number; [k: string]: unknown }): string {
  const out = (result.stdout ?? result.output ?? "done").toString();
  const ok = (result.returncode ?? 0) === 0;
  return `${ok ? "ok" : "FAIL"} · ${out.replace(/\s+/g, " ").slice(0, 48)}`;
}

function TelemetryPane({
  telemetry,
  agentStatus,
}: {
  telemetry: TelemetrySnapshot | null;
  agentStatus: AgentStatus;
}) {
  const cpu = telemetry?.cpu_percent ?? 0;
  const ram = telemetry?.ram_percent ?? 0;
  const vram = telemetry?.gpu?.vram_pct ?? 0;
  const tps = telemetry?.last_tok_per_s ?? 0;
  const runner = agentStatus.kind === "executing" ? agentStatus.tool : "thinking";

  return (
    <div className="rounded-2xl border border-neon/20 bg-carbon/70 p-3 backdrop-blur-md shadow-panel">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-widest text-neon/80">Telemetry</span>
        <span className="font-mono text-[10px] text-slate-500">busy · {runner}</span>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Gauge label="CPU" value={cpu} color="neon" />
        <Gauge label="RAM" value={ram} color="fuchsia" />
        <Gauge label="GPU" value={vram} color="violet" />
        <Gauge label="tokens/s" value={tps} color="ok" max={120} />
      </div>
    </div>
  );
}

function Gauge({
  label,
  value,
  color,
  max = 100,
}: {
  label: string;
  value: number;
  color: "neon" | "fuchsia" | "violet" | "ok";
  max?: number;
}) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const map: Record<string, string> = {
    neon: "bg-neon text-neon",
    fuchsia: "bg-fuchsia-400 text-fuchsia-400",
    violet: "bg-violet-400 text-violet-400",
    ok: "bg-ok text-ok",
  };
  const cls = map[color];
  return (
    <div className="rounded-xl border border-slate-700/40 bg-slate-950/50 p-2">
      <div className="mb-1 flex justify-between font-mono text-[10px] text-slate-500">
        <span>{label}</span>
        <span className={cls ?? "text-neon"}>{value.toFixed(label === "tokens/s" ? 1 : 0)}</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
        <div
          className={`h-full rounded-full ${color === "neon" ? "bg-neon" : color === "ok" ? "bg-ok" : "bg-fuchsia-500"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}