import { useEffect, useRef } from "react";

interface Props { isThinking: boolean; size?: number; className?: string }

export default function ParticleBrain({ isThinking, size = 52, className = "" }: Props) {
  const ref = useRef<HTMLCanvasElement>(null);
  const raf = useRef<number>(0);

  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext("2d", { alpha: true });
    if (!ctx) return;
    let w = size * 2, h = size * 2;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    c.width = w * dpr; c.height = h * dpr;
    c.style.width = w / 2 + "px"; c.style.height = h / 2 + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const cx = w / 4, cy = h / 4;
    let t = 0;
    const orbits = [
      { r: 22, n: 3, speed: 0.09, color: "#00E5FF" },
      { r: 30, n: 2, speed: -0.065, color: "#FFD700" },
      { r: 38, n: 4, speed: 0.045, color: "#38BDF8" },
    ];

    function frame() {
      t += 1;
      ctx!.clearRect(0, 0, w, h);
      // brain bg glow
      if (isThinking) {
        const g = ctx!.createRadialGradient(cx, cy, 8, cx, cy, 48);
        g.addColorStop(0, "rgba(0,229,255,0.22)");
        g.addColorStop(1, "rgba(0,0,0,0)");
        ctx!.fillStyle = g;
        ctx!.beginPath(); ctx!.arc(cx, cy, 48, 0, Math.PI * 2); ctx!.fill();
      }
      // orbit rings
      for (const o of orbits) {
        ctx!.beginPath();
        ctx!.arc(cx, cy, o.r, 0, Math.PI * 2);
        ctx!.strokeStyle = isThinking ? `${o.color}33` : "rgba(148,163,184,0.18)";
        ctx!.lineWidth = 1;
        ctx!.stroke();
      }
      // particles
      if (isThinking) {
        for (const o of orbits) {
          for (let i = 0; i < o.n; i++) {
            const ang = (t * o.speed) + (Math.PI * 2 * i / o.n);
            const x = cx + Math.cos(ang) * o.r;
            const y = cy + Math.sin(ang) * o.r * 0.72; // slight elliptical
            ctx!.beginPath();
            ctx!.arc(x, y, 3.2, 0, Math.PI * 2);
            ctx!.fillStyle = o.color;
            ctx!.shadowColor = o.color;
            ctx!.shadowBlur = 10;
            ctx!.fill();
            ctx!.shadowBlur = 0;
            // trail
            ctx!.beginPath();
            ctx!.arc(x - Math.cos(ang) * 5, y - Math.sin(ang) * 5 * 0.72, 1.2, 0, Math.PI * 2);
            ctx!.fillStyle = o.color + "88";
            ctx!.fill();
          }
        }
      }
      // nucleus electric spark
      if (isThinking && t % 9 === 0) {
        ctx!.beginPath();
        ctx!.moveTo(cx - 6, cy - 2);
        ctx!.lineTo(cx - 1, cy + 4);
        ctx!.lineTo(cx + 2, cy - 3);
        ctx!.lineTo(cx + 7, cy + 1);
        ctx!.strokeStyle = "rgba(255,255,255,0.9)";
        ctx!.lineWidth = 1.1;
        ctx!.stroke();
      }
      raf.current = requestAnimationFrame(frame);
    }
    raf.current = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf.current);
  }, [isThinking, size]);

  return (
    <div className={`relative flex items-center justify-center ${className}`} style={{ width: size, height: size }}>
      <canvas ref={ref} className="absolute inset-0" />
      <div className="relative z-10 flex h-[68%] w-[68%] items-center justify-center rounded-2xl border border-cyan-400/25 bg-[#020B1E]/80 text-[22px] shadow-[0_0_18px_rgba(0,229,255,0.35)] backdrop-blur">
        🧠
      </div>
      {isThinking && <span className="absolute -right-1 -top-1 h-2.5 w-2.5 animate-pulse rounded-full bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.9)]" />}
    </div>
  );
}
