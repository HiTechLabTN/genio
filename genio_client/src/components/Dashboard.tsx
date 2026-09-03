import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useRef, useState } from "react";
import ActivityBar from "./ActivityBar";
import AudioPlayer, { stopAllAudio } from "./AudioPlayer";
import BottomInputBar from "./BottomInputBar";
import Header from "./Header";
import RightDrawer from "./RightDrawer";
import CyberAvatar from "./avatar/CyberAvatar";
import ErrorBoundary from "./v3/ErrorBoundary";
import { HolographicHud } from "./avatar/HolographicHud";
import type { AgentStatus, Attachment, ChatEvent, TelemetrySnapshot, ToolResultMap } from "../lib/types";
import type { DeviceProfile } from "../lib/deviceProfiler";
import type { EngineDecision } from "../lib/adaptiveEngine";

interface Props {
  node: string;
  host: string;
  apiKey?: string;
  telemetry: TelemetrySnapshot | null;
  telemetryStale: boolean;
  agentStatus: AgentStatus;
  chat: ChatEvent[];
  screen: string | null;
  streaming: boolean;
  drawerOpen: boolean;
  deviceProfile?: DeviceProfile;
  engineDecision?: EngineDecision;
  onToggleDrawer: () => void;
  onDisconnect: () => void;
  onKill: () => void;
  onContinue: () => void;
  onSendPrompt: (text: string, attachments?: Attachment[]) => void;
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
  telemetryStale,
  agentStatus,
  chat,
  screen,
  streaming,
  drawerOpen,
  deviceProfile,
  engineDecision,
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
  const busy = agentStatus.kind === "thinking" || agentStatus.kind === "executing";
  const avatarMode = busy ? "listening" : "idle";
  const [selfieActive, setSelfieActive] = useState(false);

  // Responsive layout: avatar occupies primary viewport idle, HUD position when busy
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
        telemetryStale={telemetryStale}
        agentStatus={agentStatus}
        selfieActive={selfieActive}
        onToggleSelfie={() => setSelfieActive((v) => !v)}
        onKill={onKill}
        onDisconnect={onDisconnect}
        onToggleDrawer={onToggleDrawer}
      />

