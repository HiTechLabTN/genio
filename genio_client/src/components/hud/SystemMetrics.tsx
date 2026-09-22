import { memo, useEffect, useState } from "react";

interface Telemetry {
  cpu_percent?: number;
  ram_percent?: number;
  ram_used_gb?: number;
  ram_total_gb?: number;
  gpu?: { used_gb?: number; total_gb?: number; vram_pct?: number };
  // optional network/temp from telemetry
  net_kbs?: number;
  temp_c?: number;
}

interface Props {
  telemetry?: Telemetry | null;
  isCloud?: boolean;
}

/**
 * SystemMetrics — circular SVG gauges
 * - real CPU/GPU/RAM (+NET/TEMP/VRAM if available)
 * - memo(); 1s internal poll; must NOT re-render mascot (isolated via memo)
 */
const SystemMetrics = memo(function SystemMetrics({ telemetry, isCloud = false }: Props) {
  // P3: when cloud is active, never show dead 0% rings — show badge instead
  if (isCloud) {
    return (
      <div className="flex items-center gap-2 rounded-full border border-cyan-400/20 bg-cyan-500/10 px-4 py-2 backdrop-blur">
        <span className="text-sm">☁️</span>
        <span className="font-mono text-[10px] font-bold tracking-widest text-cyan-300">CLOUD MODE</span>
        <span className="font-mono text-[9px] text-white/50">Gemini • live</span>
      </div>
    );
  }
  // local poll to avoid parent re-render churn — snapshot copy
  const [snap, setSnap] = useState<Telemetry | null>(telemetry ?? null);
  useEffect(() => {
    setSnap(telemetry ?? null);
    const id = window.setInterval(() => {
      if (telemetry) setSnap({ ...telemetry });
    }, 1000);
    return () => clearInterval(id);
  }, [telemetry]);

  const cpu = Math.round((snap?.cpu_percent ?? 0) * 10) / 10;
  const gpu = snap?.gpu?.vram_pct ?? (snap?.gpu?.used_gb && snap?.gpu?.total_gb ? (snap.gpu.used_gb / snap.gpu.total_gb) * 100 : 0);
  const ram = snap?.ram_percent ?? (snap?.ram_used_gb && snap?.ram_total_gb ? (snap.ram_used_gb / snap.ram_total_gb) * 100 : 0);
  const vram = snap?.gpu?.vram_pct ?? 0;
  const net = snap?.net_kbs ?? 0;
  const temp = snap?.temp_c ?? 0;

  const gauges = [
    { label: "CPU", value: cpu, color: "#22d3ee" },
    { label: "GPU", value: Math.round(gpu * 10) / 10, color: "#a78bfa" },
    { label: "RAM", value: Math.round(ram * 10) / 10, color: "#f472b6" },
    ...(vram ? [{ label: "VRAM", value: Math.round(vram * 10) / 10, color: "#facc15" }] : []),
    ...(net ? [{ label: "NET", value: Math.round(net), color: "#4ade80", suffix: "KB/s" }] : []),
    ...(temp ? [{ label: "TEMP", value: Math.round(temp), color: "#fb7185", suffix: "°C" }] : []),
  ].slice(0, 6);

  return (
    <div className="grid grid-cols-3 gap-3">
      {gauges.map((g) => {
        const pct = Math.min(100, Math.max(0, g.value as number));
        const dash = (pct / 100) * 163.36; // 2πr where r=26
        return (
          <div key={g.label} className="flex flex-col items-center gap-1">
            <div className="relative h-[64px] w-[64px]">
              <svg width={64} height={64} className="-rotate-90">
                <circle cx={32} cy={32} r={26} stroke="rgba(255,255,255,0.08)" strokeWidth={6} fill="none" />
                <circle
                  cx={32}
                  cy={32}
                  r={26}
                  stroke={g.color}
                  strokeWidth={6}
                  fill="none"
                  strokeLinecap="round"
                  strokeDasharray={`${dash} 163.36`}
                  style={{ transition: "stroke-dasharray 0.6s ease" }}
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="font-mono text-[11px] font-bold text-white">
                  {Math.round(g.value as number)}
                  {(g as { suffix?: string }).suffix ?? "%"}
                </span>
              </div>
            </div>
            <span className="font-mono text-[9px] tracking-widest text-white/60">{g.label}</span>
          </div>
        );
      })}
    </div>
  );
});

export default SystemMetrics;
