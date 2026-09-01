import { motion } from "framer-motion";
import { Globe, Shield, Sparkles, Loader2, LogIn, Zap } from "lucide-react";
import { useState } from "react";
import { signInWithGoogle, getGoogleProfile, hasGoogleAuth } from "../lib/googleAuth";

interface Props {
  onAuthed: (token: string) => void;
  onSkip?: () => void;
}

export default function GoogleAuthOnboarding({ onAuthed, onSkip }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleGoogle() {
    setError(null);
    setLoading(true);
    try {
      const token = await signInWithGoogle();
      onAuthed(token);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Google sign-in failed");
    } finally {
      setLoading(false);
    }
  }

  const profile = getGoogleProfile();
  const already = hasGoogleAuth();

  return (
    <div className="flex h-screen w-full items-center justify-center bg-void px-6 py-8">
      <motion.div
        initial={{ opacity: 0, y: 16, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        className="w-full max-w-md rounded-[2rem] border border-neon/20 bg-carbon/90 p-8 shadow-neon backdrop-blur"
      >
        <div className="mb-6 flex flex-col items-center text-center">
          <div className="relative mb-4">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-neon/20 to-violet-500/20 ring-1 ring-neon/30">
              <Sparkles className="h-8 w-8 text-neon" />
            </div>
            <span className="absolute -bottom-1 -right-1 flex h-6 w-6 items-center justify-center rounded-full bg-white shadow">
              <Globe className="h-4 w-4 text-[#4285F4]" />
            </span>
          </div>
          <h1 className="font-display text-xl font-bold text-slate-100">Welcome to Genio</h1>
          <p className="mt-2 max-w-sm font-mono text-xs leading-relaxed text-slate-400">
            Zero-config Gemini cloud. Sign in with Google to unlock your <span className="text-neon">Tunisian cyber-companion</span> instantly — no IP, no API key, no manual setup.
          </p>
        </div>

        {already && profile?.email && (
          <div className="mb-4 flex items-center gap-3 rounded-xl border border-ok/20 bg-ok/5 px-4 py-3">
            <img src={profile.picture || `https://api.dicebear.com/7.x/initials/svg?seed=${profile.email}`} alt="avatar" className="h-8 w-8 rounded-full" />
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-slate-100">{profile.name || profile.email}</p>
              <p className="truncate font-mono text-[11px] text-ok">Already signed in — tap Continue</p>
            </div>
          </div>
        )}

        <button
          onClick={handleGoogle}
          disabled={loading}
          className="flex w-full items-center justify-center gap-3 rounded-xl bg-white px-5 py-3 text-sm font-semibold text-slate-900 shadow hover:bg-slate-50 disabled:opacity-60"
        >
          {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : <Globe className="h-5 w-5 text-[#4285F4]" />}
          {already ? "Continue with Google" : "Sign in with Google"}
        </button>

        <div className="my-4 flex items-center gap-3">
          <div className="h-px flex-1 bg-slate-700/40" />
          <span className="font-mono text-[10px] text-slate-600">SECURE • GEMINI 2.0 FLASH • DARIJA</span>
          <div className="h-px flex-1 bg-slate-700/40" />
        </div>

        <div className="grid grid-cols-2 gap-2 font-mono text-[11px]">
          <span className="flex items-center gap-1.5 text-slate-500"><Zap className="h-3 w-3 text-neon" /> Streaming</span>
          <span className="flex items-center gap-1.5 text-slate-500"><Shield className="h-3 w-3 text-ok" /> Private</span>
        </div>

        {error && <p className="mt-4 rounded-lg border border-danger/20 bg-danger/10 px-3 py-2 text-center text-xs text-rose-300">{error}</p>}

        <div className="mt-6 flex justify-center gap-4">
          {onSkip && (
            <button onClick={onSkip} className="font-mono text-xs text-slate-500 hover:text-slate-300">
              Skip for now (manual IP)
            </button>
          )}
          <button onClick={() => onAuthed("mock-bypass-" + Date.now())} className="flex items-center gap-1 font-mono text-xs text-neon/70 hover:text-neon">
            <LogIn className="h-3 w-3" /> Demo bypass
          </button>
        </div>

        <p className="mt-4 text-center font-mono text-[10px] text-slate-600">
          By continuing you agree to HiTechLab encrypted Gemini gateway. Token stored securely via Tauri Store + localStorage.
        </p>
      </motion.div>
    </div>
  );
}

export function shouldShowGoogleAuth(): boolean {
  return !hasGoogleAuth();
}
