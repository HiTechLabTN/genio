import { AnimatePresence } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import ConnectionHub from "./components/ConnectionHub";
import GoogleAuthOnboarding, { shouldShowGoogleAuth } from "./components/GoogleAuthOnboarding";
import PermissionOnboarding, { shouldShowOnboarding } from "./components/PermissionOnboarding";
import UpdateModal from "./components/UpdateModal";
import { useGenioSocket } from "./hooks/useGenioSocket";
import { useTaskProcessor } from "./hooks/useTaskProcessor";
import { checkForUpdates } from "./lib/updater";
import { useDeviceProfile } from "./lib/deviceProfiler";
import { decideEngine } from "./lib/adaptiveEngine";
import { hasGoogleAuth } from "./lib/googleAuth";
import type { Attachment, ServerNode } from "./lib/types";
import { ErrorBoundary } from "./components/v3";
import { useVoiceOutput } from "./components/v3/useVoiceOutput";
import IslamicPatterns from "./components/background/IslamicPatterns";
import HologramMascot from "./components/mascot/HologramMascot";
import SystemMetrics from "./components/hud/SystemMetrics";
import MatrixTaskScreen from "./components/hud/MatrixTaskScreen";
import SplashScreen from "./components/layout/SplashScreen";
import BottomInputBar from "./components/BottomInputBar";
import { lazy, Suspense } from "react";
const LivingMascot3D = lazy(() => import("./components/mascot/LivingMascot3D"));

// S2 SINGLE ROOT LAYOUT — h-[100dvh] fixed inset-0, no page scroll
// z-0 IslamicPatterns .07, z-1 LivingMascot3D middle 60%, z-20 TopBar, z-15 TaskMatrix compact collapsed, z-15 BottomSheet

