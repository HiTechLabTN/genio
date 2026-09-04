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
import BrainActivity from "./components/hud/BrainActivity";
import MatrixTaskScreen from "./components/hud/MatrixTaskScreen";
import SplashScreen from "./components/layout/SplashScreen";
import BottomInputBar from "./components/BottomInputBar";
import { lazy, Suspense, useCallback } from "react";
const LivingMascot3D = lazy(() => import("./components/mascot/LivingMascot3D"));

/*
 * S1 AUDIT — App.tsx root sections before cleanup:
 * 1) SplashScreen z-50
 * 2) IslamicPatterns z-0
 * 3) Health chip (left top) + Voice toggle (right top)
 * 4) MatrixTaskScreen z-8 (full 28vh→75vh panel)
 * 5) LivingMascot3D z-1 inset-0
 * 6) Chat wrapper z-15: border glow circle + AnimatePresence → Dashboard vs ConnectionHub vs UpdateModal + Chronos hint
 * 7) SystemMetrics/BrainActivity z-20 bottom-right
 * 8) TaskMinimizer fixed top-right
 *
 * Dashboard.tsx legacy stack:
 * - Header (duplicate SYSTEM LIVE + metrics chips + SELFIE MODE) → duplicate TopBar
 * - Engine tier bar (gray spacer band border-b bg-carbon/30)
 * - Main flex: avatar zone h-[35vh] dot-grid + radial portals + CyberAvatar 340 (legacy)
 * - Chat history h-[65vh] + HolographicHud when busy + ActivityBar
 * - RightDrawer
 * - BottomInputBar with GENIO APP footer gray band
 *
 * GenioShell.tsx (unused duplication):
 * - IslamicPatterns + MatrixTaskScreen + HologramMascot + chat children + SystemMetrics (all duplicated)
 *
 * S1 DELETE: dot-grid avatar zone (Dashboard idle-avatar), duplicate Header,
 * full-height panels (Dashboard h-screen flex-col, Chat h65vh), gray spacer bands (engine tier bar,
 * BottomInputBar GENIO APP footer, Header border-b bg-slate-950/80). KEEP hooks (chat/WS/telemetry/voice/face tracking).
 */

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
  // chronos hint removed S1 (gray band deleted)

  const {
    agentStatus: wsAgentStatus,
    telemetry,
    telemetryStale,
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
  const [, setDrawerOpen] = useState(false);
  const [update, setUpdate] = useState<{ version: string; notes?: string } | null>(null);
  const lastPromptRef = useRef("");
  const lastPromptFileRef = useRef<Attachment[] | undefined>(undefined);
  const [splashReady, setSplashReady] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [healthStatus, setHealthStatus] = useState<"checking" | "ok" | "offline">("checking");

  useEffect(() => {
    let alive = true;
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
          try {
            const ok = await connect(tnNode);
            if (!alive) return;
            if (ok) {
              setTarget(tnNode);
              setConnected(true);
              setHealthStatus("ok");
              return;
            }
          } catch { /* fallback */ }
          setHealthStatus("offline");
        } else {
          setHealthStatus("offline");
        }
      })
      .catch(() => {
        clearTimeout(to);
        if (alive) setHealthStatus("offline");
      });
    return () => { alive = false; clearTimeout(to); ctrl.abort(); };
  }, [splashReady, connected, connect]);

  useEffect(() => {
    if (!splashReady) return;
    window.dispatchEvent(new CustomEvent("genio:ready"));
  }, [splashReady]);

  async function handleConnect(node: ServerNode) {
    try {
      const c = new AbortController();
      const to = window.setTimeout(() => c.abort(), 3000);
      const res = await fetch(`http://${node.host}:${node.port}/api/v1/status`, { signal: c.signal }).catch(() => null);
      clearTimeout(to);
      if (!res || !(res as Response).ok) setHealthStatus("offline");
      else setHealthStatus("ok");
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
    taskProc.setIsMinimized(false);
    voice.stop();
    sendPrompt(text, attachments);
  }
  function handleContinue() {
    if (lastPromptRef.current) sendPrompt(lastPromptRef.current, lastPromptFileRef.current);
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

  const handleScrollStick = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 140;
    (e.currentTarget as unknown as { _stick?: boolean })._stick = nearBottom;
  }, []);

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

  // S1: legacy stacked blocks (Dashboard.Header, avatar h35vh dot-grid, h-screen panels, gray bands) DELETED
  // Hooks kept: chat/WS/telemetry/voice/face tracking. Minimal Transcript kept for verify.

  return (
    <div style={{ width: "100vw", height: "100vh", position: "relative", overflow: "hidden" }} className="bg-[#020B1E]">
      {showSplash && <SplashScreen onReady={() => { setShowSplash(false); setSplashReady(true); }} />}
      <ErrorBoundary name="IslamicPatterns">
        <div className="absolute inset-0 z-0">
          <IslamicPatterns />
        </div>
      </ErrorBoundary>

      {healthStatus !== "checking" && (
        <div className="absolute left-3 top-3 z-30 flex items-center gap-2 rounded-full border px-3 py-1 font-mono text-[10px] backdrop-blur" style={{ borderColor: healthStatus === "ok" ? "rgba(52,211,153,0.3)" : "rgba(251,113,133,0.3)", background: healthStatus === "ok" ? "rgba(52,211,153,0.1)" : "rgba(251,113,133,0.1)", color: healthStatus === "ok" ? "#34d399" : "#fb7185" }}>
          <span className={`h-2 w-2 rounded-full ${healthStatus === "ok" ? "bg-emerald-400" : "bg-rose-400 animate-pulse"}`} />
          {healthStatus === "ok" ? "SYSTEM LIVE" : "ON-DEVICE • Tier A"}
          {healthStatus === "offline" && <button onClick={() => window.location.reload()} className="ml-2 underline">retry</button>}
        </div>
      )}
      <button
        aria-label={voice.enabled ? "Voice on" : "Voice off"}
        onClick={() => voice.toggleEnabled()}
        className="absolute right-3 top-3 z-30 flex items-center gap-1.5 rounded-full border px-3 py-1 font-mono text-[10px] backdrop-blur transition"
        style={{
          borderColor: voice.enabled ? "rgba(34,211,238,0.3)" : "rgba(100,116,139,0.3)",
          background: voice.enabled ? "rgba(34,211,238,0.12)" : "rgba(15,23,42,0.6)",
          color: voice.enabled ? "#22d3ee" : "#94a3b8",
        }}
      >
        <span>{voice.enabled ? "🔊" : "🔇"}</span>
        {voice.enabled ? "voix" : "muet"}
      </button>
      {voice.noVoice && (
        <div className="absolute right-3 top-10 z-30 rounded-full border border-amber-400/30 bg-amber-500/10 px-3 py-1 font-mono text-[10px] text-amber-300 backdrop-blur">
          🔇 voix indisponible
        </div>
      )}

      {showV3Portal && (
        <div className="pointer-events-none absolute inset-x-3 top-16 z-[8] md:inset-x-6 md:top-20">
          <ErrorBoundary name="MatrixTaskScreen">
            <div className="pointer-events-auto">
              <MatrixTaskScreen tasks={matrixTasks} expanded={expanded} onToggle={() => setExpanded((v) => !v)} />
            </div>
          </ErrorBoundary>
        </div>
      )}

      {showV3Portal && (
        <div className="absolute inset-0 z-[1]">
          <ErrorBoundary name="LivingMascot3D">
            <Suspense fallback={<div className="absolute z-10 flex h-[35vh] w-full items-center justify-center left-1/2 top-[72px] -translate-x-1/2 md:top-[80px]"><HologramMascot status={mascotStatus} audioLevel={audioLevel} isMinimized={mascotStatus === "answering" || expanded} /></div>}>
              <LivingMascot3D status={mascotStatus} audioLevel={audioLevel} />
            </Suspense>
          </ErrorBoundary>
        </div>
      )}

      {/* S1: Dashboard legacy stack DELETED — replaced by minimal transcript + input (no Header, no avatar h35vh, no full-height panels, no gray bands) */}
      <div className="relative z-[15] flex h-full w-full flex-col">
        <AnimatePresence mode="wait">
          {showV3Portal ? (
            <div key="v3-portal" className="flex h-screen w-full flex-col">
              <div className="flex min-h-0 flex-1 flex-col pt-[36vh] md:pt-[38vh] p-4">
                <div className="flex-1 overflow-auto custom-scrollbar rounded-2xl border border-white/10 bg-black/20 p-3 backdrop-blur" onScroll={handleScrollStick}>
                  {chat.length === 0 ? (
                    <p className="text-center font-mono text-xs text-white/40">Genio ready — S1 minimal transcript (S2 will be BottomSheet)</p>
                  ) : (
                    chat.slice(-20).map((c, i) => (
                      <div key={i} className="py-1 font-mono text-[12px] text-white/80 truncate">
                        <span className="text-white/30">{c.type}: </span>{(c as unknown as { text?: string }).text ?? (c as unknown as { message?: string }).message ?? JSON.stringify(c).slice(0, 80)}
                      </div>
                    ))
                  )}
                  {telemetryStale && <p className="text-amber-300 text-xs">TN stale</p>}
                </div>
                <BottomInputBar onSendPrompt={handleSendPrompt} onSendVoice={(dataB64, durationSec) => send({ action: "voice_wav", data_b64: dataB64, duration: durationSec, final: true })} />
                <div className="mt-2 flex gap-2">
                  <button onClick={handleContinue} className="text-xs text-cyan-300 underline">Continue</button>
                  <button onClick={() => kill()} className="text-xs text-rose-300 underline">Kill</button>
                  <button onClick={handleDisconnect} className="text-xs text-slate-400 underline">Disconnect</button>
                  <button onClick={() => handleSwitchNode("tn", "TN Server")} className="text-xs text-slate-400 underline">Switch TN</button>
                </div>
                {deviceProfile && <p className="font-mono text-[10px] text-white/30">Tier {deviceProfile.tier} · {engineDecision.mode} · {deviceProfile.ramGB}GB · {isGeminiCloud ? "Gemini Cloud" : target?.host}</p>}
              </div>
            </div>
          ) : (
            <ConnectionHub key="hub" onConnect={handleConnect} />
          )}
        </AnimatePresence>
        {update && <UpdateModal version={update.version} notes={update.notes} onClose={() => setUpdate(null)} />}
      </div>

      {showV3Portal && (
        <div className="pointer-events-none absolute bottom-3 right-3 z-20 flex flex-col items-end gap-3 md:bottom-4 md:right-6">
          <div className="pointer-events-auto hidden md:block">
            <ErrorBoundary name="SystemMetrics"><SystemMetrics telemetry={telemetry ?? undefined} isCloud={isGeminiCloud && !telemetry} /></ErrorBoundary>
          </div>
          <div className="pointer-events-auto md:hidden">
            <ErrorBoundary name="SystemMetrics-mobile"><SystemMetrics telemetry={telemetry ?? undefined} isCloud={isGeminiCloud && !telemetry} /></ErrorBoundary>
          </div>
          <ErrorBoundary name="BrainActivity"><BrainActivity active={agentStatus.kind === "thinking" || agentStatus.kind === "executing"} /></ErrorBoundary>
        </div>
      )}
    </div>
  );
}
