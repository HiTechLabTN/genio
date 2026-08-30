import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  Boxes,
  Cpu,
  Gauge,
  LogOut,
  MemoryStick,
  Shield,
  Sparkles,
  Terminal,
  Wifi,
} from "lucide-react";
import { useState } from "react";
import type { ChatEvent, TelemetrySnapshot } from "../lib/types";

interface Props {
  node: string;
  host: string;
  telemetry: TelemetrySnapshot | null;
  chat: ChatEvent[];
  onDisconnect: () => void;
  onSendPrompt: (text: string) => void;
}

function fmtBytes(bytes?: number): string {
  if (bytes === undefined) return "—";
  const gb = bytes / 1024 ** 3;
  return `${gb.toFixed(1)} GB`;
}

export default function Dashboard({ node, host, telemetry, chat, onDisconnect, onSendPrompt }: Props) {
  const gpu = telemetry?.gpu;
  const cpu = telemetry?.cpu;
  const ram = telemetry?.ram;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.4 }}
      className="w-full max-w-6xl"
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
            <p className="flex items-center gap-1.5 text-xs text-slate-400 font-mono">
              <Wifi size={12} className="text-ok" />
              ws://{host}:8000 <span className="text-slate-600">·</span> armed &amp; watching
            </p>
          </div>
        </div>
        <button onClick={onDisconnect} className="neon-button !bg-transparent !text-rose-300 ring-1 ring-danger/40 hover:ring-danger/70 hover:!bg-danger/10 hover:!shadow-none">
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
            value: cpu ? `${cpu.percent?.toFixed(0) ?? "—"}%` : "—",
            sub: cpu?.temp_c ? `${cpu.temp_c.toFixed(0)}°C` : undefined,
            on: !!cpu,
          },
          {
            icon: <MemoryStick size={16} />,
            label: "RAM",
            value: ram ? fmtBytes(ram.used_bytes) : "—",
            sub: ram ? `of ${fmtBytes(ram.total_bytes)}` : undefined,
            on: !!ram,
          },
          {
            icon: <Activity size={16} />,
            label: "GPU",
            value: gpu ? `${gpu.used_gb?.toFixed(1)} GB` : "—",
            sub: gpu ? `${gpu.name} · ${gpu.total_gb?.toFixed(0)} GB` : undefined,
            on: !!gpu,
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
            transition={{ delay: 0.08 * i, duration: 0.35 }}
            className="glass-panel px-5 py-4"
          >
            <div className="mb-2 flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                {tile.icon}
                {tile.label}
              </span>
              <span className={`h-2 w-2 rounded-full ${tile.on ? "bg-ok" : "bg-danger"} ${tile.on ? "animate-pulse-slow" : ""}`} />
            </div>
            <div className="font-mono text-2xl font-bold text-white">{tile.value}</div>
            {tile.sub && <div className="mt-1 truncate text-[11px] text-slate-500 font-mono">{tile.sub}</div>}
          </motion.div>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_24rem]">
        {/* agent transcript */}
        <motion.section
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.28, duration: 0.35 }}
          className="glass-panel flex min-h-[24rem] flex-col overflow-hidden"
        >
          <div className="flex items-center justify-between border-b border-slate-700/50 px-5 py-3">
            <span className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
              <Terminal size={14} className="text-neon" />
              Agent Transcript
            </span>
            <Gauge size={14} className="text-slate-600" />
          </div>
          <div className="flex-1 space-y-3 overflow-y-auto p-5 font-mono text-[13px] leading-relaxed">
            {chat.length === 0 && (
              <p className="text-slate-500">
                <span className="text-neon">▍</span> awaiting agent events…
              </p>
            )}
            <AnimatePresence initial={false}>
              {chat.map((event, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.25 }}
                  className="flex gap-3"
                >
                  <span className="mt-0.5 select-none text-slate-600">[{i}]</span>
                  <div className="min-w-0 flex-1">
                    {event.type === "answer" && <p className="whitespace-pre-wrap text-emerald-300">{event.text}</p>}
                    {event.type === "thought" && <p className="italic text-neon-soft/90">{event.text}</p>}
                    {event.type === "tool_call" && (
                      <p className="text-amber-300">
                        <span className="text-slate-500">→ tool</span> {event.command}
                      </p>
                    )}
                    {event.type === "tool_result" && (
                      <p className="text-slate-400">{JSON.stringify(event.result)?.slice(0, 140)}</p>
                    )}
                    {event.type === "stats" && (
                      <p className="text-slate-500">
                        {event.tokens ?? 0} tok · {event.tok_per_s?.toFixed(1) ?? "—"} tok/s
                      </p>
                    )}
                    {event.type === "error" && <p className="text-rose-400">{event.message}</p>}
                    {event.type === "killed" && <p className="text-rose-400">✕ KILL SWITCH engaged — run halted</p>}
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

        {/* command deck */}
        <motion.aside
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.36, duration: 0.35 }}
          className="flex flex-col gap-4"
        >
          <div className="glass-panel p-5">
            <h2 className="neon-label">Prompt Agent</h2>
            <GenioPrompt onSendPrompt={onSendPrompt} />
          </div>
          <div className="glass-panel p-5">
            <h2 className="neon-label flex items-center gap-1.5">
              <Sparkles size={13} />
              Upcoming Modules
            </h2>
            <ul className="space-y-2 text-sm text-slate-400">
              {["Browser / Screen live view", "Toolcall inspector", "Voice I/O", "Multi-node orchestrator"].map((m) => (
                <li key={m} className="flex items-center gap-2">
                  <span className="h-1.5 w-1.5 rounded-sm bg-neon/50" />
                  {m}
                </li>
              ))}
            </ul>
          </div>
        </motion.aside>
      </div>
    </motion.div>
  );
}

function GenioPrompt({ onSendPrompt }: { onSendPrompt: (text: string) => void }) {
  const [value, setValue] = useState("");

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
      <button type="submit" disabled={!value.trim()} className="neon-button w-full">
        Dispatch to Agent
      </button>
    </form>
  );
}