import { Globe, Shield, Sparkles, Zap } from "lucide-react";
import { motion } from "framer-motion";
import { useState } from "react";
import OAuthLoginButtons from "./OAuthLoginButtons";
import { getLang, t } from "../lib/lang";
import type { SessionUser } from "../lib/session";

interface Props {
  sessionUser: SessionUser | null;
  onAuthed: () => void;
  onSkip?: () => void;
}

/**
 * Login onboarding — backend-verified Google/GitHub OAuth.
 * Never forces login: the skip path always stays available, and an
 * already-logged-in user sees their verified account with Continue.
 * No mock tokens, no demo bypass anywhere in this flow.
 */
export default function GoogleAuthOnboarding({ sessionUser, onAuthed, onSkip }: Props) {
  const [lang] = useState(getLang);
  const [error, setError] = useState<string | null>(null);

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
          <h1 className="font-display text-xl font-bold text-slate-100">{t(lang, "auth.title")}</h1>
          <p className="mt-2 max-w-sm font-mono text-xs leading-relaxed text-slate-400">
            {t(lang, "auth.subtitle")}
          </p>
          <p className="mt-2 max-w-sm text-[11px] leading-relaxed text-slate-500">
            {t(lang, "auth.why")}
          </p>
        </div>

        {sessionUser ? (
          <div className="mb-4 flex items-center gap-3 rounded-xl border border-ok/20 bg-ok/5 px-4 py-3">
            {sessionUser.picture ? (
              <img src={sessionUser.picture} alt="avatar" className="h-8 w-8 rounded-full" />
            ) : (
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-neon/20 font-bold text-neon">
                {(sessionUser.name || sessionUser.email || "?").slice(0, 1)}
              </span>
            )}
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-slate-100">
                {sessionUser.name || sessionUser.email}
              </p>
              <p className="truncate font-mono text-[11px] text-ok">
                {t(lang, "auth.signed_in")} · {sessionUser.provider}
              </p>
            </div>
          </div>
        ) : (
          <OAuthLoginButtons onError={setError} />
        )}

        <div className="my-4 flex items-center gap-3">
          <div className="h-px flex-1 bg-slate-700/40" />
          <span className="font-mono text-[10px] text-slate-600">SECURE • DARIJA</span>
          <div className="h-px flex-1 bg-slate-700/40" />
        </div>

        <div className="grid grid-cols-2 gap-2 font-mono text-[11px]">
          <span className="flex items-center gap-1.5 text-slate-500"><Zap className="h-3 w-3 text-neon" /> Streaming</span>
          <span className="flex items-center gap-1.5 text-slate-500"><Shield className="h-3 w-3 text-ok" /> Private</span>
        </div>

        {error && (
          <div className="mt-4 rounded-lg border border-danger/20 bg-danger/10 px-3 py-2 text-center text-xs text-rose-300">
            <p>{error}</p>
          </div>
        )}

        <div className="mt-6 flex justify-center gap-4">
          {onSkip && (
            <button onClick={onSkip} className="font-mono text-xs text-slate-500 hover:text-slate-300">
              {t(lang, "auth.skip")}
            </button>
          )}
          {(sessionUser || undefined) && (
            <button
              onClick={onAuthed}
              className="font-mono text-xs text-neon/70 hover:text-neon"
            >
              {t(lang, "auth.continue")}
            </button>
          )}
        </div>

        <p className="mt-4 text-center font-mono text-[10px] text-slate-600">
          {t(lang, "auth.agree")}
        </p>
      </motion.div>
    </div>
  );
}

export function shouldShowGoogleAuth(): boolean {
  // Login is optional: show the onboarding only when there is no
  // verified session. Callers combine this with useSession().
  try {
    return localStorage.getItem("genio:auth:skip") !== "1";
  } catch {
    return true;
  }
}

export function markAuthSkipped(): void {
  try {
    localStorage.setItem("genio:auth:skip", "1");
  } catch {}
}
