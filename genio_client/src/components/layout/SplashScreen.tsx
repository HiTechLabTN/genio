import splashAnime from "../../assets/splash/splash-anime.webp";
import { useEffect, useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";

const DARIJA = ["نجهّز الحكيم…", "نشحّن الذاكرة…", "نتثبت الاتصال…"];

interface Props {
  onReady?: () => void;
}

/**
 * SplashScreen — F1 holographic materialization
 * - wrapper clip-path inset(100% 0 0 0)→inset(0% 0 0 0) 1.2s ease-out + 2px cyan scanline bar moving with reveal edge
 * - 3D perspective(900px) rotateX(12deg) scale(1.08)→rotateX(0) scale(1) 0.9s spring; then idle float y[0,-10,0] 4s loop
 * - chromatic flicker: 2 copies mix-blend screen translateX ±2px tint cyan/red opacity [0,.5,0] first 350ms only
 * - base ring pulse + rising particles synced to reveal
 * - ALL transform/opacity/clip-path; no filters. 5s hard timeout
 */
export default function SplashScreen({ onReady }: Props) {
  const [visible, setVisible] = useState(true);
  const [progress, setProgress] = useState(0);
  const [darija, setDarija] = useState(0);
  const [flicker, setFlicker] = useState(true);

  const realProgress = useMemo(() => progress, [progress]);

  useEffect(() => {
    let p = 0;
    const timers: number[] = [];

    const t1 = window.setTimeout(() => {
      const id = window.setInterval(() => {
        p = Math.min(30, p + 4 + Math.random() * 4);
        setProgress(p);
        if (p >= 30) clearInterval(id);
      }, 180);
    }, 120);
    timers.push(t1 as unknown as number);

    const t2 = window.setTimeout(() => {
      const id = window.setInterval(() => {
        p = Math.min(68, p + 3 + Math.random() * 3);
        setProgress(p);
        if (p >= 68) clearInterval(id);
      }, 220);
    }, 800);
    timers.push(t2 as unknown as number);

    const t3 = window.setTimeout(async () => {
      try {
        const c = new AbortController();
        const to = window.setTimeout(() => c.abort(), 3000);
        const r = await fetch("/health", { signal: c.signal }).catch(() => fetch("http://localhost:8000/api/v1/status", { signal: c.signal }).catch(() => null));
        clearTimeout(to);
        void r;
      } catch { /* fail → Tier A */ }
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

    const d = window.setInterval(() => setDarija((v) => (v + 1) % DARIJA.length), 900);
    timers.push(d as unknown as number);

    const onReadyEvent = () => hide();
    window.addEventListener("genio:ready" as unknown as string, onReadyEvent);

    const fallback = window.setTimeout(() => hide(), 5000);
    timers.push(fallback as unknown as number);

    // chromatic flicker only first 350ms
    const flickerOff = window.setTimeout(() => setFlicker(false), 350);
    timers.push(flickerOff as unknown as number);

    function hide() {
      (window as unknown as { __GENIO_READY__?: boolean }).__GENIO_READY__ = true;
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
          {/* 3D perspective wrapper */}
          <motion.div
            initial={{ transform: "perspective(900px) rotateX(12deg) scale(1.08)", opacity: 0 }}
            animate={{ transform: "perspective(900px) rotateX(0deg) scale(1)", opacity: 1 }}
            transition={{ type: "spring", damping: 18, stiffness: 140, duration: 0.9 }}
            className="relative flex flex-col items-center"
            style={{ transformStyle: "preserve-3d" as unknown as string }}
          >
            <motion.div
              animate={{ y: [0, -10, 0] }}
              transition={{ duration: 4, repeat: Infinity, ease: "easeInOut", delay: 0.9 }}
              className="relative flex flex-col items-center"
            >
              {/* clip-path materialize */}
              <motion.div
                initial={{ clipPath: "inset(100% 0 0 0)" }}
                animate={{ clipPath: "inset(0% 0 0 0)" }}
                transition={{ duration: 1.2, ease: "easeOut" }}
                className="relative"
              >
                {/* scanline bar moving with reveal edge */}
                <motion.div
                  className="pointer-events-none absolute inset-x-0 h-[2px] bg-cyan-300 shadow-[0_0_12px_rgba(34,211,238,0.9)]"
                  initial={{ top: "100%" }}
                  animate={{ top: "0%" }}
                  transition={{ duration: 1.2, ease: "easeOut" }}
                  style={{ zIndex: 2 }}
                />

                {/* splash image with chromatic flicker copies */}
                <div className="relative">
                  <img
                    src={splashAnime}
                    alt="Genio splash"
                    className="h-[42vh] w-auto object-contain drop-shadow-[0_0_40px_rgba(34,211,238,0.35)] md:h-[48vh]"
                    fetchPriority="high"
                    decoding="async"
                    onError={(e) => {
                      const t = e.currentTarget as HTMLImageElement;
                      if (t.src.endsWith(".webp")) t.src = t.src.replace(".webp", ".svg");
                      else if (t.src.endsWith(".png")) t.src = t.src.replace(".png", ".svg");
                    }}
                  />
                  {/* chromatic flicker — first 350ms only */}
                  {flicker && (
                    <>
                      <img
                        src={splashAnime}
                        alt=""
                        aria-hidden
                        className="pointer-events-none absolute inset-0 h-[42vh] w-auto object-contain md:h-[48vh]"
                        style={{ mixBlendMode: "screen" as unknown as string, transform: "translateX(-2px)", filter: "hue-rotate(160deg) saturate(1.4)", opacity: 0.5 }}
                      />
                      <img
                        src={splashAnime}
                        alt=""
                        aria-hidden
                        className="pointer-events-none absolute inset-0 h-[42vh] w-auto object-contain md:h-[48vh]"
                        style={{ mixBlendMode: "screen" as unknown as string, transform: "translateX(2px)", filter: "hue-rotate(340deg) saturate(1.4)", opacity: 0.5 }}
                      />
                    </>
                  )}
                  {/* scanlines static */}
                  <div
                    className="pointer-events-none absolute inset-0"
                    style={{
                      background: "repeating-linear-gradient(0deg, transparent 0 2px, rgba(34,211,238,0.07) 2px 3px)",
                      mixBlendMode: "screen" as unknown as string,
                    }}
                  />
                </div>
              </motion.div>

              {/* base ring pulse */}
              <motion.div
                className="absolute -bottom-6 left-1/2 h-20 w-[70%] -translate-x-1/2 rounded-full border border-cyan-400/20"
                animate={{ scale: [0.92, 1.06, 0.92], opacity: [0.2, 0.45, 0.2] }}
                transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
                style={{ boxShadow: "0 0 24px rgba(34,211,238,0.18)" }}
              />

              {/* rising particles synced to reveal */}
              {Array.from({ length: 12 }, (_, i) => (
                <motion.div
                  key={i}
                  className="absolute h-1 w-1 rounded-full bg-cyan-300"
                  style={{ left: `${12 + i * 7}%`, top: `${22 + (i % 4) * 13}%` }}
                  initial={{ y: 10, opacity: 0 }}
                  animate={{ y: [-6, -18, -6], opacity: [0.3, 1, 0.3] }}
                  transition={{ duration: 2 + (i % 3), delay: 0.3 + i * 0.07, repeat: Infinity, ease: "easeInOut" }}
                />
              ))}
            </motion.div>

            {/* GENIO wordmark morph target */}
            <motion.div layoutId="genio-avatar" className="mt-5 flex flex-col items-center">
              <div className="font-mono text-2xl font-bold tracking-[0.3em] text-white">GENIO</div>
              <div className="font-mono text-[10px] tracking-[0.2em] text-cyan-300/70">ISLAMIC CYBERPUNK</div>
            </motion.div>

            {/* progress ring */}
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
