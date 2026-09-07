import { AnimatePresence, motion } from "framer-motion";
import { Mic, Paperclip, Send, X, MessageCircle, Sparkles } from "lucide-react";
import { Suspense, useEffect, useRef, useState } from "react";
import GoogleAuthOnboarding, { shouldShowGoogleAuth } from "./components/GoogleAuthOnboarding";
import PermissionOnboarding, { shouldShowOnboarding } from "./components/PermissionOnboarding";
import UpdateModal from "./components/UpdateModal";
import { useGenioSocket } from "./hooks/useGenioSocket";
import { useTaskProcessor } from "./hooks/useTaskProcessor";
import { checkForUpdates } from "./lib/updater";
import { hasGoogleAuth } from "./lib/googleAuth";
import type { Attachment, ServerNode } from "./lib/types";
import { ErrorBoundary } from "./components/v3";
import { useVoiceOutput } from "./components/v3/useVoiceOutput";
import IslamicPatterns from "./components/background/IslamicPatterns";
import IntroCinematic from "./components/intro/IntroCinematic";
import StateLoopAvatar from "./components/mascot/StateLoopAvatar";
import CinematicPortalSplash from "./components/layout/CinematicPortalSplash";
import { lazy } from "react";
const Genio3D = lazy(() => import("./components/mascot/Genio3D"));
import {
  setIntermediateTranscript,
  startVoiceRecording,
  stopVoiceRecording,
  speechRecognitionSupported,
  transcribeAudio,
} from "./lib/audio";

