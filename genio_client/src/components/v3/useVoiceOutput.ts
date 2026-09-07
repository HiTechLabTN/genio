import { useCallback, useEffect, useRef, useState } from "react";

const STORAGE_KEY = "genio:voice:enabled";

/**
 * Strip model internals but PRESERVE language content.
 * Never isolate Franco-Arab numerals (mta3 -> never leave "3").
 */
function stripInternals(input: string): string {
  let t = input.trim();
  if (!t) return "";
  t = t.replace(/<thought[^>]*>[\s\S]*?<\/thought>/gi, " ");
  t = t.replace(/<thought[^>]*>/gi, " ");
  t = t.replace(/<\/thought>/gi, " ");
  t = t.replace(/^thought\s*:\s*/gim, " ");
  t = t.replace(/\{"type"\s*:\s*"stats"[\s\S]*?\}/gi, " ");
  t = t.replace(/https?:\/\/\S+/g, " ");
  t = t.replace(/```[\s\S]*?```/g, " ");
  t = t.replace(/`[^`]*`/g, " ");
  t = t.replace(/<[^>]+>/g, " ");
  return t;
}

/** Keep only Arabic script for ar-TN TTS — remove whole Latin tokens including digits like mta3, n3awnek. */
function sanitizeForArabic(input: string): string {
  let t = stripInternals(input);
  // Remove any token containing Latin letters (Franco-Arab) entirely — prevents isolated "3 7"
  // e.g. mta3, t7eb, 3liha, n3awnek, chnowa -> removed as whole word
  t = t.replace(/\b[A-Za-z0-9]*[A-Za-z][A-Za-z0-9]*\b/g, " ");
  // Remove standalone latin punctuation artifacts
  t = t.replace(/[_#*]/g, " ");
  t = t.replace(/\s+/g, " ").trim();
  // If no Arabic letters remain, don't produce bare numerals
  const arabicChars = (t.match(/[\u0600-\u06FF]/g) || []).length;
  if (arabicChars < 2) {
    // check if remaining is just digits/punctuation -> suppress ("3 3 7")
    if (/^[\d\s\.,،؛:!?\-]+$/.test(t)) return "";
    if (t.length < 3) return "";
  }
  return t;
}

/** For Latin/French speech — keep Latin text but still strip internals. */
function sanitizeForFrench(input: string): string {
  let t = stripInternals(input);
  t = t.replace(/[_#*]{2,}/g, " ");
  t = t.replace(/\s+/g, " ").trim();
  if (/^[\d\s\.,،؛:!?\-]+$/.test(t)) return "";
  return t;
}

export function useVoiceOutput() {
  const utterRef = useRef<SpeechSynthesisUtterance | null>(null);
  const hasInteractedRef = useRef(false);
  const [noVoice, setNoVoice] = useState(false);
  const [enabled, setEnabled] = useState<boolean>(() => {
    try {
      const v = localStorage.getItem(STORAGE_KEY);
      return v === null ? true : v === "1" || v === "true";
    } catch {
      return true;
    }
  });

  useEffect(() => {
    if (typeof window === "undefined" || !window.speechSynthesis) {
      setNoVoice(true);
    }
  }, []);

  useEffect(() => {
    if (hasInteractedRef.current) return;
    const mark = () => {
      hasInteractedRef.current = true;
      window.removeEventListener("pointerdown", mark);
      window.removeEventListener("touchstart", mark);
      window.removeEventListener("click", mark);
      window.removeEventListener("keydown", mark);
    };
    window.addEventListener("pointerdown", mark, { once: true });
    window.addEventListener("touchstart", mark, { once: true });
    window.addEventListener("click", mark, { once: true });
    window.addEventListener("keydown", mark, { once: true });
    return () => {
      window.removeEventListener("pointerdown", mark);
      window.removeEventListener("touchstart", mark);
      window.removeEventListener("click", mark);
      window.removeEventListener("keydown", mark);
    };
  }, []);

  const toggleEnabled = useCallback(() => {
    setEnabled((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
      } catch { /* ignore */ }
      if (!next) {
        try { window.speechSynthesis?.cancel(); } catch { /* ignore */ }
      }
      return next;
    });
  }, []);

  const stop = useCallback(() => {
    try {
      window.speechSynthesis?.cancel();
      utterRef.current = null;
    } catch { /* ignore */ }
  }, []);

  const speak = useCallback((text: string) => {
    if (!text?.trim()) return;
    if (!enabled) return;
    if (!hasInteractedRef.current) return;
    if (typeof window === "undefined" || !window.speechSynthesis) {
      setNoVoice(true);
      return;
    }
    setNoVoice(false);
    try { window.speechSynthesis.resume(); } catch { /* ignore */ }
    try { window.speechSynthesis.cancel(); } catch { /* ignore */ }

    const baseStripped = stripInternals(text);
    if (!baseStripped) return;
    const hasArabic = /[\u0600-\u06FF]/.test(baseStripped);
    const hasLatin = /[A-Za-z]/.test(baseStripped);

    let cleaned = "";
    let lang: string = "ar-TN";
    let voiceLangPref: "ar" | "fr" = "ar";

    if (hasArabic) {
      cleaned = sanitizeForArabic(baseStripped);
      if (!cleaned) return;
      lang = "ar-TN";
      voiceLangPref = "ar";
    } else if (hasLatin) {
      cleaned = sanitizeForFrench(baseStripped);
      if (!cleaned) return;
      // Never speak bare numerals — if cleaned is just digits after latin strip, abort
      if (/^[\d\s]+$/.test(cleaned)) return;
      lang = "fr-FR";
      voiceLangPref = "fr";
    } else {
      // No Arabic nor Latin — likely digits/punctuation only -> don't speak numerals
      if (/^[\d\s\.,،؛:!?\-]+$/.test(baseStripped)) return;
      cleaned = baseStripped.slice(0, 900);
      lang = "ar-TN";
      voiceLangPref = "ar";
    }

    const utter = new SpeechSynthesisUtterance(cleaned.slice(0, 900));
    utter.lang = lang;
    utter.volume = 1;
    utter.rate = 0.96;
    utter.pitch = 1.02;
    try {
      const voices = window.speechSynthesis.getVoices();
      let pref: SpeechSynthesisVoice | null = null;
      if (voiceLangPref === "ar") {
        pref =
          voices.find((v) => v.lang.toLowerCase() === "ar-tn") ||
          voices.find((v) => v.lang.toLowerCase() === "ar-sa") ||
          voices.find((v) => v.lang.toLowerCase().startsWith("ar")) ||
          null;
        if (pref) { utter.voice = pref; utter.lang = pref.lang; }
        else if (!voices.length) utter.lang = "ar-TN";
      } else {
        pref =
          voices.find((v) => v.lang.toLowerCase() === "fr-fr") ||
          voices.find((v) => v.lang.toLowerCase().startsWith("fr")) ||
          voices.find((v) => /French/i.test(v.name)) ||
          null;
        if (pref) { utter.voice = pref; utter.lang = pref.lang; }
        else utter.lang = "fr-FR";
      }
    } catch { /* ignore */ }
    utter.onerror = () => {
      try {
        const retry = new SpeechSynthesisUtterance(cleaned.slice(0, 900));
        retry.volume = 1; retry.rate = 0.96; retry.pitch = 1.02;
        if (voiceLangPref === "ar") {
          retry.lang = "ar-SA";
          try {
            const vs = window.speechSynthesis.getVoices();
            const arSa = vs.find((v) => v.lang.toLowerCase() === "ar-sa") || vs.find((v) => v.lang.toLowerCase().startsWith("ar"));
            if (arSa) { retry.voice = arSa; retry.lang = arSa.lang; }
          } catch { /* ignore */ }
        } else {
          retry.lang = "fr-FR";
        }
        window.speechSynthesis.speak(retry);
      } catch { /* ignore */ }
    };
    utterRef.current = utter;
    try { window.speechSynthesis.speak(utter); } catch { /* ignore */ }
  }, [enabled]);

  useEffect(() => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    try { window.speechSynthesis.getVoices(); } catch { /* ignore */ }
    const onVoices = () => { try { window.speechSynthesis?.getVoices(); } catch { /* ignore */ } };
    window.speechSynthesis?.addEventListener?.("voiceschanged", onVoices as EventListener);
    return () => {
      window.speechSynthesis?.removeEventListener?.("voiceschanged", onVoices as EventListener);
      try { window.speechSynthesis?.cancel(); } catch { /* ignore */ }
    };
  }, []);

  return { speak, stop, enabled, toggleEnabled, noVoice, hasInteracted: hasInteractedRef };
}
