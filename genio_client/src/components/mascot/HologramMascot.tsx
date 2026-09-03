import { memo, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";

// Assets — order per spec (if PNG missing, SVG fallback exists)
import jebbaWave from "../../assets/mascot/genio-jebba-wave.png";
import burnousPresent from "../../assets/mascot/genio-burnous-present.png";
import listen from "../../assets/mascot/genio-listen.png";
import execImg from "../../assets/mascot/genio-exec.png";
import think from "../../assets/mascot/genio-think.png";
import wave from "../../assets/mascot/genio-wave.png";

type Status = "idle" | "listening" | "thinking" | "executing" | "answering" | "completed" | string;

interface Props {
  status: Status;
  audioLevel?: number;
  isMinimized?: boolean;
  className?: string;
}

const IMAGE_MAP: Record<string, string> = {
  idle: jebbaWave,
  listening: listen,
  thinking: think,
  executing: execImg,
  answering: burnousPresent,
  completed: wave,
};

const RING_COLOR: Record<string, string> = {
  idle: "#22d3ee",
  listening: "#f43f5e",
  thinking: "#facc15",
  executing: "#fb7185",
  answering: "#4ade80",
  completed: "#22d3ee",
};

const HologramMascot = memo(function HologramMascot({ status, audioLevel = 0, isMinimized = false, className = "" }: Props) {
  const normalized = IMAGE_MAP[status] ? status : "idle";
  const src = IMAGE_MAP[normalized] ?? jebbaWave;
  const ring = RING_COLOR[normalized] ?? "#22d3ee";

  // face-track lerp ±8°/±12° (mouse fallback) + lip-sync
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || isMinimized) return;
    let raf = 0;
    let sX = 0, sY = 0;
    let tx = 0, ty = 0;
    const onMove = (e: MouseEvent) => {
      const r = el.getBoundingClientRect();
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;
      tx = Math.max(-1, Math.min(1, (e.clientX - cx) / (r.width * 0.6)));
      ty = Math.max(-1, Math.min(1, (e.clientY - cy) / (r.height * 0.6)));
    };
    window.addEventListener("mousemove", onMove, { passive: true });
    const loop = () => {
      sX += (tx - sX) * 0.08;
      sY += (ty - sY) * 0.08;
      if (el) {
        el.style.transform = `perspective(800px) rotateX(${-sY * 8}deg) rotateY(${sX * 12}deg)`;
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("mousemove", onMove);
      if (el) el.style.transform = "";
    };
  }, [isMinimized]);

  const size = isMinimized ? 72 : 320;

  return (
    <motion.div
      layoutId="genio-avatar"
      ref={containerRef}
      className={`relative flex items-center justify-center select-none ${className}`}
      style={{ width: size, height: size }}
      initial={false}
      animate={{ y: isMinimized ? 0 : [0, -10, 0] }}
      transition={isMinimized ? { duration: 0.35 } : { duration: 4.5, repeat: Infinity, ease: "easeInOut" }}
      whileTap={{ scale: 0.88, rotate: -6 }}
    >
      {/* 3 pulsing rings */}
      {[0, 1, 2].map((i) => (
        <motion.div
          key={i}
          className="absolute rounded-full border"
          style={{ borderColor: ring, inset: isMinimized ? 2 : 8 + i * 10 }}
          animate={{ scale: [1, 1.06, 1], opacity: [0.18, 0.32, 0.18] }}
          transition={{ duration: 2.2 + i * 0.4, repeat: Infinity, ease: "easeInOut", delay: i * 0.25 }}
        />
      ))}

      {/* ground shadow */}
      <div
        className="absolute rounded-full"
        style={{
          bottom: isMinimized ? 2 : 8,
          width: isMinimized ? 36 : size * 0.42,
          height: isMinimized ? 8 : 14,
          background: "radial-gradient(ellipse at center, rgba(0,0,0,0.45) 0%, transparent 70%)",
          filter: "blur(1px)",
        }}
      />

      {/* mascot image crossfade */}
      <AnimatePresence mode="wait">
        <motion.img
          key={normalized}
          src={src}
          alt={`Genio ${normalized}`}
          className="relative z-10 h-full w-full object-contain drop-shadow-[0_0_24px_rgba(34,211,238,0.35)]"
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{
            opacity: 1,
            scale: 1,
            // lip-sync on visor/mouth area via scaleY (transform only)
            scaleY: 1 + audioLevel * 0.04,
          }}
          exit={{ opacity: 0, scale: 0.96 }}
          transition={{ type: "spring", damping: 18, stiffness: 220, opacity: { duration: 0.25 } }}
          style={{ transformOrigin: "50% 62%" }}
          onError={(e) => {
            // fallback to SVG if PNG failed (placeholder case)
            const t = e.currentTarget as HTMLImageElement;
            if (t.src.endsWith(".png")) t.src = t.src.replace(".png", ".svg");
          }}
        />
      </AnimatePresence>

      {/* static scanlines + radial glow (no animated filters) */}
      <div
        className="pointer-events-none absolute inset-0 z-0 rounded-full overflow-hidden"
        style={{
          background: `repeating-linear-gradient(0deg, transparent 0 2px, rgba(34,211,238,0.04) 2px 3px), radial-gradient(ellipse at 50% 30%, rgba(34,211,238,0.14), transparent 62%)`,
          maskImage: "radial-gradient(circle at 50% 50%, black 58%, transparent 78%)",
          WebkitMaskImage: "radial-gradient(circle at 50% 50%, black 58%, transparent 78%)",
        }}
      />
    </motion.div>
  );
});

export default HologramMascot;
