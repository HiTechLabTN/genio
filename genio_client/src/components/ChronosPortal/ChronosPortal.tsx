import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useTaskProcessor } from "../../hooks/useTaskProcessor";
import SystemMetrics from "./SystemMetrics";
import genioAvatarFace from "../../assets/genio-avatar-face.png";
import styles from "./ChronosPortal.module.css";
import type { AgentStatus, ChatEvent, TelemetrySnapshot } from "../../lib/types";

interface ChronosPortalProps {
  chat: ChatEvent[];
  telemetry: TelemetrySnapshot | null;
  agentStatus: AgentStatus;
  onDismiss?: () => void;
}

// Ring/glow color follows the real agent status — not decorative, it's a signal.
const STATUS_COLOR: Record<AgentStatus["kind"], string> = {
  idle: "rgba(0, 229, 255, 0.35)",
  thinking: "rgba(0, 229, 255, 0.55)",
  executing: "rgba(255, 176, 32, 0.6)",
  completed: "rgba(76, 175, 80, 0.6)",
};

export default function ChronosPortal({ chat, telemetry, agentStatus, onDismiss }: ChronosPortalProps) {
  const { isMinimized, setIsMinimized, thinkingSteps, toolActivity, metrics, result, error, isProcessing } =
    useTaskProcessor({ chat, telemetry, agentStatus });
  const [isHovered, setIsHovered] = useState(false);

  const hasContent = thinkingSteps.length > 0 || toolActivity.length > 0 || !!result || !!error || isProcessing;
  if (!hasContent) return null;

  const ringColor = STATUS_COLOR[agentStatus.kind] ?? STATUS_COLOR.idle;
  const isActive = agentStatus.kind === "thinking" || agentStatus.kind === "executing";

  return (
    <AnimatePresence mode="wait">
      {isMinimized ? (
        <motion.div
          key="minimized"
          layoutId="chronos-avatar-shell"
          className={styles.minimizedContainer}
          onClick={() => setIsMinimized(false)}
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
          initial={{ opacity: 0, scale: 0.6 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.6 }}
          whileHover={{ scale: 1.08 }}
          whileTap={{ scale: 0.94 }}
          transition={{ type: "spring", stiffness: 320, damping: 22 }}
        >
          <motion.div
            className={styles.minimizedButton}
            animate={{ y: [0, -4, 0] }}
            transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
          >
            <motion.div
              className={styles.minimizedPulseRing}
              style={{ borderColor: ringColor }}
              animate={isActive ? { scale: [1, 1.35, 1], opacity: [0.6, 0, 0.6] } : { scale: 1, opacity: 0.35 }}
              transition={isActive ? { duration: 1.6, repeat: Infinity, ease: "easeOut" } : undefined}
            />
            <motion.img
              layoutId="chronos-avatar-face"
              src={genioAvatarFace}
              alt="Genio"
              className={styles.minimizedAvatarImg}
            />
          </motion.div>
          <AnimatePresence>
            {isHovered && (result || error) && (
              <motion.div
                className={styles.minimizedTooltip}
                initial={{ opacity: 0, y: -6, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -6, scale: 0.95 }}
                transition={{ duration: 0.18 }}
              >
                {error ?? result}
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      ) : (
        <motion.div
          key="expanded"
          className={styles.portalOverlay}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
        >
          <motion.div
            layoutId="chronos-avatar-shell"
            className={styles.portalContainer}
            initial={{ opacity: 0, scale: 0.92, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.92, y: 12 }}
            transition={{ type: "spring", stiffness: 260, damping: 26 }}
          >
            {/* Avatar section — left side, real mascot artwork, breathing float */}
            <div className={styles.avatarSection}>
              <motion.div
                className={styles.avatarRing}
                animate={{ y: [0, -10, 0] }}
                transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
              >
                <motion.div
                  className={styles.avatarGlow}
                  style={{ background: `radial-gradient(circle, ${ringColor} 0%, transparent 70%)` }}
                  animate={isActive ? { opacity: [0.4, 0.85, 0.4] } : { opacity: 0.4 }}
                  transition={isActive ? { duration: 1.8, repeat: Infinity, ease: "easeInOut" } : undefined}
                />
                <div className={styles.avatarInner}>
                  <motion.img
                    layoutId="chronos-avatar-face"
                    src={genioAvatarFace}
                    alt="Genio"
                    className={styles.avatarImg}
                    animate={isProcessing ? { rotate: [0, -2, 2, 0] } : { rotate: 0 }}
                    transition={isProcessing ? { duration: 2.4, repeat: Infinity, ease: "easeInOut" } : undefined}
                  />
                </div>
              </motion.div>
              {/* Rotating Chronos ring — speed reflects activity */}
              <motion.div
                className={styles.chronosRing}
                style={{ borderColor: ringColor }}
                animate={{ rotate: 360 }}
                transition={{ duration: isActive ? 10 : 28, repeat: Infinity, ease: "linear" }}
              />
            </div>

            {/* Info section — right side */}
            <div className={styles.infoSection}>
              <h2 className={styles.portalTitle}>
                <span className={styles.titleIcon}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
                  </svg>
                </span>
                Chronos Portal
              </h2>

              <SystemMetrics metrics={metrics} />

              {/* Thinking stream — real thought events, animated in one by one */}
              <div className={styles.thinkingStream}>
                <AnimatePresence initial={false}>
                  {thinkingSteps.map((step, i) => (
                    <motion.div
                      key={`th-${i}`}
                      className={styles.thinkingStep}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.25 }}
                    >
                      <span className={styles.stepDot} />
                      {step}
                    </motion.div>
                  ))}
                  {toolActivity.map((act, i) => (
                    <motion.div
                      key={`tool-${i}`}
                      className={styles.thinkingStep}
                      style={{ opacity: 0.9 }}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 0.9, x: 0 }}
                      transition={{ duration: 0.25 }}
                    >
                      <span
                        className={styles.stepDot}
                        style={{ background: act.startsWith("✕") ? "#F44336" : act.startsWith("✓") ? "#4CAF50" : "#00E5FF" }}
                      />
                      {act}
                    </motion.div>
                  ))}
                  {isProcessing && thinkingSteps.length === 0 && toolActivity.length === 0 && (
                    <motion.div
                      key="waiting"
                      className={`${styles.thinkingStep} ${styles.pulse}`}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                    >
                      <span className={`${styles.stepDot} ${styles.active}`} />
                      waiting for agent…
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              <AnimatePresence>
                {error && (
                  <motion.div
                    key="error"
                    className={styles.resultBox}
                    style={{ borderColor: "#F44336", background: "rgba(244,67,54,0.08)" }}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                  >
                    <span style={{ color: "#F44336", fontWeight: 700 }}>✕ {error}</span>
                  </motion.div>
                )}
                {result && !error && (
                  <motion.div
                    key="result"
                    className={styles.resultBox}
                    initial={{ opacity: 0, y: 8, scale: 0.98 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ type: "spring", stiffness: 300, damping: 24 }}
                  >
                    {result}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </motion.div>

          {/* Minimize & Close buttons */}
          <div className={styles.portalButtons}>
            <motion.button
              className={styles.minimizeBtn}
              onClick={() => setIsMinimized(true)}
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.9 }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
            </motion.button>
            {onDismiss && (
              <motion.button
                className={styles.closeBtn}
                onClick={onDismiss}
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </motion.button>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
