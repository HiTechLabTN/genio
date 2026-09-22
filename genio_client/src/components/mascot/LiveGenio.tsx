import { memo, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence, useMotionValue, useTransform, useSpring } from "framer-motion";
import genioHero from "../../assets/mascot/genio-hero.png";

type Props = {
  status?: string;
  audioLevel?: number;
};

const LiveGenio = memo(function LiveGenio({ status = "idle", audioLevel = 0 }: Props) {
  const isSpeaking = audioLevel > 0.05;
  const containerRef = useRef<HTMLDivElement>(null);
  const [portalDone, setPortalDone] = useState(false);
  const [wave, setWave] = useState(false);
  useEffect(() => {
    const t1 = window.setTimeout(() => setWave(true), 1100);
    const t2 = window.setTimeout(() => setPortalDone(true), 3200);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, []);

  // Parallax motion values
  const mx = useMotionValue(0);
  const my = useMotionValue(0);
  const springX = useSpring(mx, { stiffness: 45, damping: 18 });
  const springY = useSpring(my, { stiffness: 45, damping: 18 });
  const rotateY = useTransform(springX, [-1, 1], [-9, 9]);
  const rotateX = useTransform(springY, [-1, 1], [6, -6]);
  const translateX = useTransform(springX, [-1, 1], [-14, 14]);
  const translateY = useTransform(springY, [-1, 1], [-10, 10]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const onMouseMove = (e: MouseEvent) => {
      const rect = el.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const nx = Math.max(-1, Math.min(1, (e.clientX - cx) / (rect.width * 0.45)));
      const ny = Math.max(-1, Math.min(1, (e.clientY - cy) / (rect.height * 0.45)));
      mx.set(nx);
      my.set(ny);
    };

    const onDeviceOrientation = (e: DeviceOrientationEvent) => {
      // Only react strongly on mobile where gamma/beta are meaningful
      const gamma = e.gamma ?? 0; // left/right -90..90
      const beta = e.beta ?? 0; // front/back -180..180
      // Normalize to -1..1, ignore if all zero (desktop)
      if (Math.abs(gamma) < 0.1 && Math.abs(beta) < 0.1) return;
      const nx = Math.max(-1, Math.min(1, gamma / 25));
      const ny = Math.max(-1, Math.min(1, (beta - 45) / 30));
      // blend with mouse values — gyro overrides when present
      mx.set(nx);
      my.set(ny);
    };

    const needPermission = (DeviceOrientationEvent as unknown as { requestPermission?: () => Promise<string> }).requestPermission;
    if (needPermission) {
      // iOS requires permission; we try silently, if denied mouse still works
      // Do not prompt unless user interacted — handled elsewhere
    }

    window.addEventListener("mousemove", onMouseMove, { passive: true });
    window.addEventListener("deviceorientation", onDeviceOrientation, { passive: true });

    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("deviceorientation", onDeviceOrientation);
    };
  }, [mx, my]);

  // Breathing + speaking combined
  const breathingDuration = 4.5;
  const isWaving = status === "waving" || status === "greeting" || status === "completed";

  return (
    <div
      ref={containerRef}
      className="relative flex h-full w-full items-center justify-center overflow-hidden bg-[#020B1E] select-none"
      style={{ perspective: "1100px" }}
    >
      {/* PORTAL EMERGENCE — cinematic intro housed in LiveGenio (no double splash) */}
      <AnimatePresence>
        {!portalDone && (
          <motion.div
            key="portal-intro"
            initial={{ opacity: 1 }}
            exit={{ opacity: 0, scale: 0.98, transition: { duration: 0.6, ease: "easeInOut" } }}
            className="absolute inset-0 z-30 flex flex-col items-center justify-center overflow-hidden bg-[#020B1E]"
          >
            <div className="pointer-events-none absolute inset-0 bg-[#020B1E]" />
            {/* Glowing white portal at bottom */}
            <motion.div
              initial={{ scale: 0.78, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.9, ease: "easeOut" }}
              className="absolute bottom-[-2%] left-1/2 -translate-x-1/2"
              style={{ width: "min(88vw, 560px)", height: "min(88vw, 560px)" }}
            >
              <div className="absolute inset-0 rounded-full blur-[42px]" style={{ background: "radial-gradient(circle at center, rgba(255,255,255,0.95) 0%, rgba(255,255,255,0.55) 18%, rgba(34,211,238,0.22) 38%, transparent 68%)", opacity: 0.85 }} />
              <motion.div className="absolute inset-[18%] rounded-full bg-white" style={{ boxShadow: "0 0 42px rgba(255,255,255,0.9), 0 0 80px rgba(34,211,238,0.45), inset 0 0 28px rgba(255,255,255,0.9)" }} animate={{ scale: [1, 1.03, 1] }} transition={{ duration: 2.2, repeat: Infinity }} />
              <div className="absolute inset-[28%] rounded-full bg-white" style={{ boxShadow: "0 0 24px rgba(255,255,255,1)" }} />
              <div className="absolute inset-[17%] rounded-full border border-cyan-300/30" style={{ boxShadow: "0 0 22px rgba(34,211,238,0.35)" }} />
            </motion.div>
            {/* Mascot emerges from portal */}
            <motion.div initial={{ y: 180, scale: 0.82, opacity: 0 }} animate={{ y: 0, scale: 1, opacity: 1 }} transition={{ type: "spring", damping: 18, stiffness: 120, delay: 0.25 }} className="relative z-10 flex flex-col items-center" style={{ transformOrigin: "50% 88%" }}>
              <motion.div animate={wave ? { rotateZ: [0, -7, 7, -5, 0], y: [0, -4, 0] } : { y: [0, -6, 0] }} transition={wave ? { duration: 1.1, ease: "easeInOut" } : { duration: 4.2, repeat: Infinity }} className="relative" style={{ transformOrigin: "50% 72%" }}>
                <img src={genioHero} alt="Genio" className="h-[58vh] max-h-[520px] w-auto max-w-[88vw] object-contain object-bottom drop-shadow-[0_18px_40px_rgba(0,0,0,0.6)]" draggable={false} />
              </motion.div>
              <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 1.45, duration: 0.7 }} className="mt-3 flex flex-col items-center">
                <div className="font-mono text-[22px] font-black tracking-[0.32em] text-white" style={{ textShadow: "0 0 18px rgba(255,255,255,0.45)" }}>
                  GENIO <span className="font-light tracking-[0.22em] text-cyan-200">v4.0</span>
                </div>
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.9 }} className="mt-1 font-mono text-[10px] font-bold tracking-[0.28em] text-[#FFD700]" style={{ textShadow: "0 0 12px rgba(255,215,0,0.35)" }}>
                  CYBER-COMPANION
                </motion.div>
              </motion.div>
            </motion.div>
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 2.2 }} className="absolute bottom-6 flex gap-1.5">
              {[0, 1, 2].map((i) => (
                <motion.span key={i} className="h-1.5 w-1.5 rounded-full bg-white/70" animate={{ opacity: [0.25, 1, 0.25], scale: [0.9, 1.15, 0.9] }} transition={{ duration: 1.1, repeat: Infinity, delay: i * 0.18 }} />
              ))}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Islamic Cyberpunk void background — radial + subtle zellij tint */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0 bg-[#020B1E]" />
        <div className="absolute inset-0 opacity-[0.55]" style={{ background: "radial-gradient(ellipse at 50% 72%, rgba(34,211,238,0.14) 0%, transparent 62%), radial-gradient(ellipse at 50% 28%, rgba(255,215,0,0.06) 0%, transparent 55%)" }} />
        {/* soft vignette */}
        <div className="absolute inset-0" style={{ background: "radial-gradient(ellipse at center, transparent 56%, rgba(0,0,0,0.55) 100%)" }} />
      </div>

      {/* Glowing portal at feet — always visible as base */}
      <motion.div
        className="pointer-events-none absolute bottom-[7%] left-1/2 -translate-x-1/2 rounded-full blur-[18px]"
        style={{
          width: "38%",
          height: "5%",
          maxWidth: 420,
          background: "radial-gradient(ellipse at center, rgba(255,255,255,0.95) 0%, rgba(255,255,255,0.55) 22%, rgba(34,211,238,0.35) 48%, transparent 72%)",
          opacity: 0.9,
        }}
        animate={{ scaleX: isSpeaking ? [0.96, 1.08, 0.96] : [0.98, 1.04, 0.98], opacity: isSpeaking ? [0.7, 1, 0.7] : [0.55, 0.85, 0.55] }}
        transition={{ duration: isSpeaking ? 0.45 : 3.2, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="pointer-events-none absolute bottom-[7.5%] left-1/2 h-[2px] -translate-x-1/2 rounded-full bg-white/80"
        style={{ width: "28%", maxWidth: 320, boxShadow: "0 0 18px rgba(255,255,255,0.9), 0 0 32px rgba(34,211,238,0.6)" }}
        animate={{ scaleX: [0.9, 1, 0.9], opacity: [0.6, 1, 0.6] }}
        transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
      />

      {/* Speaking pulse rings */}
      {isSpeaking && (
        <>
          <motion.div
            className="pointer-events-none absolute bottom-[7%] left-1/2 h-20 w-20 -translate-x-1/2 rounded-full border border-white/40"
            initial={{ scale: 0.6, opacity: 0.6 }}
            animate={{ scale: [0.6, 1.4, 0.6], opacity: [0.5, 0, 0.5] }}
            transition={{ duration: 0.9, repeat: Infinity, ease: "easeOut" }}
            style={{ boxShadow: "0 0 16px rgba(255,255,255,0.6)" }}
          />
          <motion.div
            className="pointer-events-none absolute bottom-[7%] left-1/2 h-28 w-28 -translate-x-1/2 rounded-full border border-cyan-400/30"
            initial={{ scale: 0.7, opacity: 0.4 }}
            animate={{ scale: [0.7, 1.35, 0.7], opacity: [0.35, 0, 0.35] }}
            transition={{ duration: 1.1, repeat: Infinity, ease: "easeOut", delay: 0.15 }}
          />
        </>
      )}

      {/* Main LIVE avatar — 2.5D parallax + breathing + speaking — FULL-BLEED */}
      <motion.div
        className="absolute inset-0 z-10 flex items-center justify-center will-change-transform overflow-hidden"
        style={
          {
            rotateX,
            rotateY,
            x: translateX,
            y: translateY,
            transformStyle: "preserve-3d",
          } as unknown as Record<string, unknown> as never
        }
      >
        <motion.div
          className="absolute inset-0 w-full h-full scale-[1.1] origin-center"
          // Breathing: vertical translate + subtle scale (scaled base keeps full-bleed)
          animate={
            isSpeaking
              ? {
                  y: [0, -6 - audioLevel * 28, 0, -3, 0],
                  scale: [1.1, 1.1 * (1.018 + audioLevel * 0.04), 1.1, 1.1 * 1.01, 1.1],
                  rotateZ: isWaving ? [0, -1.2, 1.2, -1.2, 0] : [0, 0.3, 0, -0.3, 0],
                }
              : isWaving
              ? {
                  y: [0, -7, 0],
                  scale: [1.1, 1.1 * 1.015, 1.1],
                  rotateZ: [0, -1.4, 1.4, -1, 0],
                }
              : {
                  y: [0, -8, 0],
                  scale: [1.1, 1.1 * 1.02, 1.1],
                }
          }
          transition={
            isSpeaking
              ? { duration: 0.55, repeat: Infinity, ease: "easeInOut" }
              : { duration: breathingDuration, repeat: Infinity, ease: "easeInOut" }
          }
        >
          {/* Glow behind avatar — reacts to audio */}
          <motion.div
            className="pointer-events-none absolute bottom-[10%] left-1/2 h-[46%] w-[72%] -translate-x-1/2 rounded-full blur-[38px]"
            style={{
              background: "radial-gradient(ellipse at center, rgba(34,211,238,0.22) 0%, rgba(255,215,0,0.08) 38%, transparent 72%)",
            }}
            animate={{
              opacity: isSpeaking ? [0.35, 0.75 + audioLevel * 0.5, 0.35] : [0.28, 0.45, 0.28],
              scale: isSpeaking ? 1 + audioLevel * 0.35 : 1,
            }}
            transition={{ duration: isSpeaking ? 0.35 : 3.5, repeat: Infinity, ease: "easeInOut" }}
          />

          {/* Avatar image — FULL-BLEED background layer */}
          <motion.img
            src={genioHero}
            alt="Genio — Live Avatar"
            className="absolute inset-0 w-full h-full object-cover object-center select-none"
            draggable={false}
            style={{
              filter: isSpeaking
                ? `brightness(${1.06 + audioLevel * 0.18}) saturate(${1.08 + audioLevel * 0.16}) drop-shadow(0 0 ${18 + audioLevel * 40}px rgba(34,211,238,${0.18 + audioLevel * 0.22}))`
                : "brightness(1.02) saturate(1.06)",
              transformOrigin: "50% 55%",
            }}
            animate={
              isSpeaking
                ? {
                    scaleY: [1, 1 + audioLevel * 0.06, 1],
                    scaleX: [1, 1 - audioLevel * 0.02, 1],
                  }
                : {}
            }
            transition={isSpeaking ? { duration: 0.18, repeat: Infinity, ease: "easeInOut" } : undefined}
            onError={(e) => {
              const t = e.currentTarget as HTMLImageElement;
              if (t.src.endsWith(".png")) t.src = t.src.replace(".png", ".webp");
            }}
          />

          {/* Screen blend shimmer — premium polish, transform only */}
          <motion.div
            className="pointer-events-none absolute inset-0 z-20"
            style={
              {
                background: "repeating-linear-gradient(0deg, transparent 0 2px, rgba(255,255,255,0.035) 2px 3px)",
                WebkitMaskImage: "linear-gradient(to bottom, transparent 64%, black 82%)",
                maskImage: "linear-gradient(to bottom, transparent 64%, black 82%)",
                mixBlendMode: "screen",
              } as unknown as Record<string, unknown> as never
            }
            animate={{ y: [0, 2, 0] }}
            transition={{ duration: 2.8, repeat: Infinity, ease: "easeInOut" }}
          />
        </motion.div>
      </motion.div>

      {/* Ambient particles — subtle depth */}
      <div className="pointer-events-none absolute inset-0 z-10">
        {Array.from({ length: 10 }).map((_, i) => (
          <motion.span
            key={i}
            className="absolute h-[2px] w-[2px] rounded-full bg-white/60"
            style={{ left: `${8 + i * 9}%`, top: `${18 + (i % 3) * 22}%`, boxShadow: "0 0 6px rgba(255,255,255,0.7)" }}
            animate={{ y: [0, -10, 0], opacity: [0.15, 0.55, 0.15] }}
            transition={{ duration: 3.2 + (i % 3), delay: i * 0.22, repeat: Infinity, ease: "easeInOut" }}
          />
        ))}
      </div>

      {/* Ground shadow under feet */}
      <div
        className="pointer-events-none absolute bottom-[5.5%] left-1/2 h-[10px] w-[30%] max-w-[300px] -translate-x-1/2 rounded-full"
        style={{ background: "radial-gradient(ellipse at center, rgba(0,0,0,0.52) 0%, transparent 70%)", filter: "blur(1px)" }}
      />
    </div>
  );
});

export default LiveGenio;
