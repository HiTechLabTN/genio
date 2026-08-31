import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, ChevronUp, RotateCcw, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { AgentStatus, ChatEvent } from "../lib/types";

interface Props {
  chat: ChatEvent[];
  agentStatus: AgentStatus;
  onKill: () => void;
  onContinue: () => void;
}

interface ConsoleLine {
  kind: "thought" | "tool" | "result" | "system";
  text: string;
}

function buildConsoleLines(chat: ChatEvent[]): ConsoleLine[] {
  const lines: ConsoleLine[] = [];
  for (const ev of chat) {
    if (ev.type === "thought" && ev.text) {
      lines.push({ kind: "thought", text: ev.text });
    } else if (ev.type === "tool_call" && ev.command) {
      lines.push({ kind: "tool", text: ev.command });
    } else if (ev.type === "tool_result") {
      const out = (ev.result.stdout ?? ev.result.output ?? ev.result.stderr ?? ev.result.error ?? "").toString();
      if (out) lines.push({ kind: "result", text: out.trimEnd() });
    } else if (ev.type === "killed") {
      lines.push({ kind: "system", text: "— KILL SWITCH — run halted" });
    } else if (ev.type === "armed") {
      lines.push({ kind: "system", text: "— re-armed" });
    }
  }
  return lines;
}

export default function ActivityBar({ chat, agentStatus, onKill, onContinue }: Props) {
  const [expanded, setExpanded] = useState(false);
  const lines = useRef(buildConsoleLines(chat));
  lines.current = buildConsoleLines(chat);

  const isActive = agentStatus.kind === "thinking" || agentStatus.kind === "executing";
  const logRef = useRef<HTMLPreElement>(null);

  const [elapsed, setElapsed] = useState(0);
  const activeStartRef = useRef<number | null>(null);

  // Live elapsed timer — proves the UI thread is alive while the agent works.
  useEffect(() => {
    if (isActive) {
      activeStartRef.current = Date.now();
      setElapsed(0);
      const id = window.setInterval(() => {
        if (activeStartRef.current) {
          setElapsed((Date.now() - activeStartRef.current) / 1000);
        }
      }, 100);
      return () => window.clearInterval(id);
    }
    activeStartRef.current = null;
    setElapsed(0);
    return undefined;
  }, [isActive]);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [expanded, lines.current.length]);

  return (
    <div className="flex flex-none flex-col border-t border-slate-700/40 bg-slate-950/60 backdrop-blur">
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 224, opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: "easeInOut" }}
            className="overflow-hidden border-b border-slate-700/40"
          >
            <pre
              ref={logRef}
              className="custom-scrollbar h-full overflow-y-auto bg-slate-950 p-3 font-mono text-[11px] leading-relaxed"
            >
              {lines.current.length === 0 ? (
                <span className="text-slate-600">// agent console — thoughts and tool output will stream here</span>
              ) : (
                lines.current.map((ln, i) => (
                  <div key={i} className="whitespace-pre-wrap break-words">
                    {ln.kind === "thought" && (
                      <span className="text-cyan-300">
                        <span className="text-slate-600">/* thinking */ </span>
                        {ln.text}
                      </span>
                    )}
                    {ln.kind === "tool" && (
                      <span className="text-amber-300">
                        <span className="text-slate-600">$ </span>
                        {ln.text}
                      </span>
                    )}
                    {ln.kind === "result" && <span className="text-emerald-300">{ln.text}</span>}
                    {ln.kind === "system" && <span className="text-rose-400">{ln.text}</span>}
                  </div>
                ))
              )}
            </pre>
          </motion.div>
        )}
      </AnimatePresence>

      <button
        onClick={() => setExpanded((o) => !o)}
        className="flex h-10 w-full items-center justify-between gap-2 px-4 text-left"
        aria-expanded={expanded}
        title={expanded ? "Collapse console" : "Expand activity console"}
      >
        <div className="flex min-w-0 flex-1 items-center gap-2.5">
          {isActive ? (
            <span className="flex items-center gap-2">
              <span className="relative flex h-2.5 w-2.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-neon opacity-60" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-neon" />
              </span>
              <span className="text-[11px] font-mono text-neon-soft">
                {agentStatus.kind === "thinking" && (
                  <>thinking… <span className="font-bold text-neon">{elapsed.toFixed(1)}s</span></>
                )}
                {agentStatus.kind === "executing" && (
                  <>
                    <span className="text-slate-500">executing</span>{" "}
                    <span className="font-semibold text-amber-300">{agentStatus.tool}</span>{" "}
                    <span className="font-bold text-neon">{elapsed.toFixed(1)}s</span>
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

          <span className="ml-1 truncate font-mono text-[10px] text-slate-600">
            {lines.current.length > 0 && `— ${lines.current.slice(-1)[0]?.text.slice(0, 40)}`}
          </span>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {isActive && (
            <span
              onClick={(e) => {
                e.stopPropagation();
                onKill();
              }}
              className="flex cursor-pointer items-center gap-1.5 rounded-md border border-danger/40 bg-danger/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-rose-300 transition-all hover:bg-danger/20 hover:shadow-[0_0_12px_rgba(244,63,94,0.25)]"
            >
              <Square size={10} />
              Stop
            </span>
          )}
          {agentStatus.kind === "completed" && (
            <span
              onClick={(e) => {
                e.stopPropagation();
                onContinue();
              }}
              className="flex cursor-pointer items-center gap-1.5 rounded-md border border-neon/30 bg-neon/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-neon transition-all hover:bg-neon/15 hover:shadow-neon"
            >
              <RotateCcw size={10} />
              Continue
            </span>
          )}
          <span className="ml-1 rounded-md border border-slate-700/40 bg-slate-900/60 p-1 text-slate-400">
            {expanded ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
          </span>
        </div>
      </button>
    </div>
  );
}