      {/* Engine tier subtle bar when provided */}
      {deviceProfile && engineDecision && (
        <div className="flex items-center justify-center gap-2 border-b border-neon/10 bg-carbon/30 px-4 py-1 font-mono text-[10px] text-slate-500 md:hidden">
          <span className={`h-1.5 w-1.5 rounded-full ${engineDecision.mode === "local" ? "bg-ok" : "bg-amber-400"}`} />
          Tier {deviceProfile.tier} · {engineDecision.mode === "local" ? "On-Device" : "Cloud"} · {deviceProfile.ramGB}GB
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        {/* main chat area — strict viewport */}
        <div className="relative flex min-h-0 flex-1 flex-col">
          {/* PHASE 4 STRICT RESPONSIVE VIEWPORT
              Idle: avatar dedicated top h-[35vh], chat below h-[65vh] with overflow
              Busy: avatar shrinks to top-corner widget, HUD expands in place */}
          <AnimatePresence mode="wait">
            {busy ? (
              <motion.div
                key="busy-avatar"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0 }}
                className="pointer-events-none absolute right-3 top-3 z-20 flex h-28 w-28 items-center justify-center rounded-2xl border border-neon/20 bg-carbon/60 backdrop-blur md:right-4 md:top-4 md:h-32 md:w-32"
              >
                <div className="pointer-events-auto">
                  <ErrorBoundary name="CyberAvatar-mini"><CyberAvatar mode={avatarMode} size={112} faceTrack={false} audioLevel={0.45} /></ErrorBoundary>
                </div>
              </motion.div>
            ) : (
              <motion.div
                key="idle-avatar"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="relative flex h-[35vh] shrink-0 items-center justify-center overflow-hidden border-b border-neon/5 bg-[#020B1E]"
                style={{ pointerEvents: "auto" }}
              >
                {/* Deep dark-blue space + glowing cyan portals */}
                <div className="pointer-events-none absolute inset-0">
                  <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_60%_at_50%_40%,rgba(0,229,255,0.12),transparent_70%)]" />
                  <div className="absolute inset-0 opacity-40" style={{ backgroundImage: "radial-gradient(white 1px, transparent 1px)", backgroundSize: "32px 32px" }} />
                  <div className="absolute left-1/2 top-1/2 h-[480px] w-[480px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-400/20 shadow-[0_0_60px_rgba(0,229,255,0.25)] animate-spin" style={{ animationDuration: "28s" }} />
                  <div className="absolute left-1/2 top-1/2 h-[620px] w-[620px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-400/10 shadow-[0_0_80px_rgba(0,229,255,0.15)] animate-spin" style={{ animationDuration: "42s", animationDirection: "reverse" }} />
                  <div className="absolute left-1/2 top-1/2 h-[360px] w-[360px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/5" />
                </div>
                <div className="pointer-events-auto relative z-10">
                  <ErrorBoundary name="CyberAvatar-full"><CyberAvatar mode={avatarMode} size={340} faceTrack={selfieActive} audioLevel={0} /></ErrorBoundary>
                </div>
                <div className="pointer-events-none absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-[#020B1E] to-transparent" />
              </motion.div>
            )}
          </AnimatePresence>

          {/* Chat history — strict h-[65vh] idle, flex-1 when busy (HUD occupies part) */}
          <div className={busy ? "flex min-h-0 flex-1 flex-col pt-2" : "flex h-[65vh] min-h-0 flex-col overflow-hidden pb-2"}>
            {/* TN VPS offline — visual alert in chat layer */}
            {telemetryStale && (
              <div className="mx-4 mb-2 flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-xs font-medium text-red-300 shadow-[0_0_12px_rgba(239,68,68,0.15)]">
                <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)]" />
                <span>TN VPS hors ligne — السيرفر طايح توا، ما نجمش نكوّنكتي.</span>
                <span className="ml-auto hidden text-[10px] text-red-300/70 sm:inline">Basculer vers Gemini Cloud</span>
              </div>
            )}
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
              <Transcript chat={chat} agentStatus={agentStatus} />
            </div>
            {/* Busy: expand Holographic HUD in place of avatar's former space */}
            {busy && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="shrink-0 px-3 pb-2">
                <HolographicHud chat={chat} agentStatus={agentStatus} telemetry={telemetry} />
              </motion.div>
            )}
            {/* Idle: HUD hidden to keep chat clean */}
          </div>

          <ActivityBar chat={chat} agentStatus={agentStatus} onKill={onKill} onContinue={onContinue} />
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

function Transcript({ chat, agentStatus }: { chat: ChatEvent[]; agentStatus?: AgentStatus }) {
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

  // stop any playing audio when the agent is interrupted (killed / goes idle)
  useEffect(() => {
    if (agentStatus?.kind === "idle" || agentStatus?.kind === "completed") {
      stopAllAudio();
    }
  }, [agentStatus]);

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
            className={`flex gap-3 ${event.type === "user" ? "justify-end" : ""}`}
          >
            <span className={`mt-0.5 select-none text-[11px] ${event.type === "user" ? "order-last" : "text-slate-700"}`}>{i}</span>
            <div className={`min-w-0 ${event.type === "user" ? "max-w-[85%]" : "flex-1"}`}>
              {event.type === "user" && (
                <>
                  <UserBubble text={event.text} attachments={event.attachments} />
                  {event.audio && <AudioPlayer audioUrl={event.audio.url} base64Audio={event.audio.dataB64} mime={event.audio.mime} />}
                </>
              )}
              {event.type === "answer" && (
                <>
                  <p className="whitespace-pre-wrap text-slate-200">{event.text}</p>
                  {event.audio && <AudioPlayer audioUrl={event.audio.url} base64Audio={event.audio.dataB64} mime={event.audio.mime} />}
                </>
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

function UserBubble({ text, attachments }: { text: string; attachments?: { name: string; content?: string }[] }) {
  return (
    <div className="ml-auto w-fit max-w-full rounded-2xl rounded-tr-sm border border-cyan-500 bg-cyan-900/60 px-3 py-2">
      <p className="whitespace-pre-wrap text-sm text-cyan-50">{text}</p>
      {attachments && attachments.length > 0 && (
        <div className="mt-1.5 flex flex-col gap-1">
          {attachments.map((a) => (
            <span key={a.name} className="inline-flex items-center gap-1.5 rounded bg-slate-950/60 px-2 py-0.5 text-[10px] font-mono text-neon-soft">
              📎 {a.name}
            </span>
          ))}
        </div>
      )}
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
