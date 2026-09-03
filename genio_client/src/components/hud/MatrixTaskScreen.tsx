import { memo, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface Props {
  tasks: string[];
  expanded?: boolean;
  onToggle?: () => void;
}

/**
 * MatrixTaskScreen — blur(8px) panel; Arabic matrix rain 'جينيو01ذكاءتونس' opacity .3;
 * pause on document.hidden; task rows staggered; spring 28vh→75vh; click toggles.
 */
const MatrixTaskScreen = memo(function MatrixTaskScreen({ tasks, expanded = false, onToggle }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const raf = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

    let w = 0, h = 0, dpr = 1;
    const chars = "جينيو01ذكاءتونس";
    const cols: { x: number; y: number; speed: number }[] = [];

    function resize() {
      dpr = Math.min(window.devicePixelRatio || 1, 1.6);
      w = canvas!.clientWidth;
      h = canvas!.clientHeight;
      canvas!.width = w * dpr;
      canvas!.height = h * dpr;
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
      cols.length = 0;
      const count = Math.floor(w / 14);
      for (let i = 0; i < count; i++) cols.push({ x: i * 14, y: Math.random() * h, speed: 0.7 + Math.random() * 1.4 });
    }
    resize();
    window.addEventListener("resize", resize);

    function frame() {
      if (document.hidden) {
        raf.current = requestAnimationFrame(frame);
        return;
      }
      ctx!.fillStyle = "rgba(10,14,26,0.18)";
      ctx!.fillRect(0, 0, w, h);
      ctx!.fillStyle = "rgba(34,211,238,0.3)";
      ctx!.font = "12px monospace";
      for (const c of cols) {
        const ch = chars[Math.floor(Math.random() * chars.length)];
        ctx!.fillText(ch, c.x, c.y);
        c.y += c.speed;
        if (c.y > h + 20) c.y = -10;
        // gold occasional
        if (Math.random() < 0.008) {
          ctx!.fillStyle = "rgba(255,215,0,0.55)";
          ctx!.fillText(ch, c.x, c.y);
          ctx!.fillStyle = "rgba(34,211,238,0.3)";
        }
      }
      raf.current = requestAnimationFrame(frame);
    }
    frame();
    return () => {
      cancelAnimationFrame(raf.current);
      window.removeEventListener("resize", resize);
    };
  }, []);

  const [checked, setChecked] = useState<Record<number, boolean>>({});

  return (
    <motion.div
      layout
      onClick={onToggle}
      className="relative cursor-pointer overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04] backdrop-blur-[8px] shadow-[0_8px_32px_rgba(0,0,0,0.45)] [@media(pointer:coarse)]:backdrop-blur-none [@media(pointer:coarse)]:bg-gradient-to-br [@media(pointer:coarse)]:from-[#0f172a]/90 [@media(pointer:coarse)]:to-[#1a0a1e]/85 [@media(pointer:coarse)]:border-white/5"
      animate={{ height: expanded ? "75vh" : "28vh" }}
      transition={{ type: "spring", damping: 22, stiffness: 180 }}
      style={{ willChange: "height" }}
    >
      <canvas ref={canvasRef} className="absolute inset-0 h-full w-full opacity-30" />

      {/* header */}
      <div className="relative z-10 flex items-center justify-between px-4 py-3">
        <span className="font-mono text-xs tracking-widest text-cyan-300/80">TASK MATRIX</span>
        <span className="font-mono text-[10px] text-white/40">{tasks.length} tasks</span>
      </div>

      {/* tasks */}
      <div className="relative z-10 space-y-2 px-4 pb-4">
        <AnimatePresence>
          {(tasks.length ? tasks : ["Waiting for Genio…", "System idle"]).slice(0, 6).map((t, i) => (
            <motion.div
              key={`${t}-${i}`}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }}
              transition={{ delay: i * 0.06, type: "spring", damping: 18 }}
              onClick={(e) => {
                e.stopPropagation();
                setChecked((c) => ({ ...c, [i]: !c[i] }));
              }}
              className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-xs transition-colors ${checked[i] ? "border-emerald-400/30 bg-emerald-500/10 text-emerald-200" : "border-white/10 bg-black/20 text-white/80 hover:border-cyan-300/20"}`}
            >
              <span className={`flex h-4 w-4 items-center justify-center rounded border text-[10px] ${checked[i] ? "bg-emerald-400 text-black border-emerald-400" : "border-white/20 bg-black/30"}`}>
                {checked[i] ? "✓" : "□"}
              </span>
              <span className="truncate font-mono">{t}</span>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {/* bottom fade */}
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-black/30 to-transparent" />
    </motion.div>
  );
});

export default MatrixTaskScreen;
