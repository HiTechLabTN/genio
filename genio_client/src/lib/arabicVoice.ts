/**
 * Arabic voice output — Genio speaks Tunisian answers aloud.
 *
 * Routes Arabic-script answers to the local Arabic TTS sidecar
 * (127.0.0.1:5051, MMS-TTS-ara, MSA phonetics) instead of the browser
 * SpeechSynthesis path (which has no Arabic voice on most Linux
 * desktops) or the Qwen3-TTS service (which cannot do Arabic — honest
 * 422 by design). French/English keep their existing paths untouched.
 *
 * Contract: never rejects silently — every failure returns a Tunisian
 * error string so the UI can show it next to the readable answer, with
 * a retry affordance. Text always remains the source of truth.
 */

const AR_TTS_URL =
  (typeof window !== "undefined" &&
    (window as unknown as { __GENIO_AR_TTS_URL?: string })
      .__GENIO_AR_TTS_URL) ||
  "http://127.0.0.1:5051";

export const AR_TTS_HEALTH_URL = `${AR_TTS_URL}/health`;

const ARABIC_RE = /[\u0600-\u06FF]/;

export function hasArabicScript(text: string): boolean {
  return ARABIC_RE.test(text || "");
}

export type ArabicSpeakResult =
  | { ok: true }
  | { ok: false; error: string };

let arAudio: HTMLAudioElement | null = null;

export function stopArabic(): void {
  try {
    arAudio?.pause();
    arAudio = null;
  } catch {
    /* ignore */
  }
}

/** Minimal pre-check mirroring the sidecar contract (avoid doomed requests). */
export function arabicSpeakable(text: string): { ok: true } | { ok: false; error: string } {
  const t = (text || "").trim();
  if (!t) return { ok: false, error: "ما فما حتى نص باش ننطقوه." };
  if (t.length > 2000)
    return { ok: false, error: "النص طويل برشة على النطق — جرّب تقسّمو." };
  if (!hasArabicScript(t))
    return { ok: false, error: "الصوت العربي يقرا النص المكتوب بالعربية." };
  return { ok: true };
}

export async function speakArabic(text: string): Promise<ArabicSpeakResult> {
  const pre = arabicSpeakable(text);
  if (!pre.ok) return pre;
  try {
    arAudio?.pause();
  } catch {
    /* ignore */
  }
  let res: Response;
  try {
    res = await fetch(`${AR_TTS_URL}/synthesize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text.trim().slice(0, 2000), language: "ar" }),
    });
  } catch {
    return {
      ok: false,
      error: "خدمة الصوت العربي ما تردّش — تأكد إنها خدامة وعاود جرّب.",
    };
  }
  if (res.status === 503)
    return {
      ok: false,
      error: "موديل الصوت العربي موش محمّل — استنى شوية وعاود.",
    };
  if (!res.ok)
    return {
      ok: false,
      error: "ما نجمتش ننطق الإجابة — تنجم تقراها مكتوبة ونعاودو المحاولة.",
    };
  try {
    const blob = await res.blob();
    if (!blob || blob.size < 1000)
      return { ok: false, error: "الصوت الراجع فارغ — عاود المحاولة." };
    const url = URL.createObjectURL(blob);
    arAudio = new Audio(url);
    arAudio.onended = () => URL.revokeObjectURL(url);
    await arAudio.play();
    return { ok: true };
  } catch {
    return { ok: false, error: "ما نجمتش نشغّل الصوت — عاود المحاولة." };
  }
}

export async function arabicVoiceAvailable(timeoutMs = 4000): Promise<boolean> {
  try {
    const ctl = new AbortController();
    const t = window.setTimeout(() => ctl.abort(), timeoutMs);
    const res = await fetch(AR_TTS_HEALTH_URL, { signal: ctl.signal });
    window.clearTimeout(t);
    return res.ok;
  } catch {
    return false;
  }
}
