import { useCallback, useEffect, useRef, useState } from "react";

const STORAGE_KEY = "genio:voice:enabled";

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

  // detect missing speechSynthesis
  useEffect(() => {
    if (typeof window === "undefined" || !window.speechSynthesis) {
      setNoVoice(true);
    }
  }, []);

  // WebView autoplay: require first user gesture before any speak()
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

  const speak = useCallback((text: string, lang = "ar-TN") => {
    if (!text?.trim()) return;
    if (!enabled) return;
    if (!hasInteractedRef.current) return; // WebView autoplay rule — wait for first gesture
    if (typeof window === "undefined" || !window.speechSynthesis) {
      setNoVoice(true);
      return;
    }
    setNoVoice(false);
    // resume if paused (Chrome/WebView)
    try { window.speechSynthesis.resume(); } catch { /* ignore */ }
    try { window.speechSynthesis.cancel(); } catch { /* ignore */ }
    const utter = new SpeechSynthesisUtterance(text.slice(0, 900));
    // ar-TN primary, fr-FR fallback
    utter.lang = lang || "ar-TN";
    utter.volume = 1;
    utter.rate = 1;
    utter.pitch = 1.02;
    try {
      const voices = window.speechSynthesis.getVoices();
      // prefer ar-TN, else fr-FR
      const pref =
        voices.find((v) => v.lang.toLowerCase() === "ar-tn") ||
        voices.find((v) => v.lang.toLowerCase().startsWith("ar")) ||
        voices.find((v) => v.lang.toLowerCase() === "fr-fr") ||
        voices.find((v) => v.lang.toLowerCase().startsWith("fr")) ||
        voices.find((v) => /Google|Natural/i.test(v.name)) ||
        null;
      if (pref) {
        utter.voice = pref;
        utter.lang = pref.lang;
      } else if (!voices.length) {
        // voices not loaded yet — keep ar-TN, browser will fallback
        utter.lang = "ar-TN";
      }
    } catch { /* ignore */ }
    // if lang still unsupported, fallback to fr-FR on error
    utter.onerror = () => {
      if (utter.lang.toLowerCase().startsWith("ar")) {
        try {
          const retry = new SpeechSynthesisUtterance(text.slice(0, 900));
          retry.lang = "fr-FR";
          retry.volume = 1;
          retry.rate = 1;
          retry.pitch = 1.02;
          window.speechSynthesis.speak(retry);
        } catch { /* ignore */ }
      }
    };
    utterRef.current = utter;
    try { window.speechSynthesis.speak(utter); } catch { /* ignore */ }
  }, [enabled]);

  // prime voices (Chrome lazy-loads) — guard for Android WebView
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
