import { AnimatePresence } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import ConnectionHub from "./components/ConnectionHub";
import Dashboard from "./components/Dashboard";
import UpdateModal from "./components/UpdateModal";
import { useGenioSocket } from "./hooks/useGenioSocket";
import { checkForUpdates } from "./lib/updater";
import type { Attachment, ServerNode } from "./lib/types";

export default function App() {
  const {
    agentStatus,
    telemetry,
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

  return (
    <div className="relative h-screen overflow-hidden">
      <div className="pointer-events-none absolute inset-0 -z-20 bg-grid-neon bg-grid [mask-image:radial-gradient(ellipse_70%_60%_at_50%_40%,black,transparent)]" />

      <AnimatePresence mode="wait">
        {connected && target ? (
          <Dashboard
            key="dashboard"
            node={target.label}
            host={target.host}
            apiKey={target.key}
            telemetry={telemetry}
            agentStatus={agentStatus}
            chat={chat}
            screen={screen}
            streaming={streaming}
            drawerOpen={drawerOpen}
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