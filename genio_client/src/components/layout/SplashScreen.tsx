import splashAnime from "../../assets/splash/splash-anime.png";
import { useEffect, useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";

const DARIJA = ["نجهّز الحكيم…", "نشحّن الذاكرة…", "نتثبت الاتصال…"];

interface Props {
  onReady?: () => void;
}

/**
 * SplashScreen — #10 anime hologram + GENIO wordmark
 * - Native layer: Capacitor native splash + Electron BrowserWindow backgroundColor #0a0e1a (handled natively)
 * - Web layer: overlay z-50, #10 centered, holographic materialize-in (clip-path bottom→top 1.2s + scanlines + cyan particles; transform/opacity only)
 * - Real boot progress (webview ready, providers init, daemon /health) → thin cyan progress ring under GENIO wordmark
 * - Darija status cycling
 * - Hide on 'genio:ready' spring fade+scale-out; hard 5s timeout fallback
 * - Mascot layoutId="genio-avatar" → morphs into HUD mascot
 */
export default function SplashScreen({ onReady }: Props) {
  const [visible, setVisible] = useState(true);
  const [progress, setProgress] = useState(0);
  const [darija, setDarija] = useState(0);

  const realProgress = useMemo(() => progress, [progress]);

  useEffect(() => {
    let p = 0;
    const timers: number[] = [];

    // Stage 1: webview ready (0→30)
    const t1 = window.setTimeout(() => {
      const id = window.setInterval(() => {
        p = Math.min(30, p + 4 + Math.random() * 4);
        setProgress(p);
        if (p >= 30) clearInterval(id);
      }, 180);
    }, 120);
    timers.push(t1 as unknown as number);

    // Stage 2: providers init (30→68)
    const t2 = window.setTimeout(() => {
      const id = window.setInterval(() => {
        p = Math.min(68, p + 3 + Math.random() * 3);
        setProgress(p);
        if (p >= 68) clearInterval(id);
      }, 220);
    }, 800);
    timers.push(t2 as unknown as number);

    // Stage 3: daemon /health pre-check 3s (68→100) — never crash, fallback Tier A
    const t3 = window.setTimeout(async () => {
      try {
        const c = new AbortController();
        const to = window.setTimeout(() => c.abort(), 3000);
        const r = await fetch("/health", { signal: c.signal }).catch(() => fetch("http://localhost:8000/api/v1/status", { signal: c.signal }).catch(() => null));
        clearTimeout(to);
        void r;
      } catch { /* F1: fail → Tier A, keep progress */ }
      const id = window.setInterval(() => {
        p = Math.min(100, p + 6 + Math.random() * 4);
        setProgress(p);
        if (p >= 100) {
          clearInterval(id);
          window.setTimeout(() => hide(), 420);
        }
      }, 140);
    }, 1500);
    timers.push(t3 as unknown as number);

    // Darija cycling every 900ms
    const d = window.setInterval(() => setDarija((v) => (v + 1) % DARIJA.length), 900);
    timers.push(d as unknown as number);

    // genio:ready listener
    const onReadyEvent = () => hide();
    window.addEventListener("genio:ready" as unknown as string, onReadyEvent);

    // hard 5s fallback
    const fallback = window.setTimeout(() => hide(), 5000);
    timers.push(fallback as unknown as number);

    function hide() {
      setVisible(false);
      window.setTimeout(() => onReady?.(), 520);
    }

    return () => {
      timers.forEach((id) => clearTimeout(id));
      clearInterval(d);
      window.removeEventListener("genio:ready" as unknown as string, onReadyEvent);
    };
  }, [onReady]);

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 1 }}
          exit={{ opacity: 0, scale: 0.98, transition: { duration: 0.5, ease: "easeInOut" } }}
          className="fixed inset-0 z-50 flex flex-col items-center justify-center overflow-hidden bg-[#0a0e1a]"
        >
          {/* holographic materialize container */}
          <motion.div
            initial={{ clipPath: "inset(100% 0 0 0)", opacity: 0 }}
            animate={{ clipPath: "inset(0 0 0 0)", opacity: 1 }}
            transition={{ duration: 1.2, ease: "easeOut" }}
            className="relative flex flex-col items-center"
          >
            {/* splash image #10 */}
            <div className="relative">
              <img
                src={splashAnime}
                alt="Genio splash"
                className="h-[42vh] w-auto object-contain drop-shadow-[0_0_40px_rgba(34,211,238,0.35)] md:h-[48vh]"
                onError={(e) => {
                  const t = e.currentTarget as HTMLImageElement;
                  if (t.src.endsWith(".png")) t.src = t.src.replace(".png", ".svg");
                }}
              />
              {/* scanlines — transform only */}
              <div
                className="pointer-events-none absolute inset-0"
                style={{
                  background: "repeating-linear-gradient(0deg, transparent 0 2px, rgba(34,211,238,0.07) 2px 3px)",
                  mixBlendMode: "screen",
                }}
              />
              {/* cyan particles */}
              {Array.from({ length: 12 }, (_, i) => (
                <motion.div
                  key={i}
                  className="absolute h-1 w-1 rounded-full bg-cyan-300"
                  style={{ left: `${12 + i * 7}%`, top: `${18 + (i % 4) * 14}%` }}
                  animate={{ y: [0, -12, 0], opacity: [0.4, 1, 0.4] }}
                  transition={{ duration: 2 + (i % 3), delay: i * 0.12, repeat: Infinity, ease: "easeInOut" }}
                />
              ))}
            </div>

            {/* GENIO wordmark with mascot layoutId morph target */}
            <motion.div layoutId="genio-avatar" className="mt-4 flex flex-col items-center">
              <div className="font-mono text-2xl font-bold tracking-[0.3em] text-white">GENIO</div>
              <div className="font-mono text-[10px] tracking-[0.2em] text-cyan-300/70">ISLAMIC CYBERPUNK</div>
            </motion.div>

            {/* thin cyan progress ring */}
            <div className="relative mt-6 h-14 w-14">
              <svg width={56} height={56} className="-rotate-90">
                <circle cx={28} cy={28} r={24} stroke="rgba(255,255,255,0.08)" strokeWidth={3} fill="none" />
                <motion.circle
                  cx={28}
                  cy={28}
                  r={24}
                  stroke="#22d3ee"
                  strokeWidth={3}
                  fill="none"
                  strokeLinecap="round"
                  strokeDasharray={`${(realProgress / 100) * 150.8} 150.8`}
                  style={{ transition: "stroke-dasharray 0.4s ease" }}
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center font-mono text-xs font-bold text-white">
                {Math.round(realProgress)}%
              </div>
            </div>

            {/* Darija cycling */}
            <motion.div
              key={darija}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              className="mt-3 font-mono text-sm text-amber-200/90"
              dir="rtl"
            >
              {DARIJA[darija]}
            </motion.div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
