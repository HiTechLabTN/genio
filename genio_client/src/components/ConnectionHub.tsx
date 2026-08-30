import { motion } from "framer-motion";
import { Braces, Cable, ChevronDown, CloudCog, Radio, Server, Zap } from "lucide-react";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import type { ServerNode } from "../lib/types";

export const NODE_PRESETS: ServerNode[] = [
  { id: "pop", label: "Pop!_OS (Tailscale)", host: "pop-os", port: 8000 },
  { id: "tn", label: "TN Server", host: "tn", port: 8000 },
];

interface Props {
  onConnect: (target: ServerNode) => Promise<boolean>;
}

export default function ConnectionHub({ onConnect }: Props) {
  const [nodeId, setNodeId] = useState<string>("pop");
  const [host, setHost] = useState<string>("pop-os");
  const [port, setPort] = useState<string>("8000");
  const [key, setKey] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isCustom = nodeId === "custom";

  useEffect(() => {
    if (nodeId === "custom") return;
    const preset = NODE_PRESETS.find((n) => n.id === nodeId);
    if (preset) {
      setHost(preset.host);
      setPort(String(preset.port));
    }
  }, [nodeId]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    const target: ServerNode = {
      id: nodeId,
      label: NODE_PRESETS.find((n) => n.id === nodeId)?.label ?? "Custom",
      host: host.trim(),
      port: parseInt(port, 10) || 8000,
      key: key.trim() || undefined,
    };
    const ok = await onConnect(target);
    setBusy(false);
    if (!ok) setError("Connection refused — is the Genio daemon running on that node?");
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 24, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
      className="relative w-full max-w-xl"
    >
      {/* ambient glow */}
      <div className="pointer-events-none absolute -inset-10 -z-10">
        <div className="absolute left-1/4 top-0 h-64 w-64 rounded-full bg-neon/20 blur-[100px]" />
        <div className="absolute bottom-0 right-1/4 h-64 w-64 rounded-full bg-neon-deep/30 blur-[100px]" />
      </div>

      <div className="glass-panel overflow-hidden">
        {/* header */}
        <div className="relative border-b border-slate-700/50 bg-gradient-to-r from-neon-deep/20 via-transparent to-transparent px-8 pb-5 pt-7">
          <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-neon/70 to-transparent" />
          <div className="flex items-center gap-4">
            <div className="relative">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-900/80 text-neon ring-1 ring-neon/40 shadow-neon">
                <Zap size={28} strokeWidth={1.8} />
              </div>
              <span className="absolute -right-1 -top-1 flex h-3 w-3">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-neon opacity-60" />
                <span className="relative inline-flex h-3 w-3 rounded-full bg-neon" />
              </span>
            </div>
            <div>
              <h1 className="font-display text-2xl font-bold tracking-tight text-white">
                GENIO <span className="text-neon">v2.0</span>
              </h1>
              <p className="mt-0.5 flex items-center gap-1.5 text-sm text-slate-400">
                <CloudCog size={14} className="text-neon/70" />
                Autonomous AI Orchestrator — Control Nexus
              </p>
            </div>
          </div>
        </div>

        {/* form body */}
        <form onSubmit={submit} className="space-y-6 px-8 py-7">
          <div>
            <label className="neon-label" htmlFor="node">
              Compute Node
            </label>
            <div className="relative">
              <Server size={16} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-neon/70" />
              <select
                id="node"
                value={nodeId}
                onChange={(e) => setNodeId(e.target.value)}
                className="neon-input appearance-none pl-11 pr-10 text-slate-100"
              >
                {NODE_PRESETS.map((n) => (
                  <option key={n.id} value={n.id}>
                    {n.label}
                  </option>
                ))}
                <option value="custom">Custom</option>
              </select>
              <ChevronDown size={16} className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-slate-500" />
            </div>
          </div>

          <div className="grid grid-cols-[1fr_7rem] gap-4">
            <div>
              <label className="neon-label" htmlFor="host">
                Host / IP
              </label>
              <input
                id="host"
                value={host}
                onChange={(e) => setHost(e.target.value)}
                placeholder={isCustom ? "tn / 192.168.1.20 / pop-os" : "tailscale hostname"}
                className="neon-input font-mono"
                spellCheck={false}
              />
            </div>
            <div>
              <label className="neon-label" htmlFor="port">
                Port
              </label>
              <input
                id="port"
                value={port}
                onChange={(e) => setPort(e.target.value.replace(/[^0-9]/g, ""))}
                inputMode="numeric"
                className="neon-input font-mono text-center"
              />
            </div>
          </div>

          <div>
            <label className="neon-label" htmlFor="key">
              API Key <span className="normal-case text-slate-500">(optional)</span>
            </label>
            <div className="relative">
              <Braces size={16} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-neon/70" />
              <input
                id="key"
                type="password"
                value={key}
                onChange={(e) => setKey(e.target.value)}
                placeholder="X-API-Key — leave empty for open nodes"
                className="neon-input pl-11 font-mono"
              />
            </div>
          </div>

          {error && (
            <motion.p
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              className="rounded-lg border border-danger/30 bg-danger/10 px-4 py-2.5 text-sm text-rose-300"
            >
              {error}
            </motion.p>
          )}

          <motion.button
            type="submit"
            disabled={busy || !host.trim()}
            whileTap={{ scale: 0.98 }}
            whileHover={{ scale: 1.02 }}
            className="neon-button w-full py-3.5 text-base"
          >
            {busy ? (
              <>
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-950/30 border-t-slate-950" />
                Handshaking…
              </>
            ) : (
              <>
                <Radio size={18} />
                Connect to Genio Node
              </>
            )}
          </motion.button>
        </form>

        {/* footer */}
        <div className="border-t border-slate-700/50 bg-slate-950/40 px-8 py-3.5">
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-slate-400">
            <span className="flex items-center gap-1.5">
              <Cable size={13} className="text-neon/70" />
              ws://&lt;host&gt;:&lt;port&gt;/ws/agent
            </span>
            <span className="flex items-center gap-1.5">
              <Radio size={13} className="text-ok/70" />
              telemetry · chat · exec · kill-switch
            </span>
          </div>
        </div>
      </div>
    </motion.div>
  );
}