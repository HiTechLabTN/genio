import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import mascotCutout from "../../assets/mascot/mascot_cutout.webp";
import mascotFallback from "../../assets/mascot/mascot_cutout.png";

type Props = {
  onComplete: () => void;
};

/**
 * CinematicPortalSplash — Seamless layered composite, no rectangles
 * LAYER 0: fixed void + radial + arabesque (static, only neon glows)
 * Mascot: transparent cutout with fade mask, emerges from hologram center
 * Auto-exit 3.8s max
 */
export default function CinematicPortalSplash({ onComplete }: Props) {
  const [visible, setVisible] = useState<boolean>(true);
  const [cardLoaded, setCardLoaded] = useState<boolean>(false);
  const [wave, setWave] = useState<boolean>(false);
  const [progress, setProgress] = useState<number>(0);

  useEffect(() => {
    const tWave = window.setTimeout(() => setWave(true), 1600);
    const tCard = window.setTimeout(() => setCardLoaded(true), 1800);
    const tComplete = window.setTimeout(() => {
      setVisible(false);
      window.setTimeout(() => onComplete(), 500);
    }, 2200);
    // Strict 3.8s hard fallback timeout — never freezes
    const tFailsafe = window.setTimeout(() => {
      setVisible(false);
      onComplete();
    }, 3800);
    // Progress bar 0→100% over 2200ms — أسرع
    const start = performance.now();
    const duration = 2200;
    let raf = 0;
    const tick = (now: number) => {
      const p = Math.min(100, ((now - start) / duration) * 100);
      setProgress(p);
      if (p < 100) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);

    return () => {
      window.clearTimeout(tWave);
      window.clearTimeout(tCard);
      window.clearTimeout(tComplete);
      window.clearTimeout(tFailsafe);
      cancelAnimationFrame(raf);
    };
  }, [onComplete]);

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          key="cinematic-portal-splash"
          initial={{ opacity: 1 }}
          exit={{ opacity: 0, transition: { duration: 0.6, ease: "easeInOut" } }}
          className="fixed inset-0 z-[55] flex flex-col items-center justify-center overflow-hidden bg-[#020B1E] w-full h-full"
          aria-label="Genio cinematic portal intro"
        >
          {/* LAYER 0 — Full-bleed seamless cyberpunk background — 100% static */}
          <div className="fixed inset-0 w-full h-full bg-[#020B1E]" />
          <div
            className="pointer-events-none fixed inset-0 w-full h-full opacity-[0.55]"
            style={{
              background:
                "radial-gradient(ellipse at 50% 72%, rgba(34,211,238,0.16) 0%, transparent 62%), radial-gradient(ellipse at 35% 28%, rgba(255,215,0,0.10) 0%, transparent 55%), radial-gradient(ellipse at 50% 50%, rgba(99,102,241,0.06) 0%, transparent 72%)",
            }}
          />
          {/* Islamic/Arabesque full-screen z-[1] neon oscillating cyan <-> gold */}
          <motion.div
            className="pointer-events-none fixed inset-0 z-[1] w-full h-full"
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.35 }}
            transition={{ duration: 0.9, ease: "easeOut" }}
            aria-hidden
          >
            <motion.div
              className="absolute inset-0"
              animate={{ opacity: [0.85, 1, 0.85] }}
              transition={{ duration: 2.8, repeat: Infinity, ease: "easeInOut" }}
            >
              <svg className="h-full w-full" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid slice" aria-hidden>
                <defs>
                  <pattern id="splash-arabesque" width="140" height="140" patternUnits="userSpaceOnUse">
                    <g stroke="#00E5FF" strokeWidth="1.25" fill="none" opacity={1}>
                      <path d="M70 16 L76 32 L92 32 L80 43 L84 60 L70 50 L56 60 L60 43 L48 32 L64 32 Z" />
                      <path d="M70 16 L70 60 M48 32 L92 32 M53 20 L87 48 M87 20 L53 48" opacity={0.55} />
                    </g>
                    <g stroke="#FFD700" strokeWidth="0.95" fill="none" opacity={0.9}>
                      <path d="M70 36 L73 43 L80 43 L74 48 L76 55 L70 51 L64 55 L66 48 L60 43 L67 43 Z" />
                    </g>
                  </pattern>
                  <radialGradient id="splash-glow" cx="50%" cy="50%" r="72%">
                    <stop offset="0%" stopColor="rgba(0,229,255,0.14)" />
                    <stop offset="52%" stopColor="rgba(255,215,0,0.06)" />
                    <stop offset="100%" stopColor="transparent" />
                  </radialGradient>
                </defs>
                <rect width="100%" height="100%" fill="url(#splash-arabesque)" />
                <rect width="100%" height="100%" fill="url(#splash-glow)" />
              </svg>
            </motion.div>
            <motion.div
              className="absolute inset-0"
              animate={{ opacity: [0.42, 0.78, 0.42] }}
              transition={{ duration: 2.8, repeat: Infinity, ease: "easeInOut" }}
              style={{
                background:
                  "radial-gradient(ellipse at 50% 45%, rgba(255,215,0,0.18) 0%, transparent 62%), radial-gradient(ellipse at 30% 70%, rgba(0,229,255,0.12) 0%, transparent 55%)",
                mixBlendMode: "screen" as never,
              }}
            />
          </motion.div>
          <div className="pointer-events-none fixed inset-0" style={{ background: "radial-gradient(ellipse at center, transparent 56%, rgba(0,0,0,0.58) 100%)" }} />

          {/* UNIFIED FRAME — mascot + hologram same coordinate (no rectangle) */}
          <div className="relative flex flex-col items-center justify-end h-[85vh] max-h-[850px] w-auto mx-auto select-none bg-transparent border-0 shadow-none">
            {/* Hologram platform anchored directly under sneakers */}
            <div className="absolute bottom-2 left-1/2 -translate-x-1/2 pointer-events-none z-0" style={{ perspective: "800px" } as React.CSSProperties}>
              <div className="relative flex items-center justify-center" style={{ transform: "rotateX(72deg)", transformStyle: "preserve-3d" } as React.CSSProperties}>
                {/* Ring 1 - Outer w-72 */}
                <motion.div
                  className="w-72 h-72 rounded-full border border-cyan-400/60"
                  style={{ boxShadow: "0 0 25px rgba(34,211,238,0.7), inset 0 0 12px rgba(34,211,238,0.22)" }}
                  animate={{ rotateZ: 360 }}
                  transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
                />
                {/* Ring 2 - Middle */}
                <motion.div
                  className="absolute w-52 h-52 rounded-full border-2 border-white/80"
                  style={{ boxShadow: "0 0 30px rgba(255,255,255,0.8), 0 0 30px rgba(34,211,238,0.55)" }}
                  animate={{ rotateZ: -360 }}
                  transition={{ duration: 5, repeat: Infinity, ease: "linear" }}
                />
                {/* Ring 3 - Core Glow */}
                <div className="absolute w-32 h-32 rounded-full bg-cyan-400/20 blur-md" style={{ boxShadow: "0 0 40px rgba(34,211,238,0.9), inset 0 0 14px rgba(255,255,255,0.55)" }}>
                  <div className="absolute inset-0 rounded-full blur-[2px]" style={{ background: "radial-gradient(circle at center, rgba(255,255,255,0.9) 0%, transparent 62%)" }} />
                  <div className="absolute left-1/2 top-1/2 h-[42px] w-[42px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-white/90" style={{ boxShadow: "0 0 14px rgba(255,255,255,1), 0 0 22px rgba(34,211,238,0.7)" }} />
                </div>
              </div>
              {/* Floor glow dissolving */}
              <div className="absolute left-1/2 top-[68%] h-[14px] w-[160%] -translate-x-1/2 rounded-full blur-[12px] opacity-50" style={{ background: "radial-gradient(ellipse at center, rgba(0,229,255,0.22) 0%, transparent 72%)" }} />
            </div>

            {/* Mascot Cutout — transparent, no box, fade mask so bottom dissolves into glow */}
            <motion.div
              initial={{ y: 120, scale: 0.8, opacity: 0 }}
              animate={{ y: 0, scale: 1, opacity: 1 }}
              transition={{ type: "spring", damping: 18, stiffness: 110, delay: 1.15 }}
              className="relative z-10 flex flex-col items-center bg-transparent border-0 shadow-none"
              style={{ transformOrigin: "50% 88%" }}
            >
              <motion.div
                animate={wave ? { rotateZ: [0, -7, 7, -5, 0], y: [0, -4, 0, -3, 0] } : { y: [0, -5, 0] }}
                transition={wave ? { duration: 1.0, ease: "easeInOut" } : { duration: 4.2, repeat: Infinity, ease: "easeInOut", delay: 2.6 }}
                className="relative bg-transparent border-0 shadow-none"
                style={{ transformOrigin: "50% 72%" } as React.CSSProperties}
              >
                <img
                  src={mascotCutout}
                  alt="Genio"
                  className="relative z-10 h-[72vh] max-h-[700px] w-auto object-contain pointer-events-none select-none bg-transparent border-0 shadow-none"
                  draggable={false}
                  style={{
                    WebkitMaskImage: "linear-gradient(to bottom, black 75%, transparent 100%)",
                    maskImage: "linear-gradient(to bottom, black 75%, transparent 100%)",
                  } as React.CSSProperties}
                  onError={(e) => {
                    const t = e.currentTarget as HTMLImageElement;
                    if (t.src.endsWith(".webp")) t.src = mascotFallback;
                  }}
                />
              </motion.div>
            </motion.div>
          </div>

          {/* GENIO title — no card, no box, pure glowing text + progress */}
          <motion.div
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, ease: "easeOut", delay: 1.95 }}
            className="absolute bottom-[4%] left-1/2 z-20 flex -translate-x-1/2 flex-col items-center bg-transparent border-0"
          >
            <motion.div
              animate={
                cardLoaded
                  ? { filter: "blur(0px) contrast(1.3) brightness(1.15)", opacity: 1 }
                  : { filter: ["blur(8px)", "blur(4px)", "blur(10px)", "blur(6px)"], opacity: 0.9 }
              }
              transition={cardLoaded ? { duration: 0.22, ease: "easeOut" } : { duration: 1.8, repeat: Infinity, ease: "easeInOut", times: [0, 0.35, 0.7, 1] as never }}
              className="flex flex-col items-center bg-transparent border-0"
              style={cardLoaded ? { willChange: "filter" } : { willChange: "filter" }}
            >
              <div className="font-mono text-[22px] font-black tracking-[0.32em] text-white" style={{ textShadow: "0 0 18px rgba(255,255,255,0.45), 0 0 32px rgba(0,229,255,0.35)" }}>
                GENIO <span className="font-light tracking-[0.22em] text-cyan-200">v4.0</span>
              </div>
              <div className="mt-1 font-mono text-[10px] font-bold tracking-[0.28em] text-[#FFD700]" style={{ textShadow: "0 0 12px rgba(255,215,0,0.38)" }}>
                CYBER-COMPANION
              </div>
              <motion.div
                initial={{ scaleX: 0, opacity: 0 }}
                animate={{ scaleX: 1, opacity: cardLoaded ? 0.85 : 0.55 }}
                transition={{ duration: 0.55, ease: "easeOut", delay: 2.45 }}
                className="mt-3 h-px w-28 bg-gradient-to-r from-transparent via-white/65 to-transparent"
              />
              <p className="mt-2 font-mono text-[9px] tracking-[0.16em] text-white/45">ISLAMIC CYBERPUNK • TUNISIA</p>
            </motion.div>
            {/* شريط التحميل — خط رفيع بلا صندوق */}
            <div className="mt-4 w-56 h-[3px] overflow-hidden bg-transparent">
              <motion.div
                className="h-full rounded-full"
                style={{
                  background: "linear-gradient(90deg, #00E5FF 0%, #FFD700 50%, #00E5FF 100%)",
                  boxShadow: "0 0 10px rgba(34,211,238,0.7), 0 0 20px rgba(255,215,0,0.35)",
                  width: `${progress}%`,
                }}
                initial={{ width: "0%" }}
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.12, ease: "linear" }}
              />
            </div>
            <div className="mt-1.5 flex items-center gap-2">
              <span className="font-mono text-[9px] tracking-[0.18em] text-white/50">{Math.round(progress)}%</span>
              <span className="font-mono text-[8px] tracking-[0.14em] text-cyan-200/60">{progress < 100 ? "جاري التحميل..." : "جاهز!"}</span>
            </div>
            <AnimatePresence>
              {!cardLoaded && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 0.85 }}
                  exit={{ opacity: 0, transition: { duration: 0.22 } as never }}
                  transition={{ delay: 2.0, duration: 0.3 } as never}
                  className="mt-2 flex items-center gap-1.5"
                >
                  {[0, 1, 2].map((i) => (
                    <motion.span
                      key={i}
                      className="h-1.5 w-1.5 rounded-full bg-cyan-200/70"
                      animate={{ opacity: [0.25, 1, 0.25], scale: [0.9, 1.15, 0.9] } as never}
                      transition={{ duration: 1.0, repeat: Infinity, ease: "easeInOut", delay: i * 0.18 } as never}
                    />
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
