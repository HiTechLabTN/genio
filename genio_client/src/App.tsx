import { AnimatePresence } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import ConnectionHub from "./components/ConnectionHub";
import Dashboard from "./components/Dashboard";
import GoogleAuthOnboarding, { shouldShowGoogleAuth } from "./components/GoogleAuthOnboarding";
import PermissionOnboarding, { shouldShowOnboarding } from "./components/PermissionOnboarding";
import UpdateModal from "./components/UpdateModal";
import { useGenioSocket } from "./hooks/useGenioSocket";
import { useTaskProcessor } from "./hooks/useTaskProcessor";
import { checkForUpdates } from "./lib/updater";
import { useDeviceProfile } from "./lib/deviceProfiler";
import { decideEngine } from "./lib/adaptiveEngine";
import { getGoogleToken, hasGoogleAuth } from "./lib/googleAuth";
import type { Attachment, ServerNode } from "./lib/types";
import { ErrorBoundary } from "./components/v3";
import { useVoiceOutput } from "./components/v3/useVoiceOutput";
// New Islamic HUD imports
import IslamicPatterns from "./components/background/IslamicPatterns";
import HologramMascot from "./components/mascot/HologramMascot";
import SystemMetrics from "./components/hud/SystemMetrics";
import BrainActivity from "./components/hud/BrainActivity";
import MatrixTaskScreen from "./components/hud/MatrixTaskScreen";
import SplashScreen from "./components/layout/SplashScreen";

