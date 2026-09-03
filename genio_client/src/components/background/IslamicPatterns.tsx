import { memo, useMemo } from "react";
import { motion } from "framer-motion";

/**
 * IslamicPatterns — z-0 background
 * - SVG 8-point Andalusian stars (cyan .12 + gold .08)
 * - gradient #0a0e1a → #0f172a → #1a0a1e
 * - arabesque border pulse 6s
 * - ≤20 gold particles (y/opacity only, transform/opacity)
 * - memo() to prevent re-renders from telemetry ticks
 */
const IslamicPatterns = memo(function IslamicPatterns() {
  const particles = useMemo(
    () =>
      Array.from({ length: 18 }, (_, i) => ({
        id: i,
        x: (i * 37) % 100,
        y: (i * 57) % 100,
        size: 1.2 + (i % 3) * 0.6,
        delay: (i * 0.34) % 4,
        duration: 7 + (i % 5),
      })),
    []
  );

  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-0 z-0 overflow-hidden"
      style={{
        background: "linear-gradient(180deg, #0a0e1a 0%, #0f172a 55%, #1a0a1e 100%)",
      }}
    >
      {/* 8-point Andalusian stars — SVG pattern */}
      <svg
        className="absolute inset-0 h-full w-full"
        xmlns="http://www.w3.org/2000/svg"
        preserveAspectRatio="none"
      >
        <defs>
          <pattern id="andalusian-stars" width="120" height="120" patternUnits="userSpaceOnUse">
            {/* 8-point star — cyan .12 */}
            <g stroke="#22d3ee" strokeWidth="1.2" fill="none" opacity={0.12}>
              <path d="M60 12 L66 28 L82 28 L70 38 L74 54 L60 44 L46 54 L50 38 L38 28 L54 28 Z" />
              <path d="M60 12 L60 54 M38 28 L82 28 M46 18 L74 42 M74 18 L46 42" opacity={0.5} />
            </g>
            {/* inner 8-point — gold .08 */}
            <g stroke="#FFD700" strokeWidth="0.9" fill="none" opacity={0.08}>
              <path d="M60 35 L63 41 L69 41 L64 45 L66 51 L60 47 L54 51 L56 45 L51 41 L57 41 Z" />
            </g>
          </pattern>
          <radialGradient id="glow-cyan" cx="50%" cy="38%" r="70%">
            <stop offset="0%" stopColor="rgba(34,211,238,0.14)" />
            <stop offset="55%" stopColor="rgba(34,211,238,0.04)" />
            <stop offset="100%" stopColor="transparent" />
          </radialGradient>
        </defs>
        <rect width="100%" height="100%" fill="url(#andalusian-stars)" />
        <rect width="100%" height="100%" fill="url(#glow-cyan)" />
      </svg>

      {/* arabesque border — pulse 6s (opacity only) */}
      <motion.div
        className="absolute inset-3 rounded-[2rem] border border-[#FFD700]/20"
        animate={{ opacity: [0.5, 0.85, 0.5], borderColor: ["rgba(255,215,0,0.15)", "rgba(255,215,0,0.28)", "rgba(255,215,0,0.15)"] as unknown as string[] }}
        transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
        style={{ boxShadow: "inset 0 0 40px rgba(34,211,238,0.08)" }}
      />
      <motion.div
        className="absolute inset-6 rounded-[1.7rem] border border-cyan-400/10"
        animate={{ opacity: [0.3, 0.6, 0.3] }}
        transition={{ duration: 6, repeat: Infinity, ease: "easeInOut", delay: 1.5 }}
      />

      {/* gold particles — y/opacity only, transform */}
      {particles.map((p) => (
        <motion.div
          key={p.id}
          className="absolute rounded-full bg-[#FFD700]"
          style={{
            left: `${p.x}%`,
            top: `${p.y}%`,
            width: p.size,
            height: p.size,
            boxShadow: "0 0 6px rgba(255,215,0,0.6)",
          }}
          animate={{ y: [0, -18, 0], opacity: [0.3, 0.85, 0.3] }}
          transition={{ duration: p.duration, delay: p.delay, repeat: Infinity, ease: "easeInOut" }}
        />
      ))}
    </div>
  );
});

export default IslamicPatterns;
