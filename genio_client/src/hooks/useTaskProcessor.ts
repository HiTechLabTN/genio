import { useEffect, useMemo, useState } from "react";
import type { AgentStatus, ChatEvent, TelemetrySnapshot } from "../lib/types";

/**
 * useTaskProcessor — dérive l'état du Chronos Portal des VRAIS événements WS/SSE.
 * Aucune simulation : thinkingSteps vient de `thought`, toolActivity de
 * `tool_call`/`tool_result`, metrics du SSE /api/v1/telemetry + stats,
 * result de `answer`, error de `error`/`killed`.
 * Les types WS inconnus (Phase 6) sont ignorés silencieusement.
 */

export interface TaskMetrics {
  cpu: number;
  gpu: number;
  ram: { used: number; total: number };
  vram: { used: number; total: number };
}

export interface TaskProcessorState {
  isMinimized: boolean;
  setIsMinimized: (v: boolean) => void;
  thinkingSteps: string[];
  toolActivity: string[];
  metrics: TaskMetrics;
  result: string;
  error: string | null;
  isProcessing: boolean;
}

export function useTaskProcessor({
  chat,
  telemetry,
  agentStatus,
}: {
  chat: ChatEvent[];
  telemetry: TelemetrySnapshot | null;
  agentStatus: AgentStatus;
}): TaskProcessorState {
  const [isMinimized, setIsMinimized] = useState(false);

  const thinkingSteps = useMemo(() => {
    // Only real thought events — unknown types ignored
    return chat
      .filter((e) => (e as ChatEvent).type === "thought")
      .map((e) => (e as { text: string }).text)
      .filter((t): t is string => typeof t === "string" && t.trim().length > 0);
  }, [chat]);

  const toolActivity = useMemo(() => {
    const out: string[] = [];
    for (const e of chat) {
      const t = (e as ChatEvent).type;
      if (t === "tool_call") {
        const cmd = (e as { command: string }).command ?? "";
        // Truncate long commands for HUD line
        const short = cmd.length > 80 ? cmd.slice(0, 80) + "…" : cmd;
        out.push(`▶ ${short || "tool"}`);
      } else if (t === "tool_result") {
        const res = (e as { result?: { returncode?: number; stdout?: string; stderr?: string; error?: string } }).result;
        if (res) {
          if (res.error) out.push(`✕ ${String(res.error).slice(0, 80)}`);
          else if (typeof res.returncode === "number" && res.returncode !== 0) {
            const err = (res.stderr ?? res.stdout ?? "").slice(0, 60);
            out.push(`✕ exit ${res.returncode}${err ? `: ${err}` : ""}`);
          } else {
            const rc = res.returncode ?? 0;
            out.push(`✓ done (exit ${rc})`);
          }
        } else {
          out.push("✓ done");
        }
      }
      // Unknown types (Phase 6 tolerant) are silently ignored here as required
    }
    return out;
  }, [chat]);

  const metrics: TaskMetrics = useMemo(() => {
    // Real telemetry only — SSE /api/v1/telemetry already
    // provides cpu_percent, gpu, ram_used_gb etc. Stats tok_per_s could be
    // merged but the HUD expects cpu/gpu/ram/vram, so we map those.
    const cpu = typeof telemetry?.cpu_percent === "number" ? telemetry.cpu_percent : 0;
    let gpu = 0;
    if (telemetry?.gpu) {
      if (typeof (telemetry.gpu as { vram_pct?: number }).vram_pct === "number") {
        gpu = (telemetry.gpu as { vram_pct: number }).vram_pct;
      } else if (
        typeof (telemetry.gpu as { used_gb?: number }).used_gb === "number" &&
        typeof (telemetry.gpu as { total_gb?: number }).total_gb === "number" &&
        (telemetry.gpu as { total_gb: number }).total_gb > 0
      ) {
        gpu = ((telemetry.gpu as { used_gb: number }).used_gb / (telemetry.gpu as { total_gb: number }).total_gb) * 100;
      }
    }
    const ramUsed = typeof telemetry?.ram_used_gb === "number" ? telemetry.ram_used_gb : 0;
    const ramTotal = typeof telemetry?.ram_total_gb === "number" ? telemetry.ram_total_gb : 16;
    const vramUsed = typeof telemetry?.gpu?.used_gb === "number" ? telemetry.gpu.used_gb : 0;
    const vramTotal = typeof telemetry?.gpu?.total_gb === "number" ? telemetry.gpu.total_gb : 8;
    return {
      cpu: Math.round(cpu * 10) / 10,
      gpu: Math.round(gpu * 10) / 10,
      ram: { used: Math.round(ramUsed * 10) / 10, total: ramTotal },
      vram: { used: Math.round(vramUsed * 10) / 10, total: vramTotal },
    };
  }, [telemetry]);

  const result = useMemo(() => {
    // Last answer event is the real result
    for (let i = chat.length - 1; i >= 0; i--) {
      const e = chat[i] as ChatEvent;
      if (e.type === "answer" && typeof (e as { text: string }).text === "string") {
        return (e as { text: string }).text;
      }
    }
    return "";
  }, [chat]);

  const error = useMemo(() => {
    for (let i = chat.length - 1; i >= 0; i--) {
      const e = chat[i] as ChatEvent;
      if (e.type === "error" && typeof (e as { message: string }).message === "string") {
        return (e as { message: string }).message;
      }
      if ((e as ChatEvent).type === "killed") {
        return "KILL SWITCH — run halted";
      }
    }
    return null;
  }, [chat]);

  const isProcessing = agentStatus.kind === "thinking" || agentStatus.kind === "executing";

  // Auto-expand when a new run starts; do not auto-minimize on completion
  // (user controls minimize, but we ensure portal is visible during processing)
  useEffect(() => {
    if (isProcessing) setIsMinimized(false);
  }, [isProcessing]);

  return { isMinimized, setIsMinimized, thinkingSteps, toolActivity, metrics, result, error, isProcessing };
}
