import { useState } from "react";
import { useTaskProcessor } from "../../hooks/useTaskProcessor";
import SystemMetrics from "./SystemMetrics";
import styles from "./ChronosPortal.module.css";
import type { AgentStatus, ChatEvent, TelemetrySnapshot } from "../../lib/types";

interface ChronosPortalProps {
  chat: ChatEvent[];
  telemetry: TelemetrySnapshot | null;
  agentStatus: AgentStatus;
  onDismiss?: () => void;
}

export default function ChronosPortal({ chat, telemetry, agentStatus, onDismiss }: ChronosPortalProps) {
  const { isMinimized, setIsMinimized, thinkingSteps, toolActivity, metrics, result, error, isProcessing } =
    useTaskProcessor({ chat, telemetry, agentStatus });
  const [isHovered, setIsHovered] = useState(false);

  // Visible when there is any real activity or result/error; hidden if completely idle with no history
  const hasContent = thinkingSteps.length > 0 || toolActivity.length > 0 || !!result || !!error || isProcessing;
  if (!hasContent) return null;

  // Minimized state: floating button in top-right
  if (isMinimized) {
    return (
      <div
        className={styles.minimizedContainer}
        onClick={() => setIsMinimized(false)}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        <div className={styles.minimizedButton}>
          <span className={styles.minimizedIcon}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
            </svg>
          </span>
          <span className={styles.minimizedText}>Chronos</span>
        </div>
        {isHovered && (result || error) && (
          <div className={styles.minimizedTooltip}>{error ?? result}</div>
        )}
      </div>
    );
  }

  return (
    <div className={styles.portalOverlay}>
      <div className={styles.portalContainer}>
        {/* Avatar section — left side */}
        <div className={styles.avatarSection}>
          <div className={styles.avatarRing}>
            <div className={styles.avatarInner}>
              {/* Pixar-style robot avatar */}
              <div className={styles.avatar}>
                {/* Chachia (red hat) */}
                <div className={styles.chachia} />
                <div className={styles.chachiaDome} />
                {/* Head */}
                <div className={styles.head}>
                  {/* Eyes */}
                  <div className={styles.eyeLeft}>
                    <div className={styles.pupil} />
                  </div>
                  <div className={styles.eyeRight}>
                    <div className={styles.pupil} />
                  </div>
                  {/* Beard */}
                  <div className={styles.beard} />
                  {/* Mouth (simplified) */}
                  <div className={styles.mouth} />
                </div>
                {/* Cape */}
                <div className={styles.cape}>
                  <div className={styles.capeG}>G</div>
                </div>
              </div>
            </div>
          </div>
          {/* Rotating Chronos ring */}
          <div className={styles.chronosRing} />
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

          {/* Thinking stream — real thought events */}
          <div className={styles.thinkingStream}>
            {thinkingSteps.map((step, i) => (
              <div key={`th-${i}`} className={styles.thinkingStep}>
                <span className={styles.stepDot} />
                {step}
              </div>
            ))}
            {/* Tool activity — distinct lines, not mixed with thoughts */}
            {toolActivity.map((act, i) => (
              <div key={`tool-${i}`} className={styles.thinkingStep} style={{ opacity: 0.9 }}>
                <span className={styles.stepDot} style={{ background: act.startsWith("✕") ? "#F44336" : act.startsWith("✓") ? "#4CAF50" : "#00E5FF" }} />
                {act}
              </div>
            ))}
            {isProcessing && thinkingSteps.length === 0 && toolActivity.length === 0 && (
              <div className={`${styles.thinkingStep} ${styles.pulse}`}>
                <span className={`${styles.stepDot} ${styles.active}`} />
                waiting for agent…
              </div>
            )}
          </div>

          {/* Error — visible failure state (Phase B requirement) */}
          {error && (
            <div className={styles.resultBox} style={{ borderColor: "#F44336", background: "rgba(244,67,54,0.08)" }}>
              <span style={{ color: "#F44336", fontWeight: 700 }}>✕ {error}</span>
            </div>
          )}

          {/* Result — real answer, not random DONE_MESSAGES */}
          {result && !error && (
            <div className={styles.resultBox}>
              {result}
            </div>
          )}
        </div>
      </div>

      {/* Minimize & Close buttons */}
      <div className={styles.portalButtons}>
        <button className={styles.minimizeBtn} onClick={() => setIsMinimized(true)}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
        </button>
        {onDismiss && (
          <button className={styles.closeBtn} onClick={onDismiss}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}
