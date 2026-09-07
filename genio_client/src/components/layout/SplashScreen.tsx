import genioHero from "../../assets/mascot/genio-hero.png";
import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface Props {
  onReady?: () => void;
}

/**
 * SplashScreen — Portal Emergence
 * Dark void with a glowing white circular portal at bottom.
 * Mascot emerges from portal (y 160 -> 0, scale 0.82 -> 1), does a subtle wave (rotateZ),
 * then "GENIO v4.0" + "CYBER-COMPANION" appears above. After ~3.2s calls onReady.
 * Pure transform/opacity — no layout thrash, works on low-end mobile.
 */
export default function SplashScreen({ onReady }: Props) {
  const [visible, setVisible] = useState(true);
  const [wave, setWave] = useState(false);

  useEffect(() => {
    const tWave = window.setTimeout(() => setWave(true), 1100);
    const tHide = window.setTimeout(() => hide(), 3200);
    const tMax = window.setTimeout(() => hide(), 5000);
    const onReadyEvent = () => hide();
    window.addEventListener("genio:ready" as unknown as string, onReadyEvent as EventListener);

    function hide() {
      (window as unknown as { __GENIO_READY__?: boolean }).__GENIO_READY__ = true;
      setVisible(false);
      window.setTimeout(() => onReady?.(), 520);
    }

    return () => {
      clearTimeout(tWave);
      clearTimeout(tHide);
      clearTimeout(tMax);
      window.removeEventListener("genio:ready" as unknown as string, onReadyEvent as EventListener);
    };
  }, [onReady]);

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 1 }}
          exit={{ opacity: 0, scale: 0.98, transition: { duration: 0.52, ease: "easeInOut" } }}
          className="fixed inset-0 z-50 flex flex-col items-center justify-center overflow-hidden bg-[#020B1E]"
        >
          {/* subtle void gradients */}
          <div className="pointer-events-none absolute inset-0 bg-[#020B1E]" />
          <div className="pointer-events-none absolute inset-0 opacity-40" style={{ background: "radial-gradient(ellipse at 50% 85%, rgba(255,255,255,0.08) 0%, transparent 62%)" }} />

          {/* White portal at bottom — glowing circle */}
          <motion.div
            initial={{ scale: 0.78, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.9, ease: "easeOut" }}
            className="absolute bottom-[-2%] left-1/2 -translate-x-1/2"
            style={{ width: "min(88vw, 560px)", height: "min(88vw, 560px)" }}
          >
            {/* outer soft halo */}
            <div className="absolute inset-0 rounded-full blur-[42px]" style={{ background: "radial-gradient(circle at center, rgba(255,255,255,0.95) 0%, rgba(255,255,255,0.55) 18%, rgba(34,211,238,0.22) 38%, transparent 68%)", opacity: 0.85 }} />
            {/* main white portal */}
            <motion.div
              className="absolute inset-[18%] rounded-full bg-white"
              style={{ boxShadow: "0 0 42px rgba(255,255,255,0.9), 0 0 80px rgba(34,211,238,0.45), inset 0 0 28px rgba(255,255,255,0.9)" }}
              animate={{ scale: [1, 1.03, 1], opacity: [0.92, 1, 0.92] }}
              transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
            />
            {/* inner core brighter */}
            <div className="absolute inset-[28%] rounded-full bg-white" style={{ boxShadow: "0 0 24px rgba(255,255,255,1), inset 0 0 18px rgba(255,255,255,1)", opacity: 0.98 }} />
            {/* rim cyan */}
            <div className="absolute inset-[17%] rounded-full border border-cyan-300/30" style={{ boxShadow: "0 0 22px rgba(34,211,238,0.35)" }} />
          </motion.div>

          {/* Mascot emerging from portal */}
          <motion.div
            initial={{ y: 180, scale: 0.82, opacity: 0 }}
            animate={{ y: 0, scale: 1, opacity: 1 }}
            transition={{ type: "spring", damping: 18, stiffness: 120, delay: 0.25 }}
            className="relative z-10 flex flex-col items-center"
            style={{ transformOrigin: "50% 88%" }}
          >
            <motion.div
              animate={wave ? { rotateZ: [0, -7, 7, -5, 0], y: [0, -4, 0] } : { y: [0, -6, 0] }}
              transition={wave ? { duration: 1.1, ease: "easeInOut", delay: 0.2 } : { duration: 4.2, repeat: Infinity, ease: "easeInOut" }}
              className="relative"
              style={{ transformOrigin: "50% 72%" }}
            >
              <img
                src={genioHero}
                alt="Genio"
                className="h-[58vh] max-h-[520px] w-auto max-w-[88vw] object-contain object-bottom drop-shadow-[0_18px_40px_rgba(0,0,0,0.6)] md:h-[62vh]"
                draggable={false}
                fetchPriority="high"
              />
              {/* subtle bottom fade into portal */}
              <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-[18%] bg-gradient-to-t from-white/12 to-transparent" style={{ WebkitMaskImage: "linear-gradient(to top, black 40%, transparent 100%)" } as unknown as Record<string, string>} />
            </motion.div>

            {/* GENIO v4.0 appears */}
            <motion.div
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 1.45, duration: 0.7, ease: "easeOut" }}
              className="mt-3 flex flex-col items-center"
            >
              <motion.div
                className="font-mono text-[22px] font-black tracking-[0.32em] text-white"
                style={{ textShadow: "0 0 18px rgba(255,255,255,0.45), 0 0 32px rgba(34,211,238,0.35)" }}
                initial={{ letterSpacing: "0.28em", opacity: 0 }}
                animate={{ letterSpacing: "0.32em", opacity: 1 }}
                transition={{ delay: 1.55, duration: 0.6 }}
              >
                GENIO <span className="font-light tracking-[0.22em] text-cyan-200">v4.0</span>
              </motion.div>
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 1.9, duration: 0.5 }}
                className="mt-1 font-mono text-[10px] font-bold tracking-[0.28em] text-[#FFD700]"
                style={{ textShadow: "0 0 12px rgba(255,215,0,0.35)" }}
              >
                CYBER-COMPANION
              </motion.div>
              <motion.div
                initial={{ scaleX: 0, opacity: 0 }}
                animate={{ scaleX: 1, opacity: 0.5 }}
                transition={{ delay: 2.05, duration: 0.6, ease: "easeOut" }}
                className="mt-2 h-px w-28 bg-gradient-to-r from-transparent via-white/60 to-transparent"
              />
            </motion.div>
          </motion.div>

          {/* Loading dots — minimal */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 2.2, duration: 0.4 }}
            className="absolute bottom-6 flex items-center gap-1.5"
          >
            {[0, 1, 2].map((i) => (
              <motion.span
                key={i}
                className="h-1.5 w-1.5 rounded-full bg-white/70"
                animate={{ opacity: [0.25, 1, 0.25], scale: [0.9, 1.15, 0.9] }}
                transition={{ duration: 1.1, repeat: Infinity, ease: "easeInOut", delay: i * 0.18 }}
              />
            ))}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
