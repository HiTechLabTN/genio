import { AnimatePresence } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import ConnectionHub from "./components/ConnectionHub";
import Dashboard from "./components/Dashboard";
import PermissionOnboarding, { shouldShowOnboarding } from "./components/PermissionOnboarding";
import UpdateModal from "./components/UpdateModal";
import { useGenioSocket } from "./hooks/useGenioSocket";
import { checkForUpdates } from "./lib/updater";
import { useDeviceProfile } from "./lib/deviceProfiler";
import { decideEngine } from "./lib/adaptiveEngine";
import type { Attachment, ServerNode } from "./lib/types";

export default function App() {
  const {
    agentStatus,
    telemetry,
    telemetryStale,
    chat,
    screen,
    streaming,
    connect,
    disconnect,
    send,
    sendPrompt,
    kill,
    requestScreenshot,
    toggleScreenStream,
  } = useGenioSocket();

  const [connected, setConnected] = useState(false);
  const [target, setTarget] = useState<ServerNode | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [update, setUpdate] = useState<{ version: string; notes?: string } | null>(null);
  const lastPromptRef = useRef("");
  const lastPromptFileRef = useRef<Attachment[] | undefined>(undefined);
  const [showOnboarding, setShowOnboarding] = useState(() => shouldShowOnboarding());
  const deviceProfile = useDeviceProfile();
  const engineDecision = decideEngine();

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
    sendPrompt(text, attachments);
  }

  function handleContinue() {
    if (lastPromptRef.current) {
      sendPrompt(lastPromptRef.current, lastPromptFileRef.current);
    }
  }

  if (showOnboarding) {
    return (
      <PermissionOnboarding
        onComplete={() => setShowOnboarding(false)}
        onSkip={() => setShowOnboarding(false)}
      />
    );
  }

  return (
    <div className="relative h-screen overflow-hidden">
      <div className="pointer-events-none absolute inset-0 -z-20 bg-grid-neon bg-grid [mask-image:radial-gradient(ellipse_70%_60%_at_50%_40%,black,transparent)]" />
      {/* Adaptive engine tier badge — reactive to deviceProfiler */}
      <div className="pointer-events-none absolute right-3 top-3 z-50 hidden select-none items-center gap-2 rounded-full border border-neon/15 bg-carbon/70 px-3 py-1 font-mono text-[10px] backdrop-blur md:flex">
        <span className={`h-2 w-2 rounded-full ${engineDecision.mode === "local" ? "bg-ok shadow-[0_0_8px_rgba(52,211,153,0.8)]" : "bg-amber-400 shadow-[0_0_8px_rgba(251,146,60,0.8)]"}`} />
        <span className="text-slate-300">Tier {deviceProfile.tier}</span>
        <span className="text-slate-500">·</span>
        <span className={engineDecision.mode === "local" ? "text-ok" : "text-amber-300"}>{engineDecision.mode === "local" ? "On-Device" : "Cloud"}</span>
        <span className="text-slate-600">{deviceProfile.ramGB}GB · {deviceProfile.cores} cores</span>
      </div>

      <AnimatePresence mode="wait">
        {connected && target ? (
          <Dashboard
            key="dashboard"
            node={target.label}
            host={target.host}
            apiKey={target.key}
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
            onDisconnect={handleDisconnect}
            onKill={kill}
            onContinue={handleContinue}
            onSendPrompt={handleSendPrompt}
            onSendVoice={(dataB64, durationSec) =>
              send({ action: "voice_wav", data_b64: dataB64, duration: durationSec, final: true })
            }
            onRequestScreenshot={requestScreenshot}
            onToggleScreenStream={toggleScreenStream}
            onSwitchNode={handleSwitchNode}
          />
        ) : (
          <ConnectionHub key="hub" onConnect={handleConnect} />
        )}
      </AnimatePresence>

      {update && <UpdateModal version={update.version} notes={update.notes} onClose={() => setUpdate(null)} />}
    </div>
  );
}