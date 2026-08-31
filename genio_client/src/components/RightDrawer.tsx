import { AnimatePresence, motion } from "framer-motion";
import {
  ChevronDown,
  MonitorPlay,
  Network,
  Puzzle,
  Radio,
  Square,
  Wrench,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { ChatEvent, TelemetrySnapshot, ToolResultMap } from "../lib/types";

interface Props {
  open: boolean;
  onClose: () => void;
  chat: ChatEvent[];
  screen: string | null;
  streaming: boolean;
  activeHost: string;
  activeLabel: string;
  apiKey?: string;
  telemetry: TelemetrySnapshot | null;
  onRequestScreenshot: () => boolean;
  onToggleScreenStream: (active: boolean) => boolean;
  onSwitchNode: (host: string, label: string) => Promise<boolean>;
}

type DrawerTab = "live" | "tools" | "mcp" | "nodes";

const TABS: { id: DrawerTab; label: string; icon: React.ReactNode }[] = [
  { id: "live", label: "Live", icon: <MonitorPlay size={15} /> },
  { id: "tools", label: "Tools", icon: <Wrench size={15} /> },
  { id: "mcp", label: "MCP", icon: <Puzzle size={15} /> },
  { id: "nodes", label: "Nodes", icon: <Network size={15} /> },
];

export default function RightDrawer({
  open,
  onClose,
  chat,
  screen,
  streaming,
  activeHost,
  activeLabel,
  apiKey,
  telemetry,
  onRequestScreenshot,
  onToggleScreenStream,
  onSwitchNode,
}: Props) {
  const [tab, setTab] = useState<DrawerTab>("live");

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* backdrop on mobile */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm lg:hidden"
          />

          <motion.aside
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 28, stiffness: 300 }}
            className="fixed right-0 top-0 z-50 flex h-full w-full max-w-sm flex-col border-l border-slate-700/40 bg-slate-950/95 backdrop-blur-lg lg:relative lg:w-80 lg:max-w-none"
          >
            {/* tabs */}
            <div className="flex items-center gap-1 border-b border-slate-700/40 px-2 pt-12 pb-0 lg:border-t lg:pt-2">
              {TABS.map((t) => (
                <button
                  key={t.id}
                  onClick={() => setTab(t.id)}
                  className={`flex flex-1 items-center justify-center gap-1.5 rounded-t-lg px-2 py-2.5 text-[11px] font-semibold uppercase tracking-wider transition-all ${
                    tab === t.id
                      ? "bg-neon/10 text-neon border-b-2 border-neon"
                      : "text-slate-500 hover:bg-slate-800/40 hover:text-slate-300"
                  }`}
                >
                  {t.icon}
                  <span className="hidden sm:inline">{t.label}</span>
                </button>
              ))}

              <button
                onClick={onClose}
                className="ml-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-slate-500 transition-colors hover:bg-danger/10 hover:text-rose-400 lg:hidden"
              >
                <X size={16} />
              </button>
            </div>

            {/* content */}
            <div className="flex-1 overflow-y-auto custom-scrollbar p-4">
              {tab === "live" && (
                <LiveViewport
                  screen={screen}
                  streaming={streaming}
                  onRequest={onRequestScreenshot}
                  onToggle={onToggleScreenStream}
                />
              )}
              {tab === "tools" && <ToolInspector chat={chat} />}
              {tab === "mcp" && <MCPPanel />}
              {tab === "nodes" && (
                <NodeWatch
                  activeHost={activeHost}
                  activeLabel={activeLabel}
                  apiKey={apiKey}
                  telemetry={telemetry}
                  onSwitchNode={onSwitchNode}
                />
              )}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

/* ------------------------------------------------------------------ */
/* Live Viewport                                                        */
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
          <img src={`data:image/png;base64,${screen}`} alt="screen" className="h-full w-full object-contain" />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-slate-600">
            <MonitorPlay size={36} strokeWidth={1.2} className="animate-float-y" />
            <p className="text-[11px] font-mono">no frame yet</p>
          </div>
        )}
        {screen && (
          <div className="pointer-events-none absolute inset-0 overflow-hidden">
            <div className="h-px w-full bg-gradient-to-r from-transparent via-neon/60 to-transparent animate-scan" />
          </div>
        )}
        <span className="absolute left-2 top-2 rounded bg-slate-950/70 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-neon backdrop-blur">
          {streaming ? "● STREAM" : "◆ IDLE"} {screen && `· ${kb} KB`}
        </span>
      </div>

      <div className="mt-2 flex gap-2">
        <button onClick={onRequest} className="neon-button flex-1 py-2 text-[11px]">
          <Radio size={12} /> Frame
        </button>
        <button
          onClick={() => onToggle(!streaming)}
          className={`neon-button flex-1 py-2 text-[11px] ${streaming ? "!bg-danger/80 !text-white hover:!shadow-none" : ""}`}
        >
          {streaming ? <><Square size={12} /> Stop</> : <><MonitorPlay size={12} /> Stream</>}
        </button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Tool Inspector                                                       */
/* ------------------------------------------------------------------ */

