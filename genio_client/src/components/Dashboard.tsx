import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  Boxes,
  ChevronDown,
  Cpu,
  Copy,
  Gauge,
  LogOut,
  MemoryStick,
  Mic,
  MonitorPlay,
  Network,
  Radio,
  Shield,
  Square,
  Terminal,
  Wifi,
  Wrench,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ToolResultMap } from "../lib/types";
import type { ChatEvent, TelemetrySnapshot } from "../lib/types";
import { startVoiceRecording, stopVoiceRecording } from "../lib/audio";

interface Props {
  node: string;
  host: string;
  apiKey?: string;
  telemetry: TelemetrySnapshot | null;
  chat: ChatEvent[];
  screen: string | null;
  streaming: boolean;
  onDisconnect: () => void;
  onSendPrompt: (text: string) => void;
  onSendVoice: (dataB64: string, durationSec: number) => void;
  onRequestScreenshot: () => boolean;
  onToggleScreenStream: (active: boolean) => boolean;
  onSwitchNode: (host: string, label: string) => Promise<boolean>;
}

function isNodeTuning(host: string): string {
  return host.trim().toLowerCase().startsWith("tn") ? "pop-os" : "tn";
}

export default function Dashboard({
  node,
  host,
  apiKey,
  telemetry,
  chat,
  screen,
  streaming,
  onDisconnect,
  onSendPrompt,
  onSendVoice,
  onRequestScreenshot,
  onToggleScreenStream,
  onSwitchNode,
}: Props) {
  const [tab, setTab] = useState<"live" | "tools" | "nodes">("live");
  const runs = useMemo(() => collectToolRuns(chat), [chat]);

  const cpuPct = telemetry?.cpu_percent;
  const ramUsedG = telemetry?.ram_used_gb;
  const ramTotalG = telemetry?.ram_total_gb;
  const ramPct = telemetry?.ram_percent;
  const gpu = telemetry?.gpu;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.4 }}
      className="w-full max-w-7xl"
    >
      {/* top bar */}
      <motion.header
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="glass-panel mb-6 flex flex-wrap items-center justify-between gap-4 px-6 py-4"
      >
        <div className="flex items-center gap-4">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-900/80 text-neon ring-1 ring-neon/40">
            <Boxes size={22} />
          </div>
          <div>
            <h1 className="font-display text-lg font-bold tracking-tight text-white">
              Control Nexus <span className="text-neon">• {node}</span>
            </h1>
            <p className="flex items-center gap-1.5 text-xs font-mono text-slate-400">
              <Wifi size={12} className="text-ok" />
              ws://{host}:8000{" "}
              <span className="text-slate-600">·</span>{" "}
              {telemetry?.armed === false ? (
                <span className="text-danger">KILL SWITCH — halted</span>
              ) : (
                <>
                  armed &amp; watching
                  {typeof cpuPct === "number" && (
                    <span className="text-slate-600">· CPU {cpuPct.toFixed(0)}%</span>
                  )}
                </>
              )}
            </p>
          </div>
        </div>
        <button
          onClick={onDisconnect}
          className="neon-button !bg-transparent !text-rose-300 ring-1 ring-danger/40 hover:ring-danger/70 hover:!bg-danger/10 hover:!shadow-none"
        >
          <LogOut size={15} />
          Disconnect
        </button>
      </motion.header>

      {/* stat tiles */}
      <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
        {[
          {
            icon: <Cpu size={16} />,
            label: "CPU",
            value: typeof cpuPct === "number" ? `${cpuPct.toFixed(0)}%` : "—",
            sub: telemetry?.hostname ? `🧠 ${telemetry.last_tok_per_s?.toFixed(1) ?? "–"} tok/s` : undefined,
            on: typeof cpuPct === "number",
          },
          {
            icon: <MemoryStick size={16} />,
            label: "RAM",
            value: ramUsedG ? `${ramUsedG.toFixed(1)} GB` : "—",
            sub: ramTotalG ? `of ${ramTotalG.toFixed(1)} GB ${typeof ramPct === "number" ? `· ${ramPct.toFixed(0)}%` : ""}` : undefined,
            on: !!ramUsedG,
          },
          {
            icon: <Activity size={16} />,
            label: "GPU",
            value: gpu && gpu.total_gb ? `${gpu.used_gb?.toFixed(1)} / ${gpu.total_gb.toFixed(0)} GB` : "—",
            sub: gpu?.name && gpu.name !== "unknown" ? gpu.name : telemetry?.model ?? undefined,
            on: !!gpu?.total_gb,
          },
          {
            icon: <Shield size={16} />,
            label: "SAFETY",
            value: telemetry?.armed === false ? "KILLED" : "ARMED",
            sub: telemetry?.mode ?? "autonomous",
            on: telemetry?.armed !== false,
          },
        ].map((tile, i) => (
          <motion.div
            key={tile.label}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.06 * i, duration: 0.35 }}
            className="glass-panel px-5 py-4"
          >
            <div className="mb-2 flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                {tile.icon}
                {tile.label}
              </span>
              <span
                className={`h-2 w-2 rounded-full ${tile.on ? "bg-ok" : "bg-danger"} ${tile.on ? "animate-pulse-slow" : ""}`}
              />
            </div>
            <div className="font-mono text-2xl font-bold text-white">{tile.value}</div>
            {tile.sub && <div className="mt-1 truncate text-[11px] font-mono text-slate-500">{tile.sub}</div>}
          </motion.div>
        ))}
      </div>

      <div className="grid gap-6 lg:h-[36rem] lg:grid-cols-[1fr_26rem]">
        {/* agent transcript */}
        <Transcript chat={chat} />

        {/* right column */}
        <motion.aside
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.35 }}
          className="flex min-h-0 flex-col gap-4"
        >
          <div className="glass-panel flex-none p-5">
            <GenioPrompt onSendPrompt={onSendPrompt} onSendVoice={onSendVoice} />
          </div>

          <div className="glass-panel flex min-h-0 flex-1 flex-col overflow-hidden">
            <div className="flex items-center gap-1 border-b border-slate-700/50 px-3 py-2">
              {(
                [
                  { id: "live", label: "Live View", icon: <MonitorPlay size={15} /> },
                  { id: "tools", label: "Tools", icon: <Wrench size={15} /> },
                  { id: "nodes", label: "Nodes", icon: <Network size={15} /> },
                ] as const
              ).map((t) => (
                <button
                  key={t.id}
                  onClick={() => setTab(t.id)}
                  className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg px-2 py-2 text-xs font-semibold uppercase tracking-wider transition-all duration-150 ${
                    tab === t.id
                      ? "bg-neon/15 text-neon shadow-neon"
                      : "text-slate-500 hover:bg-slate-800/50 hover:text-slate-300"
                  }`}
                >
                  {t.icon}
                  {t.label}
                </button>
              ))}
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar p-4">
              {tab === "live" && (
                <LiveViewport
                  screen={screen}
                  streaming={streaming}
                  onRequest={onRequestScreenshot}
                  onToggle={onToggleScreenStream}
                />
              )}
              {tab === "tools" && <ToolInspector runs={runs} />}
              {tab === "nodes" && (
                <NodeWatch
                  activeHost={host}
                  activeLabel={node}
                  apiKey={apiKey}
                  telemetry={telemetry}
                  onSwitchNode={onSwitchNode}
                />
              )}
            </div>
          </div>
        </motion.aside>
      </div>
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/* Transcript                                                          */
/* ------------------------------------------------------------------ */

function Transcript({ chat }: { chat: ChatEvent[] }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const stickRef = useRef(true);

  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    stickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 140;
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (el && stickRef.current) {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    }
  }, [chat]);

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.12, duration: 0.35 }}
      className="glass-panel flex min-h-0 flex-col"
    >
      <div className="flex flex-none items-center justify-between border-b border-slate-700/50 px-5 py-3">
        <span className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
          <Terminal size={14} className="text-neon" />
          Agent Transcript
        </span>
        <span className="flex items-center gap-1.5 text-[11px] text-slate-600">
          <Gauge size={12} className="text-neon/60" />
          {chat.length} events
        </span>
      </div>

      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="custom-scrollbar flex-1 min-h-0 space-y-3 overflow-y-auto p-5 pr-2 font-mono text-[13px] leading-relaxed"
      >
        {chat.length === 0 && (
          <p className="text-slate-500">
            <span className="text-neon">▍</span> awaiting agent events…
          </p>
        )}
        <AnimatePresence initial={false}>
          {chat.map((event, i) => (
            <motion.div
              key={`${i}-${event.type}`}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.2 }}
              className="flex gap-3"
            >
              <span className="mt-0.5 select-none text-slate-600">[{i}]</span>
              <div className="min-w-0 flex-1">
                {event.type === "answer" && (
                  <p className="whitespace-pre-wrap text-emerald-300">{event.text}</p>
                )}
                {event.type === "thought" && <ThoughtBubble text={event.text} />}
                {event.type === "tool_call" && (
                  <ToolCallBox command={event.command} />
                )}
                {event.type === "tool_result" && (
                  <ToolResultBox result={event.result} />
                )}
                {event.type === "stats" && (
                  <p className="text-slate-500">
                    ⏱ {event.tokens ?? 0} tok · {event.tok_per_s?.toFixed(1) ?? "—"} tok/s
                  </p>
                )}
                {event.type === "error" && (
                  <p className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-rose-300">
                    ✕ {event.message}
                  </p>
                )}
                {event.type === "killed" && (
                  <p className="text-rose-400">✕ KILL SWITCH engaged — run halted</p>
                )}
                {event.type === "armed" && <p className="text-emerald-300">✚ re-armed</p>}
                {event.type === "attached" && (
                  <p className="text-cyan-300">
                    📎 {event.name} → {event.path}
                  </p>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </motion.section>
  );
}

function ThoughtBubble({ text }: { text: string }) {
  const [open, setOpen] = useState(text.length <= 160);
  const short = text.length <= 160;

  return (
    <div className="rounded-xl border border-neon/25 bg-neon/5 px-3 py-2 backdrop-blur">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 text-left text-[11px] font-semibold uppercase tracking-[0.14em] text-neon/90"
      >
        🧠 Thought
        {!short && (
          <ChevronDown
            size={13}
            className={`ml-auto transition-transform duration-200 ${open ? "rotate-180" : ""}`}
          />
        )}
      </button>
      {(open || short) && (
        <p className="mt-1.5 whitespace-pre-wrap text-[12.5px] italic text-neon-soft/90">{text}</p>
      )}
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      /* clipboard unavailable */
    }
  }
  return (
    <button
      onClick={copy}
      className="inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] text-slate-400 transition-colors hover:bg-neon/10 hover:text-neon"
      title="Copy output"
    >
      {copied ? "✓ copied" : <Copy size={11} />}
    </button>
  );
}

function ToolCallBox({ command }: { command: string }) {
  return (
    <div className="rounded-lg border border-amber-500/25 bg-slate-950/60 overflow-hidden">
      <div className="flex items-center justify-between bg-amber-500/10 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-amber-400">
        <span className="flex items-center gap-1.5">⚡ Tool Call</span>
        <CopyButton text={command} />
      </div>
      <pre className="custom-scrollbar max-h-40 overflow-y-auto whitespace-pre-wrap break-all px-3 py-2 text-[12px] text-amber-200/90">
        {command}
      </pre>
    </div>
  );
}

function ToolResultBox({ result }: { result: ToolResultMap }) {
  const pretty = JSON.stringify(result, null, 2);
  return (
    <div className="rounded-lg border border-slate-700/60 bg-slate-950/60 overflow-hidden">
      <div className="flex items-center justify-between bg-slate-800/40 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
        <span className="flex items-center gap-1.5">✓ Tool Output</span>
        <CopyButton text={pretty} />
      </div>
      <div className="px-3 py-2 text-[12px]">
        {typeof result.returncode === "number" && (
          <p className="mb-1 flex items-center gap-2 text-slate-500">
            <span
              className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                result.returncode === 0 ? "bg-ok/15 text-ok" : "bg-danger/15 text-rose-400"
              }`}
            >
              exit {result.returncode}
            </span>
            {typeof result.duration === "number" && (
              <span>⏱ {result.duration}s{result.timed_out ? " · ⚠ timed out" : ""}</span>
            )}
          </p>
        )}
        {typeof result.success === "boolean" && (
          <p className={`mb-1 text-[11px] ${result.success ? "text-ok" : "text-rose-400"}`}>
            {result.success ? "✓ success" : "✕ failed"}
          </p>
        )}
        {result.error && <p className="mb-1 whitespace-pre-wrap break-all text-rose-400">✕ {result.error}</p>}
        {result.stdout ? (
          <pre className="custom-scrollbar max-h-40 overflow-y-auto whitespace-pre-wrap break-all text-slate-300">
            {typeof result.stdout === "string" ? result.stdout : JSON.stringify(result.stdout)}
          </pre>
        ) : null}
        {result.stderr ? (
          <pre className="mt-1 max-h-40 overflow-y-auto whitespace-pre-wrap break-all text-rose-500">
            {typeof result.stderr === "string" ? result.stderr : JSON.stringify(result.stderr)}
          </pre>
        ) : null}
        {!result.stdout && !result.stderr && !result.error && (
          <pre className="custom-scrollbar max-h-40 overflow-y-auto whitespace-pre-wrap break-all text-slate-400">
            {pretty}
          </pre>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Tool runs (inspector input)                                          */
/* ------------------------------------------------------------------ */

interface ToolRun {
  id: number;
  command: string;
  result?: ToolResultMap;
}

function collectToolRuns(chat: ChatEvent[]): ToolRun[] {
  const runs: ToolRun[] = [];
  let open: ToolRun | null = null;
  chat.forEach((ev, i) => {
    if (ev.type === "tool_call") {
      open = { id: i, command: ev.command };
      runs.push(open);
    } else if (ev.type === "tool_result" && open) {
      open.result = ev.result;
      open = null;
    }
  });
  return runs;
}

/* ------------------------------------------------------------------ */
/* Right-panel modules                                                  */
/* ------------------------------------------------------------------ */

function LiveViewport({
  screen,
  streaming,
  onRequest,
  onToggle,
}: {
  screen: string | null;
  streaming: boolean;
  onRequest: () => boolean;
  onToggle: (active: boolean) => boolean;
}) {
  const kb = screen ? Math.round((screen.length * 0.75) / 1024) : 0;

  return (
    <div>
      <div className="relative overflow-hidden rounded-xl border border-slate-700/60 bg-slate-950/80 aspect-video">
        {screen ? (
          <img
            src={`data:image/png;base64,${screen}`}
            alt="screen feed"
            className="h-full w-full object-contain"
          />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-slate-600">
            <MonitorPlay size={40} strokeWidth={1.2} className="animate-float-y" />
            <p className="text-xs font-mono">no frame yet — request one or start streaming</p>
          </div>
        )}
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="h-px w-full bg-gradient-to-r from-transparent via-neon/60 to-transparent animate-scan" />
        </div>
        <span className="absolute left-3 top-3 rounded-md bg-slate-950/70 px-2 py-1 text-[10px] font-bold uppercase tracking-[0.18em] text-neon backdrop-blur">
          ● REC · {kb} KB
        </span>
      </div>

      <div className="mt-3 flex gap-2">
        <button onClick={onRequest} className="neon-button flex-1 py-2 text-xs">
          <Radio size={13} />
          Frame
        </button>
        <button
          onClick={() => onToggle(!streaming)}
          className={`neon-button flex-1 py-2 text-xs ${
            streaming ? "!bg-danger/80 !text-white hover:!shadow-none" : ""
          }`}
        >
          {streaming ? (
            <>
              <Square size={13} />
              Stop Stream
            </>
          ) : (
            <>
              <MonitorPlay size={13} />
              Stream (1 Hz)
            </>
          )}
        </button>
      </div>
    </div>
  );
}

function ToolInspector({ runs }: { runs: ToolRun[] }) {
  const [openId, setOpenId] = useState<number | null>(null);

  return (
    <div className="space-y-2">
      {runs.length === 0 && (
        <p className="py-6 text-center text-xs font-mono text-slate-600">
          no tool executions yet — inspect toolcalls live here
        </p>
      )}
      {runs.map((run) => {
        const ok = run.result?.returncode === 0;
        const active = openId === run.id;
        return (
          <div key={run.id} className="overflow-hidden rounded-lg border border-slate-700/50 bg-slate-950/50">
            <button
              onClick={() => setOpenId(active ? null : run.id)}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs font-mono transition-colors hover:bg-neon/5"
            >
              <span className={`h-1.5 w-1.5 rounded-full shrink-0 ${run.result ? (ok ? "bg-ok" : "bg-danger") : "bg-amber-400 animate-pulse-slow"}`} />
              <span className="flex-1 truncate text-slate-300">{run.command}</span>
              {run.result?.duration !== undefined && (
                <span className="text-[10px] text-slate-500">{run.result.duration}s</span>
              )}
              <ChevronDown size={13} className={`text-slate-500 transition-transform ${active ? "rotate-180" : ""}`} />
            </button>
            {active && run.result && (
              <div className="border-t border-slate-700/40 px-3 py-2 font-mono text-[11px] leading-snug">
                {run.result.error && <p className="text-rose-400">✕ {run.result.error}</p>}
                {run.result.stdout && (
                  <pre className="custom-scrollbar max-h-32 overflow-y-auto whitespace-pre-wrap break-all text-slate-300">{String(run.result.stdout)}</pre>
                )}
                {run.result.stderr && (
                  <pre className="mt-1 max-h-24 overflow-y-auto whitespace-pre-wrap break-all text-rose-500">{String(run.result.stderr)}</pre>
                )}
                {!run.result.stdout && !run.result.stderr && (
                  <pre className="custom-scrollbar max-h-32 overflow-y-auto whitespace-pre-wrap break-all text-slate-400">
                    {JSON.stringify(run.result, null, 2)}
                  </pre>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

interface OtherNode {
  live: boolean;
  status: TelemetrySnapshot | null;
}

function NodeWatch({
  activeHost,
  activeLabel,
  apiKey,
  telemetry,
  onSwitchNode,
}: {
  activeHost: string;
  activeLabel: string;
  apiKey?: string;
  telemetry: TelemetrySnapshot | null;
  onSwitchNode: (host: string, label: string) => Promise<boolean>;
}) {
  const otherHost = isNodeTuning(activeHost);
  const otherLabel = otherHost === "tn" ? "TN VPS" : "Pop!_OS";
  const [other, setOther] = useState<OtherNode>({ live: false, status: null });
  const [switching, setSwitching] = useState(false);

  useEffect(() => {
    let alive = true;
    const ctrl = new AbortController();
    async function check() {
      try {
        const headers: Record<string, string> = { Accept: "application/json" };
        if (apiKey) headers["X-API-Key"] = apiKey;
        const res = await fetch(`http://${otherHost}:8000/api/v1/status`, { headers, signal: ctrl.signal });
        if (!alive) return;
        setOther({ live: res.ok, status: res.ok ? ((await res.json()) as TelemetrySnapshot) : null });
      } catch {
        if (alive) setOther({ live: false, status: null });
      }
    }
    check();
    const t = setInterval(check, 12000);
    return () => {
      alive = false;
      clearInterval(t);
      ctrl.abort();
    };
  }, [otherHost, apiKey]);

  async function switchTo() {
    if (otherHost === activeHost) return;
    setSwitching(true);
    await onSwitchNode(otherHost, otherLabel);
    setSwitching(false);
  }

  const nodes = [
    {
      host: activeHost,
      label: activeLabel,
      live: true,
      blink: telemetry?.armed !== false,
      status: telemetry,
      action: null as null,
    },
    {
      host: otherHost,
      label: otherLabel,
      live: other.live,
      blink: other.live,
      status: other.status,
      action: async () => switchTo(),
    },
  ];

  return (
    <div className="space-y-3">
      {nodes.map((n) => (
        <div
          key={n.host}
          className={`rounded-xl border p-4 transition-all duration-200 ${
            n.live ? "border-neon/30 bg-neon/5" : "border-danger/25 bg-danger/5"
          }`}
        >
          <div className="mb-2 flex items-center justify-between">
            <span className="flex items-center gap-2 text-sm font-bold text-white">
              <Network size={14} className={n.live ? "text-neon" : "text-danger"} />
              {n.label}
              <span className="font-mono text-[10px] text-slate-500">{n.host}</span>
            </span>
            <span
              className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider ${
                n.live ? "bg-ok/15 text-ok" : "bg-danger/15 text-rose-400"
              }`}
            >
              <span className={`h-1.5 w-1.5 rounded-full ${n.live ? "bg-ok" : "bg-danger"} ${n.blink ? "animate-pulse" : ""}`} />
              {n.live ? (n.host === activeHost ? "LIVE" : "REACHABLE") : "OFFLINE"}
            </span>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center font-mono text-[11px]">
            <div className="rounded-lg bg-slate-950/60 py-1.5">
              <div className="text-slate-500">CPU</div>
              <div className={`text-sm font-bold ${n.live ? "text-neon-soft" : "text-slate-600"}`}>
                {typeof n.status?.cpu_percent === "number" ? `${n.status.cpu_percent.toFixed(0)}%` : "—"}
              </div>
            </div>
            <div className="rounded-lg bg-slate-950/60 py-1.5">
              <div className="text-slate-500">RAM</div>
              <div className={`text-sm font-bold ${n.live ? "text-neon-soft" : "text-slate-600"}`}>
                {n.status?.ram_used_gb ? `${n.status.ram_used_gb.toFixed(1)}G` : "—"}
              </div>
            </div>
            <div className="rounded-lg bg-slate-950/60 py-1.5">
              <div className="text-slate-500">MODEL</div>
              <div className="truncate text-sm font-bold text-slate-300">{n.status?.model ?? "—"}</div>
            </div>
          </div>
          {n.action && (
            <button
              onClick={n.action}
              disabled={!n.live || switching}
              className="mt-3 w-full neon-button py-2 text-xs"
            >
              {switching ? "Switching…" : `Switch target → ${n.label}`}
            </button>
          )}
        </div>
      ))}
      <p className="text-center text-[10px] font-mono text-slate-600">
        peer health via http://{otherHost}:8000/api/v1/status · tailscale
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Prompt + Voice                                                       */
/* ------------------------------------------------------------------ */

function GenioPrompt({
  onSendPrompt,
  onSendVoice,
}: {
  onSendPrompt: (text: string) => void;
  onSendVoice: (dataB64: string, durationSec: number) => void;
}) {
  const [value, setValue] = useState("");
  const [recording, setRecording] = useState(false);
  const [recTimer, setRecTimer] = useState(0);

  useEffect(() => {
    if (!recording) {
      setRecTimer(0);
      return;
    }
    const t = setInterval(() => setRecTimer((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [recording]);

  async function toggleMic() {
    if (recording) {
      const audio = await stopVoiceRecording();
      setRecording(false);
      if (audio && audio.dataB64) {
        onSendVoice(audio.dataB64, audio.durationSec);
      }
    } else {
      try {
        await startVoiceRecording();
        setRecording(true);
      } catch {
        setRecording(false);
      }
    }
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const text = value.trim();
        if (!text) return;
        onSendPrompt(text);
        setValue("");
      }}
      className="space-y-3"
    >
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        rows={3}
        placeholder="e.g. open a browser, go to the Genio docs and summarize them…"
        className="neon-input resize-none font-mono text-xs"
      />
      <div className="flex gap-2">
        <button type="submit" disabled={!value.trim()} className="neon-button flex-1">
          Dispatch to Agent
        </button>
        <button
          type="button"
          onClick={toggleMic}
          title={recording ? "Stop and send voice" : "Record voice prompt"}
          className={`relative flex h-11 w-11 shrink-0 items-center justify-center rounded-xl transition-all duration-200 ${
            recording
              ? "bg-danger text-white shadow-neon-lg"
              : "bg-slate-900/80 text-neon ring-1 ring-neon/40 hover:shadow-neon"
          }`}
        >
          {recording && (
            <span className="absolute inset-0 animate-ping rounded-xl bg-danger/40" />
          )}
          {recording ? <Square size={16} /> : <Mic size={16} />}
          {recording && (
            <span className="absolute -top-2 -right-2 rounded-full bg-danger px-1.5 py-0.5 text-[9px] font-bold text-white">
              {recTimer}s
            </span>
          )}
        </button>
      </div>
      {recording && (
        <p className="text-center text-[11px] font-mono text-danger animate-pulse">
          ● recording — hit stop to send via Web Audio
        </p>
      )}
    </form>
  );
}