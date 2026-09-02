import { useCallback, useEffect, useRef } from "react";

export function useVoiceOutput() {
  const utterRef = useRef<SpeechSynthesisUtterance | null>(null);

  const stop = useCallback(() => {
    try {
      window.speechSynthesis.cancel();
      utterRef.current = null;
    } catch { /* ignore */ }
  }, []);

  const speak = useCallback((text: string, lang = "en-US") => {
    if (!text?.trim()) return;
    // stop previous
    try { window.speechSynthesis.cancel(); } catch { /* ignore */ }
    // pick voice
    const utter = new SpeechSynthesisUtterance(text.slice(0, 900));
    utter.lang = lang;
    utter.rate = 0.97;
    utter.pitch = 1.02;
    // prefer Google voice if available
    try {
      const voices = window.speechSynthesis.getVoices();
      const pref = voices.find(v => /Google|Natural|Samantha/i.test(v.name)) || voices.find(v => v.lang.startsWith(lang.slice(0, 2))) || null;
      if (pref) utter.voice = pref;
    } catch { /* ignore */ }
    utterRef.current = utter;
    try { window.speechSynthesis.speak(utter); } catch { /* ignore */ }
  }, []);

  // prime voices (Chrome lazy-loads)
  useEffect(() => {
    try { window.speechSynthesis.getVoices(); } catch { /* ignore */ }
    const onVoices = () => { try { window.speechSynthesis.getVoices(); } catch { /* ignore */ } };
    window.speechSynthesis.addEventListener?.("voiceschanged", onVoices as EventListener);
    return () => {
      window.speechSynthesis.removeEventListener?.("voiceschanged", onVoices as EventListener);
      try { window.speechSynthesis.cancel(); } catch { /* ignore */ }
    };
  }, []);

  return { speak, stop };
}