export default function App() {
  const [showSplash, setShowSplash] = useState(true);
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
  const matrixTasks: string[] = [...(taskProc.thinkingSteps ?? []), ...(taskProc.toolActivity ?? [])];
  const voice = useVoiceOutput();
  const prevResultRef = useRef<string>("");

  useEffect(() => {
    const r = taskProc.result;
    if (r && r !== prevResultRef.current) {
      prevResultRef.current = r;
      voice.speak(r);
      const t = window.setTimeout(() => taskProc.setIsMinimized(true), 700);
      return () => clearTimeout(t);
    }
    if (!r) prevResultRef.current = "";
  }, [taskProc.result, taskProc.setIsMinimized, voice]);

  useEffect(() => {
    if (isThinking) voice.stop();
  }, [isThinking, voice]);

  const [connected, setConnected] = useState(false);
  const [target, setTarget] = useState<ServerNode | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [update, setUpdate] = useState<{ version: string; notes?: string } | null>(null);
  const lastPromptRef = useRef("");
  const lastPromptFileRef = useRef<Attachment[] | undefined>(undefined);
  const [splashReady, setSplashReady] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [healthStatus, setHealthStatus] = useState<"checking" | "ok" | "offline">("checking");

  useEffect(() => {
    let alive = true;
    // F3: delay update check 3s + idle callback, never at boot (avoid freeze on mid-range Android)
    const ric = (window as unknown as { requestIdleCallback?: (cb: () => void, opts?: { timeout: number }) => number }).requestIdleCallback;
    const schedule = (cb: () => void) => {
      if (ric) ric(cb, { timeout: 4000 });
      else window.setTimeout(cb, 3000);
    };
    const tid = window.setTimeout(() => {
      schedule(() => {
        if (!alive) return;
        checkForUpdates().then((u) => {
          if (alive && u) setUpdate(u);
        });
      });
    }, 3000);
    return () => {
      alive = false;
      clearTimeout(tid);
    };
  }, []);

  // F1: /health pre-check 3s; fail -> On-Device Tier A + status chip + retry; never crash
  useEffect(() => {
    if (!splashReady) return;
    let alive = true;
    async function checkHealth() {
      try {
        const c = new AbortController();
        const to = window.setTimeout(() => c.abort(), 3000);
        const res = await fetch("/health", { signal: c.signal }).catch(() => fetch("http://localhost:8000/api/v1/status", { signal: c.signal }).catch(() => null));
        clearTimeout(to);
        if (!alive) return;
        if (res && (res as Response).ok) setHealthStatus("ok");
        else setHealthStatus("offline");
      } catch {
        if (alive) setHealthStatus("offline");
      }
    }
    checkHealth();
    const id = window.setInterval(checkHealth, 15000);
    return () => { alive = false; clearInterval(id); };
  }, [splashReady]);

  // Splash ready dispatch
  useEffect(() => {
    if (!splashReady) return;
    window.dispatchEvent(new CustomEvent("genio:ready"));
  }, [splashReady]);

  async function handleConnect(node: ServerNode) {
    // F1 pre-check
    try {
      const c = new AbortController();
      const to = window.setTimeout(() => c.abort(), 3000);
      const res = await fetch(`http://${node.host}:${node.port}/api/v1/status`, { signal: c.signal }).catch(() => null);
      clearTimeout(to);
      if (!res || !(res as Response).ok) {
        setHealthStatus("offline");
        // fallback Tier A is handled via deviceProfiler + adaptiveEngine elsewhere
        // show status chip but still try connect
      } else {
        setHealthStatus("ok");
      }
    } catch {
      setHealthStatus("offline");
    }
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

  // Map agentStatus to HologramMascot status
  const mascotStatus = (() => {
    if (taskProc.result && agentStatus.kind === "completed") return "answering";
    if (agentStatus.kind === "thinking") return "thinking";
    if (agentStatus.kind === "executing") return "executing";
    if (isListening) return "listening";
    if (agentStatus.kind === "completed") return "completed";
    return "idle";
  })();

  const showV3Portal = (connected && target) || isGeminiCloud;

  // audioLevel placeholder — reuse voice output level or 0.45 when listening
  const audioLevel = isListening ? 0.45 : 0;

  if (showGoogleAuth) {
    return (
      <div style={{ width: "100vw", height: "100vh", position: "relative", overflow: "hidden" }} className="bg-[#020B1E]">
        <ErrorBoundary name="IslamicPatterns"><IslamicPatterns /></ErrorBoundary>
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
        <ErrorBoundary name="IslamicPatterns"><IslamicPatterns /></ErrorBoundary>
        <PermissionOnboarding onComplete={() => setShowOnboarding(false)} onSkip={() => setShowOnboarding(false)} />
      </div>
    );
  }

  return (
    <div style={{ width: "100vw", height: "100vh", position: "relative", overflow: "hidden" }} className="bg-[#020B1E]">
      {/* SplashScreen z-50 */}
      {showSplash && <SplashScreen onReady={() => { setShowSplash(false); setSplashReady(true); }} />}

      {/* z-0 IslamicPatterns */}
      <ErrorBoundary name="IslamicPatterns">
        <div className="absolute inset-0 z-0">
          <IslamicPatterns />
        </div>
      </ErrorBoundary>

      {/* Health status chip (F1) */}
      {healthStatus !== "checking" && (
        <div className="absolute left-3 top-3 z-30 flex items-center gap-2 rounded-full border px-3 py-1 font-mono text-[10px] backdrop-blur" style={{ borderColor: healthStatus === "ok" ? "rgba(52,211,153,0.3)" : "rgba(251,113,133,0.3)", background: healthStatus === "ok" ? "rgba(52,211,153,0.1)" : "rgba(251,113,133,0.1)", color: healthStatus === "ok" ? "#34d399" : "#fb7185" }}>
          <span className={`h-2 w-2 rounded-full ${healthStatus === "ok" ? "bg-emerald-400" : "bg-rose-400 animate-pulse"}`} />
          {healthStatus === "ok" ? "SYSTEM LIVE" : "ON-DEVICE • Tier A"}
          {healthStatus === "offline" && <button onClick={() => window.location.reload()} className="ml-2 underline">retry</button>}
        </div>
      )}

      {/* z-8 MatrixTaskScreen */}
      {showV3Portal && (
        <div className="pointer-events-none absolute inset-x-3 top-16 z-[8] md:inset-x-6 md:top-20">
          <ErrorBoundary name="MatrixTaskScreen">
            <div className="pointer-events-auto">
              <MatrixTaskScreen tasks={matrixTasks} expanded={expanded} onToggle={() => setExpanded((v) => !v)} />
            </div>
          </ErrorBoundary>
        </div>
      )}

      {/* z-10 HologramMascot — F2: h-[35vh] avatar zone visible immediately at idle, no empty area */}
      {showV3Portal && (
        <div className={`absolute z-10 flex h-[35vh] w-full items-center justify-center ${mascotStatus === "answering" ? "right-6 top-20 md:right-10 md:top-24 left-auto translate-x-0 w-auto" : "left-1/2 top-[72px] -translate-x-1/2 md:top-[80px]"}`} style={{ pointerEvents: mascotStatus === "answering" ? "auto" : "auto" }}>
          <ErrorBoundary name="HologramMascot">
            <HologramMascot status={mascotStatus} audioLevel={audioLevel} isMinimized={mascotStatus === "answering" || expanded} />
          </ErrorBoundary>
        </div>
      )}

      {/* z-15 Chat + VoiceInput (keep Dashboard's ChatBubble + BottomInputBar via GenioShell children) */}
      <div className="relative z-[15] flex h-full w-full flex-col">
        <div className="pointer-events-none absolute left-1/2 top-[52%] h-[420px] w-[420px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-400/10 md:h-[560px] md:w-[560px]" style={{ opacity: showV3Portal ? 1 : 0 }} />
        <AnimatePresence mode="wait">
          {showV3Portal ? (
            <div key="v3-portal" className="flex h-screen w-full flex-col">
              <div className="flex min-h-0 flex-1 flex-col pt-[36vh] md:pt-[38vh]">
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
          <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10">
            {/* keep ChronosPortal minimized hint but not full overlay to avoid z-conflict with new HUD */}
          </div>
        ) : null}
      </div>

      {/* z-20 metrics/brain */}
      {showV3Portal && (
        <div className="pointer-events-none absolute bottom-3 right-3 z-20 flex flex-col items-end gap-3 md:bottom-4 md:right-6">
          <div className="pointer-events-auto hidden md:block">
            <ErrorBoundary name="SystemMetrics">
              <SystemMetrics telemetry={telemetry ?? undefined} />
            </ErrorBoundary>
          </div>
          <div className="pointer-events-auto md:hidden">
            <ErrorBoundary name="SystemMetrics-mobile">
              <SystemMetrics telemetry={telemetry ?? undefined} />
            </ErrorBoundary>
          </div>
          <ErrorBoundary name="BrainActivity">
            <BrainActivity active={agentStatus.kind === "thinking" || agentStatus.kind === "executing"} />
          </ErrorBoundary>
        </div>
      )}

      {/* TaskMinimizer fixed top-right — keep for result */}
      {showV3Portal && (
        <div className="pointer-events-none absolute right-3 top-[58px] z-30 hidden md:block" style={{ zIndex: 30 }}>
          {/* reuse v3 TaskMinimizer if exists */}
        </div>
      )}
    </div>
  );
}