function ToolInspector({ chat }: { chat: ChatEvent[] }) {
  const runs = useMemo(() => {
    const runs: { id: number; command: string; result?: ToolResultMap }[] = [];
    let open: { id: number; command: string; result?: ToolResultMap } | null = null;
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
  }, [chat]);

  const [openId, setOpenId] = useState<number | null>(null);

  return (
    <div className="space-y-2">
      {runs.length === 0 && (
        <p className="py-8 text-center text-[11px] font-mono text-slate-600">no tool executions yet</p>
      )}
      {runs.map((run) => {
        const ok = run.result?.returncode === 0;
        const active = openId === run.id;
        return (
          <div key={run.id} className="overflow-hidden rounded-lg border border-slate-700/50 bg-slate-950/50">
            <button
              onClick={() => setOpenId(active ? null : run.id)}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-[11px] font-mono transition-colors hover:bg-neon/5"
            >
              <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${run.result ? (ok ? "bg-ok" : "bg-danger") : "bg-amber-400 animate-pulse-slow"}`} />
              <span className="flex-1 truncate text-slate-300">{run.command}</span>
              {run.result?.duration !== undefined && <span className="text-[10px] text-slate-500">{run.result.duration}s</span>}
              <ChevronDown size={12} className={`text-slate-500 transition-transform ${active ? "rotate-180" : ""}`} />
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

/* ------------------------------------------------------------------ */
/* MCP & Plugins                                                        */
/* ------------------------------------------------------------------ */

function MCPPanel() {
  const tools = [
    { name: "bash", desc: "Execute shell commands", active: true },
    { name: "browser", desc: "Headless Chromium browser", active: true },
    { name: "computer", desc: "Screen capture & mouse control", active: true },
    { name: "screen", desc: "Desktop screenshot", active: true },
    { name: "social_post", desc: "Post to social platforms", active: true },
    { name: "api", desc: "REST API calls from specs", active: true },
  ];

  return (
    <div className="space-y-3">
      <h3 className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Server Tools</h3>
      {tools.map((t) => (
        <div key={t.name} className="flex items-center justify-between rounded-lg border border-slate-700/40 bg-slate-950/40 px-3 py-2">
          <div>
            <p className="text-xs font-mono font-bold text-slate-200">{t.name}</p>
            <p className="text-[10px] text-slate-500">{t.desc}</p>
          </div>
          <span className={`rounded-full px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider ${t.active ? "bg-ok/15 text-ok" : "bg-slate-800 text-slate-600"}`}>
            {t.active ? "active" : "off"}
          </span>
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Nodes                                                                */
/* ------------------------------------------------------------------ */

function isNodeTuning(host: string): string {
  return host.trim().toLowerCase().startsWith("tn") ? "pop-os" : "tn";
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
  const [other, setOther] = useState<{ live: boolean; status: TelemetrySnapshot | null }>({ live: false, status: null });
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
    return () => { alive = false; clearInterval(t); ctrl.abort(); };
  }, [otherHost, apiKey]);

  async function switchTo() {
    setSwitching(true);
    await onSwitchNode(otherHost, otherLabel);
    setSwitching(false);
  }

  const nodes = [
    { host: activeHost, label: activeLabel, live: true, status: telemetry, action: null as null },
    { host: otherHost, label: otherLabel, live: other.live, status: other.status, action: switchTo },
  ];

  return (
    <div className="space-y-3">
      {nodes.map((n) => (
        <div key={n.host} className={`rounded-xl border p-3 transition-all ${n.live ? "border-neon/25 bg-neon/5" : "border-danger/20 bg-danger/5"}`}>
          <div className="mb-2 flex items-center justify-between">
            <span className="flex items-center gap-2 text-xs font-bold text-white">
              <Network size={13} className={n.live ? "text-neon" : "text-danger"} />
              {n.label}
              <span className="font-mono text-[10px] text-slate-500">{n.host}</span>
            </span>
            <span className={`rounded-full px-2 py-0.5 text-[9px] font-bold uppercase ${n.live ? "bg-ok/15 text-ok" : "bg-danger/15 text-rose-400"}`}>
              {n.live ? "LIVE" : "OFFLINE"}
            </span>
          </div>
          <div className="grid grid-cols-3 gap-1.5 text-center font-mono text-[10px]">
            <div className="rounded bg-slate-950/60 py-1"><div className="text-slate-500">CPU</div><div className="text-xs font-bold text-neon-soft">{n.status?.cpu_percent?.toFixed(0) ?? "—"}%</div></div>
            <div className="rounded bg-slate-950/60 py-1"><div className="text-slate-500">RAM</div><div className="text-xs font-bold text-neon-soft">{n.status?.ram_used_gb?.toFixed(1) ?? "—"}G</div></div>
            <div className="rounded bg-slate-950/60 py-1"><div className="text-slate-500">MODEL</div><div className="truncate text-[10px] font-bold text-slate-300">{n.status?.model ?? "—"}</div></div>
          </div>
          {n.action && (
            <button onClick={n.action} disabled={!n.live || switching} className="mt-2 w-full neon-button py-1.5 text-[11px]">
              {switching ? "Switching…" : `Switch → ${n.label}`}
            </button>
          )}
        </div>
      ))}
    </div>
  );
}