import { memo, useEffect, useRef, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useFaceTrackingContext } from "../avatar/useFaceTracking";

// Brand puppet assets — webp q80 (hero used in landing, puppet uses 4 states)
import genioWave from "../../assets/mascot/genio-wave.webp";
import genioListen from "../../assets/mascot/genio-listen.webp";
import genioThink from "../../assets/mascot/genio-think.webp";
import genioSpeak from "../../assets/mascot/genio-speak.webp";

type Status = "idle" | "listening" | "thinking" | "executing" | "answering" | "completed" | string;

interface Props {
  status: Status;
  audioLevel?: number;
  className?: string;
}

const IMAGE_MAP: Record<string, string> = {
  idle: genioWave,
  completed: genioWave,
  listening: genioListen,
  thinking: genioThink,
  executing: genioSpeak,
  answering: genioSpeak,
};

const RING_COLOR: Record<string, string> = {
  idle: "#22d3ee",
  completed: "#22d3ee",
  listening: "#f43f5e",
  thinking: "#facc15",
  executing: "#fb7185",
  answering: "#4ade80",
};

const HologramPuppet = memo(function HologramPuppet({ status, audioLevel = 0, className = "" }: Props) {
  const normalized = IMAGE_MAP[status] ? status : "idle";
  const src = IMAGE_MAP[normalized] ?? genioWave;
  const ring = RING_COLOR[normalized] ?? "#22d3ee";

  const containerRef = useRef<HTMLDivElement>(null);
  const imgWrapRef = useRef<HTMLDivElement>(null);
  const { faceLookTarget } = useFaceTrackingContext();

  // tap reaction override
  const [tapOverride, setTapOverride] = useState<string | null>(null);
  const [jump, setJump] = useState(false);
  const [sparks, setSparks] = useState(false);
  const lastTap = useRef(0);
  const overrideTimer = useRef<number | null>(null);

  const activeStatus = tapOverride ?? normalized;
  const activeSrc = IMAGE_MAP[activeStatus] ?? src;
  const activeRing = RING_COLOR[activeStatus] ?? ring;

  // tilt via face tracking + pointer fallback
  useEffect(() => {
    const el = imgWrapRef.current;
    if (!el) return;
    let raf = 0;
    let sX = 0, sY = 0;
    let tx = 0, ty = 0;
    let hasFace = false;
    const onMove = (e: MouseEvent) => {
      if (hasFace) return;
      const r = el.getBoundingClientRect();
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;
      tx = Math.max(-1, Math.min(1, (e.clientX - cx) / (r.width * 0.6)));
      ty = Math.max(-1, Math.min(1, (e.clientY - cy) / (r.height * 0.6)));
    };
    window.addEventListener("mousemove", onMove, { passive: true });
    const loop = () => {
      const fx = faceLookTarget.current[0];
      const fy = faceLookTarget.current[1];
      if (fx !== 0 || fy !== 0) {
        hasFace = true;
        tx = fx;
        ty = fy;
      } else if (hasFace && fx === 0 && fy === 0) {
        // keep last pointer if face lost
        hasFace = false;
      }
      sX += (tx - sX) * 0.08;
      sY += (ty - sY) * 0.08;
      if (el) {
        el.style.transform = `perspective(900px) rotateX(${-sY * 6}deg) rotateY(${sX * 8}deg)`;
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("mousemove", onMove);
      if (el) el.style.transform = "";
    };
  }, [faceLookTarget]);

  // preload other states
  useEffect(() => {
    const all = [genioWave, genioListen, genioThink, genioSpeak] as string[];
    const rest = all.filter((u) => u !== activeSrc);
    for (const u of rest) {
      const img = new Image();
      (img as unknown as { fetchPriority: string }).fetchPriority = "low";
      img.decoding = "async";
      img.src = u;
    }
  }, [activeSrc]);

  const handleTap = useCallback((e: React.PointerEvent) => {
    const el = containerRef.current;
    if (!el) return;
    const now = Date.now();
    const isDouble = now - lastTap.current < 300;
    lastTap.current = now;
    if (isDouble) {
      setJump(true);
      setSparks(true);
      if (overrideTimer.current) window.clearTimeout(overrideTimer.current);
      overrideTimer.current = window.setTimeout(() => {
        setJump(false);
        setSparks(false);
      }, 600) as unknown as number;
      return;
    }
    const rect = el.getBoundingClientRect();
    const yRatio = (e.clientY - rect.top) / rect.height;
    // head zone top 38%
    if (yRatio < 0.38) {
      setTapOverride("thinking");
      if (overrideTimer.current) window.clearTimeout(overrideTimer.current);
      overrideTimer.current = window.setTimeout(() => {
        setTapOverride("idle");
        window.setTimeout(() => setTapOverride(null), 400);
      }, 900) as unknown as number;
    } else {
      setTapOverride("answering");
      if (overrideTimer.current) window.clearTimeout(overrideTimer.current);
      overrideTimer.current = window.setTimeout(() => setTapOverride(null), 800) as unknown as number;
    }
  }, []);

  useEffect(() => () => { if (overrideTimer.current) window.clearTimeout(overrideTimer.current); }, []);

  return (
    <div
      ref={containerRef}
      className={`relative flex h-full w-full items-center justify-center select-none ${className}`}
      onPointerDown={handleTap}
      style={{ touchAction: "manipulation" }}
    >
      {/* cyan glow pulse synced to status — behind puppet */}
      <motion.div
        className="pointer-events-none absolute rounded-full blur-[42px]"
        style={{
          width: "68%",
          height: "42%",
          bottom: "18%",
          background: `radial-gradient(ellipse at center, ${activeRing} 0%, transparent 72%)`,
          opacity: 0.22,
        }}
        animate={{ scale: [1, 1.08, 1], opacity: [0.18, 0.28, 0.18] }}
        transition={{ duration: normalized === "listening" ? 1.2 : normalized === "answering" ? 0.9 : 2.6, repeat: Infinity, ease: "easeInOut" }}
      />

      {/* holographic ring + particles under feet */}
      <div className="pointer-events-none absolute bottom-[10%] left-1/2 -translate-x-1/2 flex flex-col items-center gap-1">
        <motion.div
          className="rounded-full border"
          style={{ width: 96, height: 18, borderColor: activeRing, opacity: 0.9, boxShadow: `0 0 18px ${activeRing}` }}
          animate={{ scaleX: [1, 1.06, 1], opacity: [0.7, 1, 0.7] }}
          transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          className="rounded-full border"
          style={{ width: 72, height: 12, borderColor: activeRing, opacity: 0.5 }}
          animate={{ scaleX: [1, 1.08, 1], opacity: [0.4, 0.7, 0.4] }}
          transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut", delay: 0.3 }}
        />
        {/* particles */}
        <div className="flex gap-1">
          {[0, 1, 2, 3, 4].map((i) => (
            <motion.span
              key={i}
              className="h-1 w-1 rounded-full"
              style={{ background: activeRing }}
              animate={{ y: [0, -6, 0], opacity: [0.3, 0.9, 0.3] }}
              transition={{ duration: 1.6 + i * 0.2, repeat: Infinity, ease: "easeInOut", delay: i * 0.15 }}
            />
          ))}
        </div>
      </div>

      {/* spark burst on double-tap */}
      <AnimatePresence>
        {sparks && (
          <motion.div className="pointer-events-none absolute bottom-[18%] left-1/2 -translate-x-1/2">
            {Array.from({ length: 10 }).map((_, i) => (
              <motion.span
                key={i}
                className="absolute h-1.5 w-1.5 rounded-full"
                style={{ background: "#FFD700", left: 0, top: 0, boxShadow: "0 0 8px #FFD700" }}
                initial={{ x: 0, y: 0, opacity: 1, scale: 1 }}
                animate={{
                  x: (Math.random() - 0.5) * 120,
                  y: -30 - Math.random() * 60,
                  opacity: 0,
                  scale: 0,
                }}
                transition={{ duration: 0.6, ease: "easeOut", delay: i * 0.02 }}
              />
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* breathing + jump container */}
      <motion.div
        ref={imgWrapRef}
        className="relative z-10 flex h-full w-full items-center justify-center will-change-transform"
        style={{ transformStyle: "preserve-3d" }}
        animate={{
          scale: jump ? [1, 1.06, 1] : [1, 1.015, 1],
          y: jump ? [0, -18, 0] : [0, 0, 0],
        }}
        transition={jump ? { duration: 0.6, ease: "easeOut" } : { duration: 4.5, repeat: Infinity, ease: "easeInOut" }}
      >
        <AnimatePresence mode="wait">
          <motion.div
            key={activeStatus}
            initial={{ opacity: 0, scale: 0.985 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.985 }}
            transition={{ duration: 0.25, ease: "easeOut", type: "spring", damping: 22, stiffness: 280 }}
            className="relative h-full w-full flex items-center justify-center"
            style={{ willChange: "transform, opacity" }}
          >
            {/* image with mask + screen blend */}
            <img
              src={activeSrc}
              alt={`Genio ${activeStatus}`}
              className="h-full w-full object-contain object-bottom select-none"
              style={{
                WebkitMaskImage: "radial-gradient(ellipse at 50% 55%, black 62%, transparent 82%)",
                maskImage: "radial-gradient(ellipse at 50% 55%, black 62%, transparent 82%)",
                mixBlendMode: "screen",
                filter: "contrast(1.05) saturate(1.05)",
                transformOrigin: "50% 78%",
              } as React.CSSProperties}
              draggable={false}
              onError={(e) => {
                const t = e.currentTarget as HTMLImageElement;
                if (t.src.endsWith(".webp")) t.src = t.src.replace(".webp", ".png");
              }}
            />

            {/* mouth-zone glow when answering — synced to audioLevel */}
            {normalized === "answering" && (
              <motion.div
                className="pointer-events-none absolute rounded-full blur-[14px]"
                style={{
                  width: "22%",
                  height: "10%",
                  left: "50%",
                  top: "58%",
                  x: "-50%",
                  background: `radial-gradient(ellipse at center, ${activeRing} 0%, transparent 70%)`,
                  opacity: 0.55 + audioLevel * 0.45,
                  mixBlendMode: "screen",
                } as React.CSSProperties}
                animate={{ scale: 1 + audioLevel * 0.4, opacity: 0.4 + audioLevel * 0.6 }}
                transition={{ duration: 0.12, ease: "easeOut" }}
              />
            )}

            {/* scanline shimmer — transform only */}
            <motion.div
              className="pointer-events-none absolute inset-0"
              style={{
                background: `repeating-linear-gradient(0deg, transparent 0 2px, rgba(34,211,238,0.06) 2px 3px)`,
                WebkitMaskImage: "radial-gradient(ellipse at 50% 50%, black 55%, transparent 85%)",
                maskImage: "radial-gradient(ellipse at 50% 50%, black 55%, transparent 85%)",
                mixBlendMode: "screen",
              } as React.CSSProperties}
              animate={{ y: [0, 3, 0] }}
              transition={{ duration: 2.8, repeat: Infinity, ease: "easeInOut" }}
            />
          </motion.div>
        </AnimatePresence>
      </motion.div>

      {/* ground shadow */}
      <div
        className="pointer-events-none absolute rounded-full"
        style={{
          bottom: "8%",
          width: "34%",
          height: 12,
          background: "radial-gradient(ellipse at center, rgba(0,0,0,0.45) 0%, transparent 70%)",
          filter: "blur(1px)",
        }}
      />
    </div>
  );
});

export default HologramPuppet;
