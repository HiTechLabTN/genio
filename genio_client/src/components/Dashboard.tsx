import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useRef, useState } from "react";
import ActivityBar from "./ActivityBar";
import BottomInputBar from "./BottomInputBar";
import Header from "./Header";
import RightDrawer from "./RightDrawer";
import type { AgentStatus, ChatEvent, TelemetrySnapshot, ToolResultMap } from "../lib/types";

interface Props {
  node: string;
  host: string;
  apiKey?: string;
  telemetry: TelemetrySnapshot | null;
  agentStatus: AgentStatus;
  chat: ChatEvent[];
  screen: string | null;
  streaming: boolean;
  drawerOpen: boolean;
  onToggleDrawer: () => void;
  onDisconnect: () => void;
  onKill: () => void;
  onContinue: () => void;
  onSendPrompt: (text: string) => void;
  onSendVoice: (dataB64: string, durationSec: number) => void;
  onRequestScreenshot: () => boolean;
  onToggleScreenStream: (active: boolean) => boolean;
  onSwitchNode: (host: string, label: string) => Promise<boolean>;
}

export default function Dashboard({
  node,
  host,
  apiKey,
  telemetry,
  agentStatus,
  chat,
  screen,
  streaming,
  drawerOpen,
  onToggleDrawer,
  onDisconnect,
  onKill,
  onContinue,
  onSendPrompt,
  onSendVoice,
  onRequestScreenshot,
  onToggleScreenStream,
  onSwitchNode,
}: Props) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.3 }}
      className="flex h-screen w-full flex-col"
    >
      <Header
        node={node}
        host={host}
        telemetry={telemetry}
        agentStatus={agentStatus}
        onKill={onKill}
        onDisconnect={onDisconnect}
        onToggleDrawer={onToggleDrawer}
      />

      <div className="flex min-h-0 flex-1">
        {/* main chat area */}
        <div className="flex min-h-0 flex-1 flex-col">
          <Transcript chat={chat} />
          <ActivityBar agentStatus={agentStatus} onKill={onKill} onContinue={onContinue} />
        </div>

        {/* right drawer */}
        <RightDrawer
          open={drawerOpen}
          onClose={onToggleDrawer}
          chat={chat}
          screen={screen}
          streaming={streaming}
          activeHost={host}
          activeLabel={node}
          apiKey={apiKey}
          telemetry={telemetry}
          onRequestScreenshot={onRequestScreenshot}
          onToggleScreenStream={onToggleScreenStream}
          onSwitchNode={onSwitchNode}
        />
      </div>

      <BottomInputBar onSendPrompt={onSendPrompt} onSendVoice={onSendVoice} />
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/* Transcript                                                           */
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
    <div
      ref={scrollRef}
      onScroll={handleScroll}
      className="custom-scrollbar flex-1 min-h-0 space-y-3 overflow-y-auto px-5 py-4 font-mono text-[13px] leading-relaxed"
    >
      {chat.length === 0 && (
        <div className="flex h-full flex-col items-center justify-center gap-4 text-slate-600">
          <div className="relative">
            <div className="flex h-20 w-20 items-center justify-center rounded-3xl bg-neon/10 text-neon/60 ring-1 ring-neon/20">
              <svg viewBox="0 0 100 100" className="h-12 w-12 fill-current">
                <path d="M50 10 C30 10 15 25 15 45 L15 55 C15 75 30 90 50 90 C70 90 85 75 85 55 L85 45 C85 25 70 10 50 10Z M35 42 C35 38 38 35 42 35 C46 35 49 38 49 42 C49 46 46 49 42 49 C38 49 35 46 35 42Z M58 42 C58 38 61 35 65 35 C69 35 72 38 72 42 C72 46 69 49 65 49 C61 49 58 46 58 42Z M40 62 C40 62 45 72 50 72 C55 72 60 62 60 62" strokeWidth="1.5" stroke="currentColor" fill="none"/>
              </svg>
            </div>
            <span className="absolute -bottom-1 -right-1 h-3 w-3 rounded-full bg-neon/50 animate-pulse-slow" />
          </div>
          <div className="text-center">
            <p className="font-display text-sm font-semibold text-slate-400">Genio is ready</p>
            <p className="mt-1 text-[11px] font-mono text-slate-600">type a prompt below to begin</p>
          </div>
        </div>
      )}

      <AnimatePresence initial={false}>
        {chat.map((event, i) => (
          <motion.div
            key={`${i}-${event.type}`}
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.15 }}
            className="flex gap-3"
          >
            <span className="mt-0.5 select-none text-slate-700 text-[11px]">{i}</span>
            <div className="min-w-0 flex-1">
              {event.type === "answer" && (
                <p className="whitespace-pre-wrap text-slate-200">{event.text}</p>
              )}
              {event.type === "thought" && <ThoughtBubble text={event.text} />}
              {event.type === "tool_call" && <ToolCallLine command={event.command} />}
              {event.type === "tool_result" && <ToolResultLine result={event.result} />}
              {event.type === "stats" && (
                <p className="text-[11px] text-slate-600">
                  {event.tokens ?? 0} tok · {event.tok_per_s?.toFixed(1) ?? "—"} tok/s
                </p>
              )}
              {event.type === "error" && (
                <p className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-rose-300">
                  {event.message}
                </p>
              )}
              {event.type === "killed" && <p className="text-sm text-rose-400">KILL SWITCH — run halted</p>}
              {event.type === "armed" && <p className="text-sm text-emerald-400">re-armed</p>}
              {event.type === "attached" && (
                <p className="text-cyan-400 text-xs">📎 {event.name} → {event.path}</p>
              )}
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

function ThoughtBubble({ text }: { text: string }) {
  const [open, setOpen] = useState(text.length <= 200);

  return (
    <div className="rounded-lg border border-neon/20 bg-neon/5 px-3 py-2">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-1.5 text-left text-[11px] font-semibold uppercase tracking-wider text-neon/80"
      >
        💭 thought
        {text.length > 200 && (
          <span className="ml-auto text-[9px] text-slate-500">{open ? "collapse" : "expand"}</span>
        )}
      </button>
      {(open || text.length <= 200) && (
        <p className="mt-1.5 whitespace-pre-wrap text-xs italic text-slate-400">{text}</p>
      )}
    </div>
  );
}

function ToolCallLine({ command }: { command: string }) {
  return (
    <div className="group flex items-start gap-2 rounded-lg bg-amber-500/5 border border-amber-500/20 px-3 py-1.5">
      <span className="mt-0.5 text-amber-400 text-[11px]">⚡</span>
      <code className="flex-1 break-all text-xs text-amber-200/90">{command}</code>
      <CopyBtn text={command} />
    </div>
  );
}

function ToolResultLine({ result }: { result: ToolResultMap }) {
  const output = (result.stdout ?? result.output ?? result.error ?? "").toString();
  return (
    <div className="ml-6 flex items-center gap-2 text-[11px]">
      {typeof result.returncode === "number" && (
        <span className={`rounded px-1.5 py-0.5 font-bold ${result.returncode === 0 ? "bg-ok/15 text-ok" : "bg-danger/15 text-rose-400"}`}>
          {result.returncode === 0 ? "ok" : `exit ${result.returncode}`}
        </span>
      )}
      {typeof result.success === "boolean" && !("returncode" in result) && (
        <span className={`rounded px-1.5 py-0.5 font-bold ${result.success ? "bg-ok/15 text-ok" : "bg-danger/15 text-rose-400"}`}>
          {result.success ? "ok" : "failed"}
        </span>
      )}
      {result.duration != null && <span className="text-slate-500">{result.duration}s</span>}
      {output && (
        <>
          <span className="truncate text-slate-500 max-w-xs">
            {output.split("\n")[0].slice(0, 80)}
          </span>
          <CopyBtn text={output} />
        </>
      )}
    </div>
  );
}

function CopyBtn({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch { /* noop */ }
  }
  return (
    <button
      onClick={copy}
      className="shrink-0 rounded px-1 py-0.5 text-[10px] text-slate-500 opacity-0 transition-all group-hover:opacity-100 hover:bg-neon/10 hover:text-neon"
      title="Copy"
    >
      {copied ? "✓" : "⧉"}
    </button>
  );
}
