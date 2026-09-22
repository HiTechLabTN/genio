import { memo } from "react";
import { motion } from "framer-motion";

/**
 * HoloPlatform — anneau holographique lumineux sous la mascotte, fidèle à la
 * plateforme circulaire cyan de la référence (assets-pipeline/reference-views/original_hero.png) :
 * plusieurs anneaux concentriques + segments qui tournent lentement + pulse doux.
 * Position: à placer sous le personnage, en absolute dans le même conteneur positionné.
 */
const HoloPlatform = memo(function HoloPlatform({
  width = 420,
  top = 430,
}: {
  width?: number;
  /** Offset vertical fixe en px depuis le haut du conteneur parent (positionné en absolute),
   * à aligner sur les pieds du personnage — le conteneur mascotte fait 520px de haut. */
  top?: number;
}) {
  const h = width * 0.34;
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute left-1/2 -translate-x-1/2"
      style={{ top, width, height: h }}
    >
      <svg viewBox="0 0 200 68" width="100%" height="100%" style={{ overflow: "visible" }}>
        <defs>
          <radialGradient id="holo-fill" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="rgba(34,211,238,0.22)" />
            <stop offset="60%" stopColor="rgba(34,211,238,0.08)" />
            <stop offset="100%" stopColor="rgba(34,211,238,0)" />
          </radialGradient>
        </defs>
        <ellipse cx="100" cy="34" rx="96" ry="30" fill="url(#holo-fill)" />
        {/* Anneau principal */}
        <ellipse cx="100" cy="34" rx="88" ry="26" fill="none" stroke="#22d3ee" strokeWidth="1.4" opacity="0.55" />
        {/* Anneau secondaire, légèrement plus petit */}
        <ellipse cx="100" cy="34" rx="70" ry="20" fill="none" stroke="#67e8f9" strokeWidth="0.9" opacity="0.35" />
        {/* Segments tournants (arcs pointillés) */}
        <motion.ellipse
          cx="100" cy="34" rx="88" ry="26" fill="none" stroke="#22d3ee" strokeWidth="2.4"
          strokeDasharray="14 38" opacity="0.7"
          animate={{ strokeDashoffset: [0, -260] }}
          transition={{ duration: 9, repeat: Infinity, ease: "linear" }}
        />
        <motion.ellipse
          cx="100" cy="34" rx="70" ry="20" fill="none" stroke="#a5f3fc" strokeWidth="1.6"
          strokeDasharray="8 24" opacity="0.5"
          animate={{ strokeDashoffset: [0, 160] }}
          transition={{ duration: 6, repeat: Infinity, ease: "linear" }}
        />
      </svg>
      <motion.div
        className="absolute inset-0 rounded-[50%]"
        style={{ boxShadow: "0 0 40px 8px rgba(34,211,238,0.18)" }}
        animate={{ opacity: [0.6, 1, 0.6] }}
        transition={{ duration: 3.2, repeat: Infinity, ease: "easeInOut" }}
      />
    </div>
  );
});

export default HoloPlatform;
