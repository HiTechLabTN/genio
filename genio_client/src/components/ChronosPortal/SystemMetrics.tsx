import type { TaskMetrics } from "../../hooks/useTaskProcessor";
import styles from "./ChronosPortal.module.css";

interface SystemMetricsProps {
  metrics: TaskMetrics;
}

function Bar({ label, value, max, color }: { label: string; value: number; max: number; color: string }) {
  const pct = Math.min((value / max) * 100, 100);
  return (
    <div className={styles.barGroup}>
      <div className={styles.barHeader}>
        <span className={styles.barLabel}>{label}</span>
        <span className={styles.barValue}>{value.toFixed(1)}</span>
      </div>
      <div className={styles.barTrack}>
        <div className={styles.barFill} style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}

export default function SystemMetrics({ metrics }: SystemMetricsProps) {
  return (
    <div className={styles.metricsContainer}>
      <Bar label="CPU" value={metrics.cpu} max={100} color="#00E5FF" />
      <Bar label="GPU" value={metrics.gpu} max={100} color="#E040FB" />
      <Bar label="RAM" value={metrics.ram.used} max={metrics.ram.total} color="#FF9800" />
      <Bar label="VRAM" value={metrics.vram.used} max={metrics.vram.total} color="#F44336" />
    </div>
  );
}
