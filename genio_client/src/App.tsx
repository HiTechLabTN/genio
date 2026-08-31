import { AnimatePresence } from "framer-motion";
import { useState } from "react";
import ConnectionHub from "./components/ConnectionHub";
import Dashboard from "./components/Dashboard";
import { useGenioSocket } from "./hooks/useGenioSocket";
import type { ServerNode } from "./lib/types";

export default function App() {
  const {
    telemetry,
    chat,
    screen,
    streaming,
    connect,
    disconnect,
    send,
    requestScreenshot,
    toggleScreenStream,
  } = useGenioSocket();
  const [connected, setConnected] = useState(false);
  const [target, setTarget] = useState<ServerNode | null>(null);

  async function handleConnect(node: ServerNode) {
    const ok = await connect(node);
    if (ok) {
      setTarget(node);
      setConnected(true);
    }
    return ok;
  }

  function handleDisconnect() {
    disconnect();
    setConnected(false);
    setTarget(null);
  }

  async function handleSwitchNode(host: string, label: string) {
    if (!target) return false;
    const next: ServerNode = { ...target, host, label };
    const ok = await connect(next);
    if (ok) setTarget(next);
    return ok;
  }

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-4 py-10">
      <div className="pointer-events-none absolute inset-0 -z-20 bg-grid-neon bg-grid [mask-image:radial-gradient(ellipse_70%_60%_at_50%_40%,black,transparent)]" />

      <AnimatePresence mode="wait">
        {connected && target ? (
          <Dashboard
            key="dashboard"
            node={target.label}
            host={target.host}
            apiKey={target.key}
            telemetry={telemetry}
            chat={chat}
            screen={screen}
            streaming={streaming}
            onDisconnect={handleDisconnect}
            onSendPrompt={(text) => send({ action: "prompt", text })}
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

      <footer className="mt-10 text-center text-[11px] font-mono text-slate-600">
        genio v2.0 client · tauri + react + tailwind · “the machine works for you”
      </footer>
    </div>
  );
}