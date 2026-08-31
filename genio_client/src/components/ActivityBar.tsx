import { RotateCcw, Square } from "lucide-react";
import type { AgentStatus } from "../lib/types";

interface Props {
  agentStatus: AgentStatus;
  onKill: () => void;
  onContinue: () => void;
}

export default function ActivityBar({ agentStatus, onKill, onContinue }: Props) {
  const isActive = agentStatus.kind === "thinking" || agentStatus.kind === "executing";

  return (
    <div className="flex h-10 flex-none items-center justify-between border-t border-slate-700/40 bg-slate-950/60 px-4 backdrop-blur">
      <div className="flex items-center gap-2.5">
        {isActive ? (
          <span className="flex items-center gap-2">
            <span className="relative flex h-2.5 w-2.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-neon opacity-60" />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-neon" />
            </span>
            <span className="text-[11px] font-mono text-neon-soft">
              {agentStatus.kind === "thinking" && "thinking…"}
              {agentStatus.kind === "executing" && (
                <>
                  <span className="text-slate-500">executing</span>{" "}
                  <span className="font-semibold text-amber-300">{agentStatus.tool}</span>
                </>
              )}
            </span>
          </span>
        ) : (
          <span className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-slate-600" />
            <span className="text-[11px] font-mono text-slate-500">idle</span>
          </span>
        )}
      </div>

      <div className="flex items-center gap-2">
        {isActive && (
          <button
            onClick={onKill}
            className="flex items-center gap-1.5 rounded-md border border-danger/40 bg-danger/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-rose-300 transition-all hover:bg-danger/20 hover:shadow-[0_0_12px_rgba(244,63,94,0.25)]"
          >
            <Square size={10} />
            Stop
          </button>
        )}
        {agentStatus.kind === "completed" && (
          <button
            onClick={onContinue}
            className="flex items-center gap-1.5 rounded-md border border-neon/30 bg-neon/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-neon transition-all hover:bg-neon/15 hover:shadow-neon"
          >
            <RotateCcw size={10} />
            Continue
          </button>
        )}
      </div>
    </div>
  );
}
