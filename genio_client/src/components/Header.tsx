import { motion } from "framer-motion";
import {
  Activity,
  Cpu,
  LogOut,
  MemoryStick,
  Menu,
  Power,
  Shield,
  Zap,
} from "lucide-react";
import type { AgentStatus, TelemetrySnapshot } from "../lib/types";

interface Props {
  node: string;
  host: string;
  telemetry: TelemetrySnapshot | null;
  agentStatus: AgentStatus;
  onKill: () => void;
  onDisconnect: () => void;
  onToggleDrawer: () => void;
}

export default function Header({
  node,
  host,
  telemetry,
  agentStatus,
  onKill,
  onDisconnect,
  onToggleDrawer,
}: Props) {
  const cpu = telemetry?.cpu_percent;
  const ram = telemetry?.ram_used_gb;
  const ramT = telemetry?.ram_total_gb;
  const gpu = telemetry?.gpu;
  const isKilled = telemetry?.armed === false;

  return (
    <motion.header
      initial={{ opacity: 0, y: -12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="flex h-[52px] flex-none items-center justify-between border-b border-slate-700/40 bg-slate-950/80 px-4 backdrop-blur-lg"
    >
      <div className="flex items-center gap-3">
        <button
          onClick={onToggleDrawer}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-neon/10 hover:text-neon"
          title="Toggle drawer"
        >
          <Menu size={18} />
        </button>

        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-neon/15 text-neon">
            <Zap size={14} strokeWidth={2.5} />
          </div>
          <span className="font-display text-sm font-bold tracking-tight text-white">
            GENIO
          </span>
        </div>

        <div className="hidden items-center gap-2 sm:flex">
          <MetricChip icon={<Cpu size={12} />} label="CPU" value={cpu != null ? `${cpu.toFixed(0)}%` : null} ok={cpu != null} />
          <MetricChip
            icon={<MemoryStick size={12} />}
            label="RAM"
            value={ram != null && ramT != null ? `${ram.toFixed(1)}/${ramT.toFixed(0)} GB` : null}
            ok={ram != null}
          />
          <MetricChip
            icon={<Activity size={12} />}
            label={gpu?.name?.replace(/NVIDIA\s*/i, "").slice(0, 10) ?? "GPU"}
            value={gpu?.total_gb ? `${gpu.used_gb?.toFixed(1)}/${gpu.total_gb.toFixed(0)} GB` : null}
            ok={!!gpu?.total_gb}
          />
          <MetricChip
            icon={isKilled ? <Shield size={12} /> : <Zap size={12} />}
            label={isKilled ? "KILLED" : "ARMED"}
            value={null}
            ok={!isKilled}
            accent={isKilled ? "danger" : "ok"}
          />
        </div>

        <div className="ml-2 hidden rounded-full bg-slate-900/60 px-2.5 py-1 text-[10px] font-mono text-slate-500 lg:block">
          {node} · {host}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <AgentStatusBadge status={agentStatus} />
        {agentStatus.kind === "executing" || agentStatus.kind === "thinking" ? (
          <button
            onClick={onKill}
            className="flex h-8 items-center gap-1.5 rounded-lg border border-danger/40 bg-danger/10 px-3 text-[11px] font-bold uppercase tracking-wider text-rose-300 transition-all hover:bg-danger/20 hover:shadow-[0_0_16px_rgba(244,63,94,0.3)]"
          >
            <Power size={12} />
            Stop
          </button>
        ) : null}
        <button
          onClick={onDisconnect}
          title="Disconnect"
          className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 transition-colors hover:bg-danger/10 hover:text-rose-400"
        >
          <LogOut size={16} />
        </button>
      </div>
    </motion.header>
  );
}

function MetricChip({
  icon,
  label,
  value,
  ok,
  accent,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | null;
  ok: boolean;
  accent?: "ok" | "danger" | "neon";
}) {
  const base = accent === "danger"
    ? "border-danger/30 bg-danger/10 text-rose-300"
    : accent === "ok"
    ? "border-ok/30 bg-ok/10 text-emerald-300"
    : ok
    ? "border-neon/25 bg-neon/5 text-neon-soft"
    : "border-slate-700/40 bg-slate-900/50 text-slate-500";

  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-mono ${base}`}>
      {icon}
      {value ? (
        <>
          <span className="opacity-60">{label}</span>
          <span className="font-bold">{value}</span>
        </>
      ) : (
        <span className="font-bold">{label}</span>
      )}
    </span>
  );
}

function AgentStatusBadge({ status }: { status: AgentStatus }) {
  if (status.kind === "idle") return null;
  return (
    <motion.span
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider ${
        status.kind === "thinking"
          ? "border-neon/40 bg-neon/15 text-neon animate-pulse-slow"
          : status.kind === "executing"
          ? "border-amber-400/40 bg-amber-400/15 text-amber-300 animate-pulse-slow"
          : "border-ok/40 bg-ok/15 text-emerald-300"
      }`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {status.kind === "thinking" && "Thinking…"}
      {status.kind === "executing" && `Exec: ${status.tool}`}
      {status.kind === "completed" && "Completed"}
    </motion.span>
  );
}