export default function App() {
  const [showGoogleAuth, setShowGoogleAuth] = useState(() => shouldShowGoogleAuth());
  const [showOnboarding, setShowOnboarding] = useState(() => shouldShowOnboarding());
  const [showIntro, setShowIntro] = useState(() => {
    try {
      const seen = localStorage.getItem("genio:intro:seen");
      const isAppPath = typeof window !== "undefined" && window.location.pathname.startsWith("/app");
      return !!(!seen && isAppPath);
    } catch {
      return false;
    }
  });
  useEffect(() => {
    if (!showGoogleAuth) return;
    if (!hasGoogleAuth()) return;
    const id = window.setTimeout(() => setShowGoogleAuth(false), 1200);
    return () => clearTimeout(id);
  }, [showGoogleAuth]);

  const [connected, setConnected] = useState(false);
  const [target, setTarget] = useState<ServerNode | null>(null);
  const hasToken = hasGoogleAuth();
  const isGeminiCloud = !connected;

  const {
    agentStatus: wsAgentStatus,
    telemetry,
    chat: wsChat,
    connect,
    disconnect,
    send,
    sendPrompt: wsSendPrompt,
    kill,
    connectionToast,
  } = useGenioSocket();

  const [geminiChat, setGeminiChat] = useState<typeof wsChat>([]);
  const [geminiStatus, setGeminiStatus] = useState<typeof wsAgentStatus>({ kind: "idle" });
  const chat = isGeminiCloud ? geminiChat : wsChat;
  const agentStatus = isGeminiCloud ? geminiStatus : wsAgentStatus;

  const sendPrompt = isGeminiCloud
    ? (text: string, attachments?: Attachment[]) => {
        setGeminiChat((prev) => [...prev.slice(-299), { type: "user", text, timestamp: Date.now() } as const]);
        if (!hasToken) {
          setGeminiChat((prev) => [
            ...prev.slice(-299),
            { type: "answer", text: "سجّل بـ Google باش تكمّل في السحاب" } as const,
            { type: "error", message: "NEED_GOOGLE_AUTH" } as const,
          ]);
          setGeminiStatus({ kind: "idle" });
          return true;
        }
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
                  const lastText = (last as { text?: string })?.text;
                  if (last?.type === "thought" && lastText === acc.slice(0, -chunk.text!.length)) {
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
                  return [...prev.slice(-299), { type: "answer", text: acc.trim() || "عسلامة! أنا جينيو، المهندس الذكي متاعك في هايتك لاب. فاش نجم نعاونك اليوم؟" }];
                });
                setGeminiStatus({ kind: "completed" });
                setTimeout(() => setGeminiStatus({ kind: "idle" }), 1200);
              }
            }
          } catch (e: unknown) {
            const msg = e instanceof Error ? e.message : String(e);
            if (msg === "NO_GOOGLE_TOKEN" || msg.includes("NO_GOOGLE_TOKEN")) {
              setGeminiChat((prev) => [...prev.slice(-299), { type: "answer", text: "سجّل بـ Google باش تكمّل في السحاب" } as const, { type: "error", message: "NEED_GOOGLE_AUTH" } as const]);
            } else if (msg === "GEMINI_PROXY_FAIL" || msg.includes("GEMINI_PROXY_FAIL") || msg.includes("السيرفر طايح")) {
              setGeminiChat((prev) => [...prev.slice(-299), { type: "answer", text: "مشكل في الاتصال بالسحاب — عاود جرّب" } as const]);
            } else if (msg.includes("السيرفر طايح")) setGeminiChat((prev) => [...prev.slice(-299), { type: "answer", text: msg }]);
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

  const isListening = agentStatus.kind === "thinking" || agentStatus.kind === "executing";
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
    if (taskProc.isProcessing) voice.stop();
  }, [taskProc.isProcessing, voice]);

  const [update, setUpdate] = useState<{ version: string; notes?: string } | null>(null);
  const lastPromptRef = useRef("");
  const [splashReady] = useState(true);
  // Splash MUST play on every visit to /app — no sessionStorage skip
  const [showCinematic, setShowCinematic] = useState<boolean>(() => true);
  const handleCinematicComplete = () => {
    setShowCinematic(false);
    // Seamless handoff: ensure background ready event
    window.dispatchEvent(new CustomEvent("genio:ready"));
  };
  const handleIntroDone = () => {
    try {
      localStorage.setItem("genio:intro:seen", "1");
    } catch {
      // ignore
    }
    setShowIntro(false);
  };
  const [healthStatus, setHealthStatus] = useState<"checking" | "ok" | "offline">("checking");

  const isNative = (() => {
    if (typeof window === "undefined") return false;
    const w = window as unknown as Record<string, unknown>;
    const hasTauri = !!(w.__TAURI__ || w.__TAURI_IPC__ || w.__TAURI_INTERNALS__);
    const cap = w.Capacitor as { isNative?: boolean; isNativePlatform?: () => boolean } | undefined;
    const capNative = !!(cap?.isNative || cap?.isNativePlatform?.());
    const isElectron = !!(w.process as { versions?: { electron?: string } } | undefined)?.versions?.electron;
    return hasTauri || capNative || isElectron;
  })();

  useEffect(() => {
    if (!isNative) return;
    let alive = true;
    const ric = (window as unknown as { requestIdleCallback?: (cb: () => void, opts?: { timeout: number }) => number })
      .requestIdleCallback;
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
  }, [isNative]);

  useEffect(() => {
    if (!splashReady) return;
    let alive = true;
    async function checkHealth() {
      try {
        const c = new AbortController();
        const to = window.setTimeout(() => c.abort(), 3000);
        const res = await fetch("/health", { signal: c.signal }).catch(() =>
          fetch("http://localhost:8000/api/v1/status", { signal: c.signal }).catch(() => null)
        );
        clearTimeout(to);
        if (!alive) return;
        if (res && (res as Response).ok) setHealthStatus("ok");
        else setHealthStatus("offline");
      } catch {
        if (alive) setHealthStatus("offline");
      }
    }
    void checkHealth();
    const id = window.setInterval(checkHealth, 15000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [splashReady]);

  useEffect(() => {
    if (!splashReady) return;
    if (connected) return;
    let alive = true;
    const defaultNode: ServerNode = !isNative
      ? { id: "hitech-cloud", label: "HiTech Cloud", host: "genio.hitech.tn", port: 443 }
      : { id: "tn", label: "TN Server", host: "tn", port: 8000 };
    const statusUrl = !isNative ? "/api/v1/status" : `http://${defaultNode.host}:${defaultNode.port}/api/v1/status`;
    const ctrl = new AbortController();
    const to = window.setTimeout(() => ctrl.abort(), 2500);
    fetch(statusUrl, { signal: ctrl.signal })
      .then(async (r) => {
        clearTimeout(to);
        if (!alive) return;
        if (r.ok) {
          try {
            const ok = await connect(defaultNode);
            if (!alive) return;
            if (ok) {
              setTarget(defaultNode);
              setConnected(true);
              setHealthStatus("ok");
              return;
            }
          } catch {
            // fallback silent
          }
          setHealthStatus("offline");
        } else setHealthStatus("offline");
      })
      .catch(() => {
        clearTimeout(to);
        if (alive) setHealthStatus("offline");
      });
    return () => {
      alive = false;
      clearTimeout(to);
      ctrl.abort();
    };
  }, [splashReady, connected, connect, isNative]);

  useEffect(() => {
    if (!splashReady) return;
    window.dispatchEvent(new CustomEvent("genio:ready"));
  }, [splashReady]);

  function handleDisconnect() {
    voice.stop();
    disconnect();
    setConnected(false);
    setTarget(null);
  }

  function handleSendPrompt(text: string, attachments?: Attachment[]) {
    lastPromptRef.current = text;
    taskProc.setIsMinimized(false);
    voice.stop();
    sendPrompt(text, attachments);
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
  // Audio reactivity: answering/executing + listening -> pulsing 0.38-0.63 for LiveGenio
  const [audioLevelBump, setAudioLevelBump] = useState(0);
  useEffect(() => {
    const speaking = mascotStatus === "answering" || mascotStatus === "executing" || isListening;
    if (!speaking) { setAudioLevelBump(0); return; }
    const id = window.setInterval(() => setAudioLevelBump(Math.random() * 0.22), 120);
    return () => window.clearInterval(id);
  }, [mascotStatus, isListening]);
  const baseLevel = mascotStatus === "answering" || mascotStatus === "executing" || isListening ? 0.38 : 0;
  const audioLevel = baseLevel + audioLevelBump;

  // FAB state
  const [fabOpen, setFabOpen] = useState(false);
  const [fabValue, setFabValue] = useState("");
  const [fabAttachments, setFabAttachments] = useState<Attachment[]>([]);
  const [fabRecording, setFabRecording] = useState(false);
  const [fabRecTimer, setFabRecTimer] = useState(0);
  const [fabMicError, setFabMicError] = useState<string | null>(null);
  const [fabDragOver, setFabDragOver] = useState(false);
  const fabInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!fabRecording) {
      setFabRecTimer(0);
      return;
    }
    const t = window.setInterval(() => setFabRecTimer((s) => s + 1), 1000);
    return () => window.clearInterval(t);
  }, [fabRecording]);

  useEffect(() => {
    if (fabOpen) window.setTimeout(() => fabInputRef.current?.focus(), 180);
  }, [fabOpen]);

  function fabHandleSubmit() {
    const text = fabValue.trim();
    if (!text && fabAttachments.length === 0) return;
    if (text) handleSendPrompt(text, fabAttachments.length ? fabAttachments : undefined);
    setFabValue("");
    setFabAttachments([]);
  }
  function fabHandleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      fabHandleSubmit();
    }
  }
  async function fabToggleMic() {
    setFabMicError(null);
    if (fabRecording) {
      const audio = await stopVoiceRecording();
      setFabRecording(false);
      if (audio?.blob && connected) {
        try {
          const base =
            target && target.host !== "genio.hitech.tn" && !target.host.includes("genio.hitech.tn")
              ? `http://${target.host}:${target.port}`
              : "";
          const apiBase = base || undefined;
          const key = target?.key;
          const transcribed = await transcribeAudio(audio.blob, apiBase, key);
          const finalText = (transcribed && transcribed.trim()) || audio?.transcript?.trim() || "";
          if (finalText) {
            setFabValue(finalText);
            if (audio) audio.transcript = finalText;
            // صوت بلا كتابة: ابعث مباشرة بعد التسجيل
            window.setTimeout(() => {
              if (finalText.trim()) {
                handleSendPrompt(finalText.trim(), fabAttachments.length ? fabAttachments : undefined);
                setFabValue("");
                setFabAttachments([]);
              }
            }, 300);
          }
        } catch {
          const fb = audio?.transcript?.trim() || "";
          if (fb) {
            setFabValue(fb);
            window.setTimeout(() => {
              handleSendPrompt(fb, fabAttachments.length ? fabAttachments : undefined);
              setFabValue("");
              setFabAttachments([]);
            }, 300);
          }
        }
      } else if (audio?.transcript && !fabValue.trim()) {
        const fb2 = audio.transcript.trim();
        setFabValue(fb2);
        window.setTimeout(() => {
          handleSendPrompt(fb2, fabAttachments.length ? fabAttachments : undefined);
          setFabValue("");
          setFabAttachments([]);
        }, 300);
      }
      if (audio && audio.dataB64) send({ action: "voice_wav", data_b64: audio.dataB64, duration: audio.durationSec, final: true });
    } else {
      setIntermediateTranscript("");
      try {
        await startVoiceRecording((text: string) => {
          setFabValue(text);
        });
        setFabRecording(true);
      } catch (err: unknown) {
        setFabRecording(false);
        setFabMicError(err instanceof Error ? err.message : "Microphone unavailable");
      }
    }
  }
  function fabHandleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files) return;
    void readFabFiles(Array.from(files));
    e.target.value = "";
  }
  function fabHandleDrop(e: React.DragEvent) {
    e.preventDefault();
    setFabDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length) void readFabFiles(files);
  }
  async function readFabFiles(files: File[]) {
    const newAtts = await Promise.all(files.map(readFabFile));
    setFabAttachments((prev) => [...prev, ...newAtts]);
  }
  function readFabFile(f: File): Promise<Attachment> {
    return new Promise((resolve) => {
      const id = crypto.randomUUID();
      const reader = new FileReader();
      const textual = (() => {
        if (!f.type) {
          const ext = f.name.split(".").pop()?.toLowerCase();
          return ["txt", "md", "html", "htm", "css", "js", "ts", "json", "py", "c", "cpp", "h", "java", "rs", "go", "rb", "sh", "yaml", "yml", "log", "csv", "xml", "sql", "ini", "toml"].includes(ext ?? "");
        }
        return f.type.startsWith("text/") || /json|xml|javascript|yaml/.test(f.type);
      })();
      if (textual) {
        reader.onload = () => {
          resolve({ id, name: f.name, type: f.type, dataB64: "", size: f.size, content: String(reader.result) });
        };
        reader.readAsText(f);
      } else {
        reader.onload = () => {
          const dataB64 = String(reader.result).split(",")[1] || "";
          resolve({ id, name: f.name, type: f.type, dataB64, size: f.size });
        };
        reader.readAsDataURL(f);
      }
    });
  }
  function fabRemoveAttachment(id: string) {
    setFabAttachments((prev) => prev.filter((a) => a.id !== id));
  }

  // silent telemetry keep-alive (no UI clutter) — ensures background logic runs
  useEffect(() => {
    // keep telemetry in memory silently, no render
    void telemetry;
    void healthStatus;
  }, [telemetry, healthStatus]);

  if (showGoogleAuth) {
    return (
      <div style={{ width: "100vw", height: "100vh", position: "relative", overflow: "hidden" }} className="bg-[#020B1E]">
        <ErrorBoundary name="IslamicPatterns">
          <IslamicPatterns />
        </ErrorBoundary>
        <GoogleAuthOnboarding onAuthed={() => setShowGoogleAuth(false)} onSkip={() => setShowGoogleAuth(false)} />
      </div>
    );
  }
  if (showOnboarding) {
    return (
      <div style={{ width: "100vw", height: "100vh", position: "relative", overflow: "hidden" }} className="bg-[#020B1E]">
        <ErrorBoundary name="IslamicPatterns">
          <IslamicPatterns />
        </ErrorBoundary>
        <PermissionOnboarding onComplete={() => setShowOnboarding(false)} onSkip={() => setShowOnboarding(false)} />
      </div>
    );
  }

  return (
    <div className="fixed inset-0 h-[100dvh] w-full overflow-hidden bg-[#020B1E]">
      {/* z-0 IslamicPatterns — stays mounted for seamless handoff, CinematicPortalSplash reuses same void #020B1E */}
      <ErrorBoundary name="IslamicPatterns">
        <div className="absolute inset-0 z-0">
          <IslamicPatterns />
        </div>
      </ErrorBoundary>

      {/* z-1 Full 3D Genio — photoréaliste 70k polys + PBR 2K + Rig 34 bones + 60FPS — fallback 2.5D */}
      {showV3Portal ? (
        <div className="absolute inset-0 z-[1]">
          <ErrorBoundary name="Genio3D">
            <Suspense fallback={<StateLoopAvatar status={mascotStatus} audioLevel={audioLevel} />}>
              <Genio3D audioLevel={audioLevel} status={mascotStatus} />
            </Suspense>
          </ErrorBoundary>
        </div>
      ) : (
        <div className="absolute inset-0 z-[1] flex items-center justify-center">
          <div className="rounded-2xl border border-white/10 bg-white/5 px-6 py-4 backdrop-blur-md">
            <p className="font-mono text-sm text-white/80">Connecting to Genio Cloud…</p>
          </div>
        </div>
      )}

      {/* Futuristic Chat FAB — فوق السبلاش من البداية z-60 */}
      <div className="absolute bottom-6 right-6 z-[60] flex flex-col items-end gap-3">
        <AnimatePresence>
          {fabOpen && (
            <motion.div
              key="fab-panel"
              initial={{ opacity: 0, y: 16, scale: 0.92 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 16, scale: 0.92 }}
              transition={{ type: "spring", stiffness: 420, damping: 28 }}
              className={`w-[min(92vw,360px)] overflow-hidden rounded-[1.5rem] border bg-white/10 backdrop-blur-md shadow-[0_8px_32px_rgba(0,0,0,0.4),0_0_40px_rgba(34,211,238,0.15)] ${fabDragOver ? "border-cyan-400/60 ring-2 ring-cyan-400/30" : "border-white/20"}`}
              onDragOver={(e) => {
                e.preventDefault();
                setFabDragOver(true);
              }}
              onDragLeave={() => setFabDragOver(false)}
              onDrop={fabHandleDrop}
            >
              {/* header — clean متصل badge, no raw URL/port */}
              <div className="flex items-center justify-between px-4 py-3">
                <div className="flex items-center gap-2">
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-cyan-400 to-blue-500 text-white shadow-[0_0_12px_rgba(34,211,238,0.5)]">
                    <Sparkles size={14} />
                  </span>
                  <span className="font-mono text-xs font-bold tracking-[0.18em] text-white">GENIO CHAT</span>
                  <span className="flex items-center gap-1.5 rounded-full border border-emerald-400/20 bg-emerald-500/10 px-2 py-0.5">
                    <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)] animate-pulse" />
                    <span className="font-mono text-[10px] font-bold tracking-[0.14em] text-emerald-200">متصل</span>
                  </span>
                </div>
                <button
                  aria-label="Close chat"
                  onClick={() => setFabOpen(false)}
                  className="flex h-7 w-7 items-center justify-center rounded-full border border-white/10 bg-white/5 text-white/70 backdrop-blur hover:bg-white/10 hover:text-white transition-colors"
                >
                  <X size={14} />
                </button>
              </div>

              {/* transcript */}
              <div className="mx-3 max-h-[32vh] min-h-[96px] overflow-auto rounded-xl border border-white/10 bg-black/25 p-3 backdrop-blur">
                {chat.length === 0 ? (
                  <p className="text-center font-mono text-[11px] leading-relaxed text-white/40">
                    ✨ Genio is listening — tape un message or speak ✨
                  </p>
                ) : (
                  <div className="space-y-2">
                    {chat
                      .filter((c) => {
                        const t = (c as unknown as { type?: string }).type;
                        if (t === "pong") return false;
                        if (t === "stats") return false;
                        if (t === "thought") return false;
                        // string contains pong heartbeats
                        const raw = JSON.stringify(c).toLowerCase();
                        if (raw.includes("pong")) {
                          const txt = ((c as unknown as { text?: string }).text ?? (c as unknown as { message?: string }).message ?? "").toLowerCase();
                          if (txt.includes("pong") || t === "pong") return false;
                        }
                        if (t !== "user" && t !== "answer") {
                          // hide internals except allowed special answers
                          const txt = (c as unknown as { text?: string }).text ?? "";
                          // allow the two Tunisian auth/cloud messages (answer type)
                          if (txt === "سجّل بـ Google باش تكمّل في السحاب" || txt === "مشكل في الاتصال بالسحاب — عاود جرّب") return true;
                          // hide tool_call, tool_result, artifact, error, session, attached, killed etc.
                          // only user + answer should render per spec
                          return false;
                        }
                        const txt2 = (c as unknown as { text?: string }).text ?? "";
                        if (/<thought[\s>]/i.test(txt2)) return false;
                        if (/^thought\s*:/i.test(txt2.trim())) return false;
                        return true;
                      })
                      .slice(-14)
                      .map((c, i) => {
                      const rawText = (c as unknown as { text?: string }).text;
                      const msg = (c as unknown as { message?: string }).message;
                      // sanitize thought blocks & prefixes from answer
                      const cleanText = (() => {
                        if (!rawText) return rawText;
                        let t = rawText;
                        t = t.replace(/<thought[^>]*>[\s\S]*?<\/thought>/gi, "");
                        t = t.replace(/<thought[^>]*>/gi, "");
                        t = t.replace(/<\/thought>/gi, "");
                        t = t.replace(/^thought\s*:\s*/im, "");
                        // strip leading stats JSON leakage
                        t = t.replace(/^\s*\{"type"\s*:\s*"stats"[\s\S]*?\}\s*/i, "");
                        return t.trim();
                      })();
                      if (!cleanText && !msg) return null;
                      if (cleanText === "سجّل بـ Google باش تكمّل في السحاب") {
                        return (
                          <div key={i} className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 p-3">
                            <p className="font-mono text-[12px] font-bold text-cyan-200">{cleanText}</p>
                            <button
                              onClick={() => setShowGoogleAuth(true)}
                              className="mt-2 rounded-full bg-white px-4 py-1.5 font-mono text-[11px] font-bold text-slate-900 hover:bg-slate-100 transition-colors"
                            >
                              سجّل بـ Google
                            </button>
                          </div>
                        );
                      }
                      if (msg === "NEED_GOOGLE_AUTH") return null;
                      if (cleanText === "مشكل في الاتصال بالسحاب — عاود جرّب") {
                        return (
                          <div key={i} className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-2">
                            <p className="font-mono text-[11px] text-amber-200">{cleanText}</p>
                            <button
                              onClick={() => lastPromptRef.current && handleSendPrompt(lastPromptRef.current)}
                              className="mt-1 rounded-full border border-amber-400/30 px-3 py-1 font-mono text-[10px] text-amber-200"
                            >
                              عاود جرّب
                            </button>
                          </div>
                        );
                      }
                      const isUser = c.type === "user";
                      return (
                        <div
                          key={i}
                          className={`rounded-lg px-2.5 py-1.5 font-mono text-[11px] leading-relaxed ${
                            isUser
                              ? "ml-6 bg-cyan-500/15 text-cyan-100 border border-cyan-400/20"
                              : "mr-6 bg-white/5 text-white/85 border border-white/10"
                          }`}
                        >
                          <span className="opacity-40 text-[9px]">{isUser ? "you" : "genio"}:</span> {cleanText ?? msg ?? ""}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* attachments preview */}
              {fabAttachments.length > 0 && (
                <div className="mx-3 mt-2 flex flex-wrap gap-1.5">
                  {fabAttachments.map((att) => (
                    <span
                      key={att.id}
                      className="flex items-center gap-1 rounded-full border border-cyan-400/20 bg-cyan-500/10 px-2 py-1 text-[10px] font-mono text-cyan-100"
                    >
                      <Paperclip size={10} />
                      <span className="max-w-[120px] truncate">{att.name}</span>
                      <button onClick={() => fabRemoveAttachment(att.id)} className="ml-0.5 text-white/50 hover:text-rose-300">
                        <X size={10} />
                      </button>
                    </span>
                  ))}
                </div>
              )}
              {fabDragOver && <p className="mx-3 mt-2 text-center font-mono text-[10px] text-cyan-300">drop files to attach</p>}

              {/* input row — glassmorphic */}
              <div className="flex items-center gap-2 p-3">
                <label className="flex h-9 w-9 shrink-0 cursor-pointer items-center justify-center rounded-xl border border-white/10 bg-white/5 text-white/60 backdrop-blur transition-all hover:border-cyan-400/30 hover:bg-white/10 hover:text-cyan-300" title="أضف ملف: فيديو، صورة، صوت، وثيقة">
                  <Paperclip size={16} />
                  <input type="file" multiple className="hidden" onChange={fabHandleFile} accept=".txt,.md,.py,.js,.ts,.json,.yaml,.yml,.log,.csv,.xml,.html,.css,.c,.cpp,.java,.rs,.go,.rb,.sh,.sql,.png,.jpg,.jpeg,.gif,.webp,.mp4,.webm,.mov,.avi,.mkv,.mp3,.wav,.m4a,.ogg,.pdf,.zip,.xlsx,.docx" />
                </label>

                <input
                  ref={fabInputRef}
                  value={fabValue}
                  onChange={(e) => setFabValue(e.target.value)}
                  onKeyDown={fabHandleKeyDown}
                  placeholder="أكتب أو تحدث بالصوت... 🎙️"
                  className="min-w-0 flex-1 rounded-xl border border-white/10 bg-white/5 px-3 py-2.5 text-sm text-white placeholder-white/30 outline-none backdrop-blur transition-all focus:border-cyan-400/40 focus:bg-white/10 font-mono"
                />

                <button
                  onClick={() => void fabToggleMic()}
                  aria-label={fabRecording ? "Stop recording" : "Microphone"}
                  className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border backdrop-blur transition-all ${
                    fabRecording
                      ? "border-rose-400 bg-rose-500/20 text-rose-200 shadow-[0_0_16px_rgba(244,63,94,0.4)] animate-pulse"
                      : "border-white/10 bg-white/5 text-white/60 hover:border-rose-400/30 hover:bg-white/10 hover:text-rose-300"
                  }`}
                >
                  <Mic size={16} />
                </button>

                <button
                  onClick={fabHandleSubmit}
                  aria-label="Send"
                  disabled={!fabValue.trim() && fabAttachments.length === 0}
                  className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border backdrop-blur transition-all ${
                    !fabValue.trim() && fabAttachments.length === 0
                      ? "border-white/5 bg-white/5 text-white/20"
                      : "border-cyan-400 bg-cyan-400/15 text-cyan-200 shadow-[0_0_16px_rgba(34,211,238,0.35)] hover:bg-cyan-400/20 active:scale-95"
                  } disabled:opacity-40`}
                >
                  <Send size={16} />
                </button>
              </div>

              {fabMicError && <p className="mx-3 pb-2 text-center font-mono text-[11px] text-rose-300">⚠ {fabMicError}</p>}
              {fabRecording && (
                <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mx-3 pb-3 text-center font-mono text-[10px] text-rose-300">
                  ● recording {fabRecTimer}s — {speechRecognitionSupported() ? "live transcription…" : "release to send"}
                </motion.p>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        <motion.button
          aria-label={fabOpen ? "Close chat" : "Open chat"}
          onClick={() => setFabOpen((v) => !v)}
          whileHover={{ scale: 1.06 }}
          whileTap={{ scale: 0.94 }}
          className="flex h-14 w-14 items-center justify-center rounded-full border border-white/20 bg-white/10 backdrop-blur-md shadow-[0_8px_24px_rgba(0,0,0,0.35),0_0_32px_rgba(34,211,238,0.25)] hover:bg-white/15 hover:shadow-[0_8px_24px_rgba(0,0,0,0.4),0_0_40px_rgba(34,211,238,0.35)] transition-colors"
        >
          <AnimatePresence mode="wait" initial={false}>
            {fabOpen ? (
              <motion.span key="x" initial={{ rotate: -90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: 90, opacity: 0 }} transition={{ duration: 0.18 }}>
                <X size={22} className="text-white" />
              </motion.span>
            ) : (
              <motion.span key="msg" initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.8, opacity: 0 }} transition={{ duration: 0.18 }} className="relative">
                <MessageCircle size={24} className="text-white" />
                <span className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.9)] animate-pulse" />
              </motion.span>
            )}
          </AnimatePresence>
        </motion.button>
      </div>

      {/* Silent background actions — no UI clutter */}
      <div className="pointer-events-none absolute inset-0 z-10">
        {/* Kill/Disconnect kept accessible via keyboard only, hidden */}
        <button
          onClick={() => kill()}
          aria-label="Kill agent"
          className="sr-only"
          tabIndex={-1}
        >
          Kill
        </button>
        <button onClick={handleDisconnect} aria-label="Disconnect" className="sr-only" tabIndex={-1}>
          Disconnect
        </button>
      </div>

      {update && isNative && <UpdateModal version={update.version} notes={update.notes} onClose={() => setUpdate(null)} />}
      {connectionToast && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="fixed bottom-24 left-1/2 z-50 -translate-x-1/2 rounded-full border border-amber-400/30 bg-amber-500/15 px-4 py-2 font-mono text-[11px] text-amber-200 backdrop-blur-md shadow-lg"
        >
          {connectionToast}
        </motion.div>
      )}
      {/* Cinematic Portal Splash — first load only, 3.4s timeline, seamless handoff to StateLoopAvatar */}
      {showCinematic && <CinematicPortalSplash onComplete={handleCinematicComplete} />}
      {showIntro && !showCinematic && <IntroCinematic onComplete={handleIntroDone} onSkip={handleIntroDone} />}
    </div>
  );
}
