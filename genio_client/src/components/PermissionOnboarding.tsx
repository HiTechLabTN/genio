import { motion } from "framer-motion";
import { Camera, Mic, Wifi, HardDrive, ShieldCheck, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { verifyCapabilities, requestAll, type PermissionSnapshot } from "../lib/permissions";

interface Props {
  onComplete: (snapshot: PermissionSnapshot) => void;
  onSkip?: () => void;
}

export default function PermissionOnboarding({ onComplete, onSkip }: Props) {
  const [snapshot, setSnapshot] = useState<PermissionSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [requesting, setRequesting] = useState(false);

  async function refresh() {
    setLoading(true);
    const snap = await verifyCapabilities();
    setSnapshot(snap);
    setLoading(false);
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleRequestAll() {
    setRequesting(true);
    try {
      const snap = await requestAll();
      setSnapshot(snap);
      if (snap.allGranted) {
        localStorage.setItem("genio:onboarding:done", "1");
        onComplete(snap);
      }
    } finally {
      setRequesting(false);
    }
  }

  function handleContinue() {
    if (snapshot) {
      if (snapshot.allGranted) localStorage.setItem("genio:onboarding:done", "1");
      onComplete(snapshot);
    }
  }

  if (loading) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-void text-slate-200">
        <Loader2 className="h-8 w-8 animate-spin text-neon" />
        <span className="ml-3 font-mono text-sm">checking device capabilities…</span>
      </div>
    );
  }

  const items = snapshot
    ? [
        { icon: Camera, label: "Camera", desc: "Front-camera face tracking (Chachia avatar gaze)", status: snapshot.camera },
        { icon: Mic, label: "Microphone", desc: "Native voice input (Darija STT)", status: snapshot.microphone },
        { icon: HardDrive, label: "Storage", desc: "Attachments & READ_MEDIA_*", status: snapshot.storage },
        { icon: Wifi, label: "Network", desc: "INTERNET & ACCESS_NETWORK_STATE", status: snapshot.network },
      ]
    : [];

  return (
    <div className="flex h-screen w-full flex-col items-center justify-center bg-void px-6 py-8">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-xl rounded-3xl border border-neon/20 bg-carbon/80 p-6 shadow-neon backdrop-blur"
      >
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-neon/10 ring-1 ring-neon/20">
            <ShieldCheck className="h-6 w-6 text-neon" />
          </div>
          <div>
            <h1 className="font-display text-lg font-bold text-slate-100">Permissions & Hardware</h1>
            <p className="font-mono text-xs text-slate-400">Genio needs a few capabilities to run natively on Android</p>
          </div>
        </div>

        <div className="space-y-3">
          {items.map(({ icon: Icon, label, desc, status }) => (
            <div key={label} className="flex items-center gap-3 rounded-xl border border-slate-700/40 bg-slate-950/40 px-4 py-3">
              <Icon className={`h-5 w-5 shrink-0 ${status.granted ? "text-ok" : "text-amber-400"}`} />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-slate-100">{label}</p>
                <p className="truncate font-mono text-[11px] text-slate-500">{desc} — {status.message}</p>
              </div>
              {status.granted ? <CheckCircle2 className="h-5 w-5 text-ok" /> : <XCircle className="h-5 w-5 text-rose-400" />}
            </div>
          ))}
        </div>

        <div className="mt-6 flex gap-3">
          <button
            onClick={handleRequestAll}
            disabled={requesting}
            className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-neon px-4 py-2.5 text-sm font-bold text-slate-950 hover:bg-neon-soft disabled:opacity-50"
          >
            {requesting ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
            {snapshot?.allGranted ? "Re-verify" : "Grant all"}
          </button>
          <button
            onClick={handleContinue}
            className="rounded-xl border border-slate-700/50 bg-slate-900/60 px-4 py-2.5 text-sm font-medium text-slate-300 hover:border-neon/30 hover:text-neon"
          >
            {snapshot?.allGranted ? "Continue" : "Continue anyway"}
          </button>
        </div>

        <p className="mt-4 text-center font-mono text-[10px] text-slate-500">
          Tauri Android will also enforce manifest permissions: CAMERA, RECORD_AUDIO, INTERNET, ACCESS_NETWORK_STATE, READ_MEDIA_*.
        </p>

        {onSkip && (
          <button onClick={onSkip} className="mx-auto mt-2 block font-mono text-[11px] text-slate-600 hover:text-slate-400">
            skip onboarding
          </button>
        )}
      </motion.div>
    </div>
  );
}

export function shouldShowOnboarding(): boolean {
  try {
    return localStorage.getItem("genio:onboarding:done") !== "1";
  } catch {
    return true;
  }
}
