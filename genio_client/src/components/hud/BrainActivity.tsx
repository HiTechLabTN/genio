import { memo } from "react";
import { motion } from "framer-motion";

interface Props {
  active?: boolean;
}

/**
 * BrainActivity — thinking/executing only
 * - pulsing brain + 8 sparks (transform/opacity only)
 */
const BrainActivity = memo(function BrainActivity({ active = false }: Props) {
  if (!active) return null;
  const sparks = Array.from({ length: 8 }, (_, i) => ({
    id: i,
    angle: (i * 360) / 8,
    delay: i * 0.12,
  }));

  return (
    <div className="relative flex h-[140px] w-[180px] items-center justify-center">
      {/* pulsing brain core */}
      <motion.div
        className="relative z-10 flex h-16 w-16 items-center justify-center rounded-full bg-gradient-to-br from-cyan-400/20 to-violet-500/20 ring-1 ring-cyan-300/30 backdrop-blur"
        animate={{ scale: [1, 1.06, 1], opacity: [0.85, 1, 0.85] }}
        transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
      >
        <span className="text-xl">🧠</span>
        <motion.div
          className="absolute inset-0 rounded-full border border-cyan-300/40"
          animate={{ scale: [1, 1.35], opacity: [0.5, 0] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: "easeOut" }}
        />
      </motion.div>

      {/* 8 sparks — transform/opacity only */}
      {sparks.map((s) => (
        <motion.div
          key={s.id}
          className="absolute h-1.5 w-1.5 rounded-full bg-[#FFD700] shadow-[0_0_6px_rgba(255,215,0,0.8)]"
          style={{
            left: "50%",
            top: "50%",
          }}
          animate={{
            x: [0, Math.cos((s.angle * Math.PI) / 180) * 52],
            y: [0, Math.sin((s.angle * Math.PI) / 180) * 52],
            opacity: [0, 1, 0],
            scale: [0.6, 1, 0.6],
          }}
          transition={{ duration: 1.4, delay: s.delay, repeat: Infinity, ease: "easeInOut" }}
        />
      ))}

      {/* subtle cyan ring */}
      <motion.div
        className="absolute h-28 w-28 rounded-full border border-cyan-400/20"
        animate={{ scale: [0.9, 1.05, 0.9], opacity: [0.3, 0.55, 0.3] }}
        transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
      />
    </div>
  );
});

export default BrainActivity;