export default function App() {
  const [showSplash, setShowSplash] = useState(true);
  const [showGoogleAuth, setShowGoogleAuth] = useState(() => shouldShowGoogleAuth());
  const [showOnboarding, setShowOnboarding] = useState(() => shouldShowOnboarding());
  useEffect(() => {
    if (!showGoogleAuth) return;
    if (!hasGoogleAuth()) return;
    const id = window.setTimeout(() => setShowGoogleAuth(false), 1200);
    return () => clearTimeout(id);
  }, [showGoogleAuth]);
  const deviceProfile = useDeviceProfile();
  const engineDecision = decideEngine();
  const isGeminiCloud = hasGoogleAuth();

  const {
    agentStatus: wsAgentStatus,
    telemetry,
    telemetryStale: _telemetryStale,
    chat: wsChat,
    screen: _screen,
    streaming: _streaming,
    connect,
    disconnect,
    send,
    sendPrompt: wsSendPrompt,
    kill,
    requestScreenshot: _requestScreenshot,
    toggleScreenStream: _toggleScreenStream,
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
              if (chunk.toolCall) setGeminiChat((prev) => [...prev.slice(-299), { type: "tool_call", command: JSON.stringify(chunk.toolCall) }]);
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
            if (msg.includes("السيرفر طايح")) setGeminiChat((prev) => [...prev.slice(-299), { type: "answer", text: msg }]);
            else setGeminiChat((prev) => [...prev.slice(-299), { type: "error", message: msg }]);
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
  useEffect(() => { if (isThinking) voice.stop(); }, [isThinking, voice]);

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
    const ric = (window as unknown as { requestIdleCallback?: (cb: () => void, opts?: { timeout: number }) => number }).requestIdleCallback;
    const schedule = (cb: () => void) => { if (ric) ric(cb, { timeout: 4000 }); else window.setTimeout(cb, 3000); };
    const tid = window.setTimeout(() => { schedule(() => { if (!alive) return; checkForUpdates().then((u) => { if (alive && u) setUpdate(u); }); }); }, 3000);
    return () => { alive = false; clearTimeout(tid); };
  }, []);
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
        if (res && (res as Response).ok) setHealthStatus("ok"); else setHealthStatus("offline");
      } catch { if (alive) setHealthStatus("offline"); }
    }
    checkHealth();
    const id = window.setInterval(checkHealth, 15000);
    return () => { alive = false; clearInterval(id); };
  }, [splashReady]);
  useEffect(() => {
    if (!splashReady) return;
    if (connected) return;
    let alive = true;
    const tnNode: ServerNode = { id: "tn", label: "TN Server", host: "tn", port: 8000 };
    const ctrl = new AbortController();
    const to = window.setTimeout(() => ctrl.abort(), 2000);
    fetch(`http://${tnNode.host}:${tnNode.port}/api/v1/status`, { signal: ctrl.signal })
      .then(async (r) => {
        clearTimeout(to);
        if (!alive) return;
        if (r.ok) {
          try { const ok = await connect(tnNode); if (!alive) return; if (ok) { setTarget(tnNode); setConnected(true); setHealthStatus("ok"); return; } } catch { /* fallback */ }
          setHealthStatus("offline");
        } else setHealthStatus("offline");
      })
      .catch(() => { clearTimeout(to); if (alive) setHealthStatus("offline"); });
    return () => { alive = false; clearTimeout(to); ctrl.abort(); };
  }, [splashReady, connected, connect]);
  useEffect(() => { if (!splashReady) return; window.dispatchEvent(new CustomEvent("genio:ready")); }, [splashReady]);

  async function handleConnect(node: ServerNode) {
    try {
      const c = new AbortController(); const to = window.setTimeout(() => c.abort(), 3000);
      const res = await fetch(`http://${node.host}:${node.port}/api/v1/status`, { signal: c.signal }).catch(() => null);
      clearTimeout(to); if (!res || !(res as Response).ok) setHealthStatus("offline"); else setHealthStatus("ok");
    } catch { setHealthStatus("offline"); }
    const ok = await connect(node); if (ok) { setTarget(node); setConnected(true); setDrawerOpen(false); } return ok;
  }
  function handleDisconnect() { voice.stop(); disconnect(); setConnected(false); setTarget(null); setDrawerOpen(false); }
  // legacy handleSwitchNode removed — clean layout uses TopBar disconnect only
  function handleSendPrompt(text: string, attachments?: Attachment[]) {
    lastPromptRef.current = text; lastPromptFileRef.current = attachments; taskProc.setIsMinimized(false); voice.stop(); sendPrompt(text, attachments);
  }

  const mascotStatus = (() => {
    if (taskProc.result && agentStatus.kind === "completed") return "answering";
    if (agentStatus.kind === "thinking") return "thinking";
    if (agentStatus.kind === "executing") return "executing";
    if (isListening) return "listening";
    if (agentStatus.kind === "completed") return "completed";
    return "idle";
  })();
  const showV3Portal = (connected && target) || isGeminiCloud;
  const audioLevel = isListening ? 0.45 : 0;

  if (showGoogleAuth) {
    return (
      <div style={{ width: "100vw", height: "100vh", position: "relative", overflow: "hidden" }} className="bg-[#020B1E]">
        <ErrorBoundary name="IslamicPatterns"><IslamicPatterns /></ErrorBoundary>
        <GoogleAuthOnboarding onAuthed={() => setShowGoogleAuth(false)} onSkip={() => setShowGoogleAuth(false)} />
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
    <div className="fixed inset-0 h-[100dvh] w-screen overflow-hidden bg-[#020B1E]">
      {showSplash && <SplashScreen onReady={() => { setShowSplash(false); setSplashReady(true); }} />}

      {/* z-0 IslamicPatterns */}
      <ErrorBoundary name="IslamicPatterns">
        <div className="absolute inset-0 z-0">
          <IslamicPatterns />
        </div>
      </ErrorBoundary>

      {/* z-1 LivingMascot3D middle 60% */}
      {showV3Portal && (
        <div className="absolute inset-0 z-[1]">
          <ErrorBoundary name="LivingMascot3D">
            <Suspense fallback={<div className="absolute z-10 flex h-[35vh] w-full items-center justify-center left-1/2 top-[72px] -translate-x-1/2 md:top-[80px]"><HologramMascot status={mascotStatus} audioLevel={audioLevel} isMinimized={mascotStatus === "answering" || expanded} /></div>}>
              <LivingMascot3D status={mascotStatus} audioLevel={audioLevel} />
            </Suspense>
          </ErrorBoundary>
        </div>
      )}

      {/* z-20 TopBar: [☰] [SYSTEM LIVE] … [🔊 VOIX] */}
      <div className="absolute inset-x-0 top-0 z-20 flex h-[52px] items-center justify-between gap-2 border-b border-white/10 bg-slate-950/60 px-3 backdrop-blur-md md:px-6">
        <div className="flex items-center gap-2">
          <button
            aria-label="Menu"
            onClick={() => setDrawerOpen((v) => !v)}
            className="flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-white/80 backdrop-blur hover:bg-white/10"
          >
            ☰
          </button>
          {healthStatus !== "checking" && (
            <div className="flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[10px] backdrop-blur" style={{ borderColor: healthStatus === "ok" ? "rgba(52,211,153,0.3)" : "rgba(251,113,133,0.3)", background: healthStatus === "ok" ? "rgba(52,211,153,0.1)" : "rgba(251,113,133,0.1)", color: healthStatus === "ok" ? "#34d399" : "#fb7185" }}>
              <span className={`h-2 w-2 rounded-full ${healthStatus === "ok" ? "bg-emerald-400" : "bg-rose-400 animate-pulse"}`} />
              {healthStatus === "ok" ? "SYSTEM LIVE" : "ON-DEVICE"}
            </div>
          )}
          <span className="hidden font-mono text-[10px] text-white/40 md:inline">{isGeminiCloud ? "Gemini Cloud" : target?.label ?? "TN VPS"}</span>
        </div>
        <div className="flex items-center gap-2">
          {voice.noVoice && (
            <span className="rounded-full border border-amber-400/30 bg-amber-500/10 px-2.5 py-1 font-mono text-[10px] text-amber-300">🔇 voix indisponible</span>
          )}
          <button
            aria-label={voice.enabled ? "Voice on" : "Voice off"}
            onClick={() => voice.toggleEnabled()}
            className="flex items-center gap-1.5 rounded-full border px-3 py-1 font-mono text-[10px] backdrop-blur"
            style={{ borderColor: voice.enabled ? "rgba(34,211,238,0.3)" : "rgba(100,116,139,0.3)", background: voice.enabled ? "rgba(34,211,238,0.12)" : "rgba(15,23,42,0.6)", color: voice.enabled ? "#22d3ee" : "#94a3b8" }}
          >
            <span>{voice.enabled ? "🔊" : "🔇"}</span>
            {voice.enabled ? "voix" : "muet"}
          </button>
        </div>
      </div>

      {/* z-15 TaskMatrix compact collapsible max-h 28% — mobile top, desktop right panel */}
      {showV3Portal && (
        <div className="absolute inset-x-3 top-[60px] z-[15] md:left-auto md:right-6 md:top-[64px] md:w-[360px] md:max-w-[36vw]">
          <ErrorBoundary name="MatrixTaskScreen">
            <div className="pointer-events-auto max-h-[28vh] overflow-hidden rounded-2xl border border-white/10 bg-black/30 backdrop-blur-md md:max-h-[28vh]">
              <MatrixTaskScreen tasks={matrixTasks} expanded={expanded} onToggle={() => setExpanded((v) => !v)} />
            </div>
          </ErrorBoundary>
        </div>
      )}

      {/* Drawer overlay for ConnectionHub when not connected or ☰ pressed */}
      <AnimatePresence>
        {drawerOpen && (
          <div className="absolute inset-0 z-30 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
            <div className="relative w-full max-w-xl">
              <button onClick={() => setDrawerOpen(false)} className="absolute -right-2 -top-2 z-10 flex h-8 w-8 items-center justify-center rounded-full bg-white text-black">✕</button>
              <ConnectionHub onConnect={handleConnect} />
            </div>
          </div>
        )}
      </AnimatePresence>

      {/* ConnectionHub centered when not portal */}
      {!showV3Portal && (
        <div className="absolute inset-0 z-[15] flex items-center justify-center p-4">
          <ConnectionHub onConnect={handleConnect} />
        </div>
      )}

      {/* z-15 BottomSheet: status chip + gauges/cloud + chat transcript + input */}
      {showV3Portal && (
        <div className="absolute inset-x-0 bottom-0 z-[15] flex flex-col gap-2 border-t border-white/10 bg-slate-950/55 p-3 backdrop-blur-xl md:p-4" style={{ paddingBottom: "calc(0.75rem + env(safe-area-inset-bottom))" }}>
          <div className="flex flex-wrap items-center gap-2">
            {healthStatus !== "checking" && (
              <span className="rounded-full border px-2 py-0.5 font-mono text-[9px]" style={{ borderColor: healthStatus === "ok" ? "rgba(52,211,153,0.3)" : "rgba(251,113,133,0.3)", color: healthStatus === "ok" ? "#34d399" : "#fb7185" }}>
                {healthStatus === "ok" ? "● LIVE" : "● Tier A"}
              </span>
            )}
            <ErrorBoundary name="SystemMetrics-sheet">
              <SystemMetrics telemetry={telemetry ?? undefined} isCloud={isGeminiCloud && !telemetry} />
            </ErrorBoundary>
            <span className="ml-auto font-mono text-[9px] text-white/40">{deviceProfile.tier} · {engineDecision.mode} · {deviceProfile.ramGB}GB</span>
            <button onClick={handleDisconnect} className="rounded-full border border-white/10 px-2 py-0.5 font-mono text-[9px] text-white/60">Disconnect</button>
            <button onClick={() => kill()} className="rounded-full border border-rose-500/20 px-2 py-0.5 font-mono text-[9px] text-rose-300">Kill</button>
          </div>

          {/* transcript — compact, no page scroll overflow, max-h to keep input visible */}
          <div className="max-h-[22vh] min-h-[64px] overflow-auto rounded-xl border border-white/10 bg-black/30 p-2 backdrop-blur md:max-h-[24vh]">
            {chat.length === 0 ? (
              <p className="text-center font-mono text-[11px] text-white/30">Genio ready — tape un message ↓</p>
            ) : (
              <div className="space-y-1">
                {chat.slice(-12).map((c, i) => (
                  <div key={i} className={`font-mono text-[11px] ${c.type === "user" ? "text-cyan-200" : c.type === "error" ? "text-rose-300" : "text-white/80"}`}>
                    <span className="text-white/20">{c.type}:</span> {(c as unknown as { text?: string }).text ?? (c as unknown as { message?: string }).message ?? JSON.stringify(c).slice(0, 90)}
                  </div>
                ))}
              </div>
            )}
          </div>

          <BottomInputBar onSendPrompt={handleSendPrompt} onSendVoice={(dataB64, durationSec) => send({ action: "voice_wav", data_b64: dataB64, duration: durationSec, final: true })} />
        </div>
      )}

      {update && <UpdateModal version={update.version} notes={update.notes} onClose={() => setUpdate(null)} />}
    </div>
  );
}
