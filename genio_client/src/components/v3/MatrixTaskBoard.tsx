import { useEffect, useRef } from "react";

interface Props {
  tasks: string[];
  isThinking: boolean;
  className?: string;
}

/**
 * MatrixTaskBoard — semi-transparent overlay z:1
 * Canvas green digital rain + scrolling task lines (> TASK_01: ...)
 */
export default function MatrixTaskBoard({ tasks, isThinking, className = "" }: Props) {
  const ref = useRef<HTMLCanvasElement>(null);
  const raf = useRef<number>(0);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;
    let w = 0, h = 0, dpr = 1;
    let cols = 0;
    let drops: number[] = [];
    const chars = "01ABCDEFGHIJKLMNOPQRSTUVWXYZ$#*+";
    function resize() {
      // eslint-disable-next-line react-hooks/refs
      if (!canvas || !canvas.parentElement) return;
      const rect = canvas.parentElement.getBoundingClientRect();
      w = rect.width; h = rect.height;
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = w * dpr; canvas.height = h * dpr;
      canvas.style.width = w + "px"; canvas.style.height = h + "px";
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
      cols = Math.floor(w / 14);
      drops = Array.from({ length: cols }, () => Math.random() * h);
    }
    resize();
    const ro = new ResizeObserver(resize);
    if (canvas.parentElement) ro.observe(canvas.parentElement);
    window.addEventListener("resize", resize);

    let t = 0;
    function frame() {
      t += 1;
      // fade
      ctx!.fillStyle = "rgba(2,11,30,0.16)";
      ctx!.fillRect(0, 0, w, h);
      ctx!.font = "12px monospace";
      const speed = isThinking ? 2.2 : 0.7;
      for (let i = 0; i < cols; i++) {
        const x = i * 14;
        const y = drops[i];
        const ch = chars[Math.floor(Math.random() * chars.length)];
        // head bright
        ctx!.fillStyle = "rgba(52,211,153,0.95)";
        ctx!.fillText(ch, x, y);
        // tail dim
        ctx!.fillStyle = "rgba(52,211,153,0.22)";
        ctx!.fillText(ch, x, y - 14);
        drops[i] += 8 * speed + Math.random() * 6;
        if (drops[i] > h && Math.random() > 0.96) drops[i] = 0;
      }
      // every ~8 frames draw task lines as overlay code
      if (tasks.length && t % 10 === 0) {
        ctx!.fillStyle = "rgba(110,231,183,0.0)"; // no-op, tasks rendered as DOM below
      }
      raf.current = requestAnimationFrame(frame);
    }
    raf.current = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf.current);
      ro.disconnect();
      window.removeEventListener("resize", resize);
    };
  }, [isThinking, tasks]);

  const lines = tasks.length ? tasks : (isThinking ? ["> CHRONOS: SYNCING...", "> MATRIX: ANALYZING..."] : []);

  return (
    <div className={`pointer-events-none absolute inset-0 overflow-hidden rounded-[1.4rem] border border-emerald-500/10 ${className}`} style={{ zIndex: 1, opacity: 0.3 }}>
      <canvas ref={ref} className="absolute inset-0 h-full w-full" />
      <div className="absolute inset-0 bg-gradient-to-b from-emerald-500/[0.04] via-transparent to-cyan-500/[0.04]" />
      {/* scrolling task lines */}
      <div className="absolute inset-x-0 bottom-0 flex flex-col gap-1 p-3 font-mono text-[10px] leading-tight text-emerald-300">
        {lines.slice(-6).map((ln, i) => (
          <div key={i} className="truncate opacity-80" style={{ textShadow: "0 0 8px rgba(52,211,153,0.8)" }}>
            {ln.startsWith(">") ? ln : `> TASK_${String(i + 1).padStart(2, "0")}: ${ln.toUpperCase()}`}
          </div>
        ))}
      </div>
    </div>
  );
}
