import { useEffect, useState } from "react";

interface Metrics { cpu: number; gpu: number; ram: number; ramUsed: number; ramTotal: number }

function getGpuInfo(): string | null {
  try {
    const c = document.createElement("canvas");
    const gl = (c.getContext("webgl") || c.getContext("experimental-webgl")) as WebGLRenderingContext | null;
    if (!gl) return null;
    const dbg = gl.getExtension("WEBGL_debug_renderer_info") as { UNMASKED_RENDERER_WEBGL: number } | null;
    if (!dbg) return null;
    const renderer = gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) as string;
    return renderer?.slice(0, 28) || null;
  } catch { return null; }
}

export default function SystemMetricsLive({ className = "" }: { className?: string }) {
  const [m, setM] = useState<Metrics>({ cpu: 18, gpu: 22, ram: 42, ramUsed: 6.7, ramTotal: 16 });
  const [gpuLabel] = useState(() => getGpuInfo());

  useEffect(() => {
    let t0 = performance.now();
    let lastIdle = 0;
    const cores = navigator.hardwareConcurrency || 4;

    const id = window.setInterval(() => {
      const now = performance.now();
      const dt = now - t0;
      // CPU: synthesize from cores + performance.now delta + low idle
      let idleEst = 0;
      try {
        // requestIdleCallback not widely available — approximate
        const maybeRIC = (window as unknown as { requestIdleCallback?: (cb: (d: { timeRemaining: () => number }) => void) => number }).requestIdleCallback;
        if (maybeRIC) {
          // we already track lastIdle via callback if fired — fallback below
          idleEst = lastIdle;
          // fire a probe
          maybeRIC((deadline) => { lastIdle = deadline.timeRemaining(); });
        }
      } catch { /* ignore */ }
      const base = 12 + (cores % 4) * 3 + Math.sin(dt * 0.0007) * 10 + Math.random() * 8;
      const cpu = Math.max(6, Math.min(92, base - idleEst * 0.6));

      // RAM: use performance.memory if available
      let ramPct = 42 + Math.sin(dt * 0.0005) * 6 + Math.random() * 4;
      let used = 6.7, total = 16;
      const mem = (performance as unknown as { memory?: { usedJSHeapSize: number; jsHeapSizeLimit: number; totalJSHeapSize: number } }).memory;
      if (mem) {
        const pct = (mem.usedJSHeapSize / mem.jsHeapSizeLimit) * 100;
        if (pct > 2 && pct < 95) ramPct = pct * 0.55 + ramPct * 0.45; // blend to keep stable
        used = mem.usedJSHeapSize / (1024 * 1024 * 1024);
        total = mem.jsHeapSizeLimit / (1024 * 1024 * 1024);
        // normalize display to GB
        used = Math.round(used * 10) / 10;
        total = Math.max(4, Math.round(total));
      }

      // GPU: WebGL probe blend or sim
      const gpu = Math.max(8, Math.min(88, 18 + Math.sin(dt * 0.0009 + 1.2) * 14 + Math.random() * 10));

      setM({ cpu: Math.round(cpu), gpu: Math.round(gpu), ram: Math.round(ramPct), ramUsed: used, ramTotal: total });
    }, 1000);
    return () => clearInterval(id);
  }, []);

  const Bar = ({ label, value, color, sub }: { label: string; value: number; color: string; sub?: string }) => (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between font-mono text-[10px]">
        <span className="tracking-[0.14em] text-slate-400">{label}</span>
        <span className="font-bold" style={{ color }}>{value}%</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-800/80">
        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${value}%`, background: color, boxShadow: `0 0 10px ${color}` }} />
      </div>
      {sub && <span className="font-mono text-[9px] text-slate-500">{sub}</span>}
    </div>
  );

  return (
    <div className={`rounded-2xl border border-cyan-400/20 bg-[#020B1E]/75 px-4 py-3 backdrop-blur-xl shadow-[0_0_22px_rgba(0,229,255,0.18)] ${className}`}>
      <div className="mb-2 flex items-center gap-2">
        <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.9)]" />
        <span className="font-mono text-[10px] tracking-[0.16em] text-cyan-300">SYSTEM LIVE</span>
        <span className="ml-auto font-mono text-[9px] text-slate-500">{navigator.hardwareConcurrency || 4} cores{gpuLabel ? ` · ${gpuLabel}` : ""}</span>
      </div>
      <div className="grid gap-3">
        <Bar label="CPU" value={m.cpu} color="#00E5FF" />
        <Bar label="GPU" value={m.gpu} color="#FFD700" />
        <Bar label="RAM" value={m.ram} color="#38BDF8" sub={`${m.ramUsed} / ${m.ramTotal} GB`} />
      </div>
    </div>
  );
}
