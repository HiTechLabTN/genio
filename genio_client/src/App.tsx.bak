import { AnimatePresence } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import ConnectionHub from "./components/ConnectionHub";
import Dashboard from "./components/Dashboard";
import GoogleAuthOnboarding, { shouldShowGoogleAuth } from "./components/GoogleAuthOnboarding";
import PermissionOnboarding, { shouldShowOnboarding } from "./components/PermissionOnboarding";
import UpdateModal from "./components/UpdateModal";
import ChronosPortal from "./components/ChronosPortal/ChronosPortal";
import { useGenioSocket } from "./hooks/useGenioSocket";
import { useTaskProcessor } from "./hooks/useTaskProcessor";
import { checkForUpdates } from "./lib/updater";
import { useDeviceProfile } from "./lib/deviceProfiler";
import { decideEngine } from "./lib/adaptiveEngine";
import { getGoogleToken, hasGoogleAuth } from "./lib/googleAuth";
import type { Attachment, ServerNode } from "./lib/types";
import { AndalusianBackground, MatrixTaskBoard, SystemMetricsLive, TaskMinimizer, ParticleBrain, AnimeMascot, ErrorBoundary } from "./components/v3";
import { useVoiceOutput } from "./components/v3/useVoiceOutput";

export default function App() {
  const [showGoogleAuth, setShowGoogleAuth] = useState(() => shouldShowGoogleAuth());
  const [showOnboarding, setShowOnboarding] = useState(() => shouldShowOnboarding());
  const deviceProfile = useDeviceProfile();
  const engineDecision = decideEngine();
  const isGeminiCloud = hasGoogleAuth();
  const [chronosDismissed, setChronosDismissed] = useState(false);

  const {
    agentStatus: wsAgentStatus,
    telemetry,
    telemetryStale,
    chat: wsChat,
    screen,
    streaming,
    connect,
    disconnect,
    send,
    sendPrompt: wsSendPrompt,
    kill,
    requestScreenshot,
    toggleScreenStream,
  } = useGenioSocket();
  const [geminiChat, setGeminiChat] = useState<typeof wsChat>([]);
  const [geminiStatus, setGeminiStatus] = useState<typeof wsAgentStatus>({ kind: "idle" });
  const chat = isGeminiCloud ? geminiChat : wsChat;
  const agentStatus = isGeminiCloud ? geminiStatus : wsAgentStatus;
  const sendPrompt = isGeminiCloud
    ? (text: string, attachments?: Attachment[]) => {
        setGeminiChat((prev) => [...prev.slice(-299), { type: "user", text, timestamp: Date.now() } as const]);
        setGeminiStatus({ kind: "thinking" });
        void (async () => {
          try {
            const { streamGemini } = await import("./lib/providers/gemini_provider");
            let acc = "";
            setGeminiStatus({ kind: "executing", tool: "gemini" });
            for await (const chunk of streamGemini(text, { attachments })) {
              if (chunk.text) {
                acc += chunk.text;
                setGeminiChat((prev) => {
                  const last = prev[prev.length - 1];
                  if (last?.type === "thought" && (last as { text: string }).text === acc.slice(0, -chunk.text!.length)) {
                    return [...prev.slice(0, -1), { type: "thought", text: acc }];
                  }
                  return [...prev.slice(-299), { type: "thought", text: acc }];
                });
              }
              if (chunk.toolCall) {
                setGeminiChat((prev) => [...prev.slice(-299), { type: "tool_call", command: JSON.stringify(chunk.toolCall) }]);
              }
              if (chunk.done) {
                setGeminiChat((prev) => {
                  const last = prev[prev.length - 1];
                  if (last?.type === "thought") return [...prev.slice(0, -1), { type: "answer", text: acc.trim() }];
                  return [...prev.slice(-299), { type: "answer", text: acc.trim() || "Saha, ena Genio! Chnowa n3awnk?" }];
                });
                setGeminiStatus({ kind: "completed" });
                setTimeout(() => setGeminiStatus({ kind: "idle" }), 1200);
              }
            }
          } catch (e: unknown) {
            const msg = e instanceof Error ? e.message : String(e);
            if (msg.includes("السيرفر طايح")) {
              setGeminiChat((prev) => [...prev.slice(-299), { type: "answer", text: msg }]);
            } else {
              setGeminiChat((prev) => [...prev.slice(-299), { type: "error", message: msg }]);
            }
            setGeminiStatus({ kind: "idle" });
          }
        })();
        return true;
      }
    : wsSendPrompt;

  // v3 task processor integration — defensive defaults to prevent undefined crash (black screen)
  const taskProcRaw = useTaskProcessor({ chat: chat ?? [], telemetry: telemetry ?? null, agentStatus });
  const taskProc = {
    thinkingSteps: taskProcRaw?.thinkingSteps ?? [],
    toolActivity: taskProcRaw?.toolActivity ?? [],
    isProcessing: taskProcRaw?.isProcessing ?? false,
    result: taskProcRaw?.result ?? "",
    isMinimized: taskProcRaw?.isMinimized ?? false,
    setIsMinimized: taskProcRaw?.setIsMinimized ?? (() => {}),
    metrics: taskProcRaw?.metrics ?? { cpu: 0, gpu: 0, ram: { used: 0, total: 16 }, vram: { used: 0, total: 8 } },
    error: taskProcRaw?.error ?? null,
  } as ReturnType<typeof useTaskProcessor>;
  const isThinking = taskProc.isProcessing ?? false;
  const isListening = agentStatus.kind === "thinking" || agentStatus.kind === "executing";
  // tasks for matrix: combine thinkingSteps + toolActivity with safe spread
  const matrixTasks: string[] = [...(taskProc.thinkingSteps ?? []), ...(taskProc.toolActivity ?? [])];
  const voice = useVoiceOutput();
  const prevResultRef = useRef<string>("");

  // VoiceOutput + TaskMinimizer trigger when result populates
  useEffect(() => {
    const r = taskProc.result;
    if (r && r !== prevResultRef.current) {
      prevResultRef.current = r;
      voice.speak(r);
      // auto-minimize after 700ms (let user read)
      const t = window.setTimeout(() => taskProc.setIsMinimized(true), 700);
      return () => clearTimeout(t);
    }
    if (!r) prevResultRef.current = "";
  }, [taskProc.result, taskProc.setIsMinimized, voice]);

  // stop speech when new task starts
  useEffect(() => {
    if (isThinking) voice.stop();
  }, [isThinking, voice]);

  const [connected, setConnected] = useState(false);
  const [target, setTarget] = useState<ServerNode | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [update, setUpdate] = useState<{ version: string; notes?: string } | null>(null);
  const lastPromptRef = useRef("");
  const lastPromptFileRef = useRef<Attachment[] | undefined>(undefined);

  useEffect(() => {
    let alive = true;
    checkForUpdates().then((u) => {
      if (alive && u) setUpdate(u);
    });
    return () => { alive = false; };
  }, []);

  async function handleConnect(node: ServerNode) {
    const ok = await connect(node);
    if (ok) {
      setTarget(node);
      setConnected(true);
      setDrawerOpen(false);
    }
    return ok;
  }
  function handleDisconnect() {
    voice.stop();
    disconnect();
    setConnected(false);
    setTarget(null);
    setDrawerOpen(false);
  }
  async function handleSwitchNode(host: string, label: string) {
    if (!target) return false;
    const next: ServerNode = { ...target, host, label };
    const ok = await connect(next);
    if (ok) setTarget(next);
    return ok;
  }
  function handleSendPrompt(text: string, attachments?: Attachment[]) {
    lastPromptRef.current = text;
    lastPromptFileRef.current = attachments;
    setChronosDismissed(false);
    taskProc.setIsMinimized(false);
    voice.stop();
    sendPrompt(text, attachments);
  }
  function handleContinue() {
    if (lastPromptRef.current) sendPrompt(lastPromptRef.current, lastPromptFileRef.current);
  }

  if (showGoogleAuth) {
    return (
      <div style={{ width: "100vw", height: "100vh", position: "relative", overflow: "hidden" }} className="bg-[#020B1E]">
        <ErrorBoundary name="AndalusianBackground"><AndalusianBackground /></ErrorBoundary>
        <GoogleAuthOnboarding
          onAuthed={() => setShowGoogleAuth(false)}
          onSkip={() => setShowGoogleAuth(false)}
        />
      </div>
    );
  }
  if (showOnboarding) {
    return (
      <div style={{ width: "100vw", height: "100vh", position: "relative", overflow: "hidden" }} className="bg-[#020B1E]">
        <ErrorBoundary name="AndalusianBackground"><AndalusianBackground /></ErrorBoundary>
        <PermissionOnboarding onComplete={() => setShowOnboarding(false)} onSkip={() => setShowOnboarding(false)} />
      </div>
    );
  }

  const showV3Portal = connected && target || isGeminiCloud;

  return (
    <div style={{ width: "100vw", height: "100vh", position: "relative", overflow: "hidden" }} className="bg-[#020B1E]">
      {/* z-index 0: AndalusianBackground — wrapped in ErrorBoundary so a Canvas crash never blacks out UI */}
      <ErrorBoundary name="AndalusianBackground"><AndalusianBackground /></ErrorBoundary>

      {/* z-index 1: MatrixTaskBoard — semi-transparent overlay behind content but above bg */}
      {showV3Portal && (
        <div className="pointer-events-none absolute inset-0" style={{ zIndex: 1 }}>
          <ErrorBoundary name="MatrixTaskBoard"><MatrixTaskBoard tasks={matrixTasks} isThinking={isThinking} className="absolute inset-3" /></ErrorBoundary>
        </div>
      )}

      {/* z-index 3: SystemMetricsLive fixed top-right, always visible when connected */}
      {showV3Portal && (
        <div className="pointer-events-none absolute right-3 top-[58px] z-30 hidden md:block" style={{ zIndex: 3 }}>
          <ErrorBoundary name="SystemMetricsLive"><SystemMetricsLive className="pointer-events-auto w-[220px]" /></ErrorBoundary>
        </div>
      )}
      {/* mobile metrics bar */}
      {showV3Portal && (
        <div className="absolute left-3 right-3 top-[58px] z-30 md:hidden" style={{ zIndex: 3 }}>
          <ErrorBoundary name="SystemMetricsLive-mobile"><SystemMetricsLive className="w-full opacity-95" /></ErrorBoundary>
        </div>
      )}

      {/* z-index 2: main portal / mascot / brain */}
      <div className="relative flex h-full w-full flex-col" style={{ zIndex: 2 }}>
        {/* top header placeholder — Header is inside Dashboard, but we show SELFIE toggle here for v3 */}
        {/* When connected, Dashboard already renders Header; we keep v3 mascot layer independently */}

        <AnimatePresence mode="wait">
          {showV3Portal ? (
            <div key="v3-portal" className="flex h-screen w-full flex-col">
              {/* subtle v3 top bar with ParticleBrain + listening indicator */}
              <div className="flex items-center gap-3 px-4 pt-[68px] md:px-6">
                <ErrorBoundary name="ParticleBrain"><ParticleBrain isThinking={isThinking} size={56} className="shrink-0" /></ErrorBoundary>
                <div className="min-w-0 flex-1">
                  <div className="font-mono text-[11px] tracking-[0.16em] text-cyan-300">
                    {isThinking ? "CHRONOS · THINKING..." : taskProc.result ? "CHRONOS · READY" : "CHRONOS · IDLE"}
                  </div>
                  <div className="truncate font-mono text-xs text-slate-400">
                    {isThinking ? matrixTasks[matrixTasks.length - 1] || "synchronizing time & tasks..." : "ready when you are."}
                  </div>
                </div>
                <div className={`hidden items-center gap-2 rounded-full border px-3 py-1.5 font-mono text-[10px] md:flex ${isListening ? "border-red-400/30 bg-red-500/10 text-red-300" : "border-cyan-400/20 bg-cyan-400/10 text-cyan-300"}`}>
                  <span className={`h-2 w-2 rounded-full ${isListening ? "bg-red-500 animate-pulse" : "bg-cyan-400"}`} />
                  {isListening ? "ÉCOUTE" : "PRÊT"}
                </div>
              </div>

              {/* mascot row — centered holographic avatar */}
              <div className={`relative flex shrink-0 items-center justify-center overflow-hidden transition-all duration-700 ${taskProc.isMinimized ? "h-0 opacity-0" : "h-[42vh] md:h-[44vh]"}`}>
                {/* cyan portal rings behind mascot */}
                <div className="pointer-events-none absolute left-1/2 top-1/2 h-[420px] w-[420px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-400/15 shadow-[0_0_60px_rgba(0,229,255,0.18)]" />
                <div className="pointer-events-none absolute left-1/2 top-1/2 h-[560px] w-[560px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-400/10" />
                <ErrorBoundary name="AnimeMascot"><AnimeMascot listening={isListening} isThinking={isThinking} faceTrack={!taskProc.isMinimized} size={360} className="relative z-10" /></ErrorBoundary>
              </div>

              {/* Dashboard embedded — portal UI */}
              <div className={`flex min-h-0 flex-1 flex-col transition-all duration-700 ${taskProc.isMinimized ? "pointer-events-none opacity-0 scale-[0.98]" : "opacity-100"}`}>
                <Dashboard
                  key={isGeminiCloud ? "dashboard-gemini" : "dashboard"}
                  node={isGeminiCloud ? "Gemini Cloud" : target?.label || "Genio"}
                  host={isGeminiCloud ? "genio-server" : target?.host || ""}
                  apiKey={isGeminiCloud ? getGoogleToken() || undefined : target?.key}
                  telemetry={telemetry}
                  telemetryStale={telemetryStale}
                  agentStatus={agentStatus}
                  chat={chat}
                  screen={screen}
                  streaming={streaming}
                  drawerOpen={drawerOpen}
                  deviceProfile={deviceProfile}
                  engineDecision={engineDecision}
                  onToggleDrawer={() => setDrawerOpen((o) => !o)}
                  onDisconnect={isGeminiCloud ? () => setShowGoogleAuth(true) : handleDisconnect}
                  onKill={kill}
                  onContinue={handleContinue}
                  onSendPrompt={handleSendPrompt}
                  onSendVoice={(dataB64, durationSec) => send({ action: "voice_wav", data_b64: dataB64, duration: durationSec, final: true })}
                  onRequestScreenshot={requestScreenshot}
                  onToggleScreenStream={toggleScreenStream}
                  onSwitchNode={handleSwitchNode}
                />
              </div>
            </div>
          ) : (
            <ConnectionHub key="hub" onConnect={handleConnect} />
          )}
        </AnimatePresence>

        {update && <UpdateModal version={update.version} notes={update.notes} onClose={() => setUpdate(null)} />}

        {!chronosDismissed && taskProc.thinkingSteps.length === 0 && taskProc.toolActivity.length === 0 ? (
          <ChronosPortal chat={chat} telemetry={telemetry} agentStatus={agentStatus} onDismiss={() => setChronosDismissed(true)} />
        ) : null}
      </div>

      {/* TaskMinimizer fixed top-right — z-index 3 */}
      {showV3Portal && (
        <TaskMinimizer
          result={taskProc.result}
          isMinimized={taskProc.isMinimized}
          onToggle={() => taskProc.setIsMinimized(!taskProc.isMinimized)}
          onExpand={() => taskProc.setIsMinimized(false)}
        />
      )}
    </div>
  );
}
