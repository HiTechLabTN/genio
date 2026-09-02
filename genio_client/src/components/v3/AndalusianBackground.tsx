import { useEffect, useRef } from "react";

/**
 * AndalusianBackground — v3.0
 * Canvas 2D: navy #020B1E -> #0A1A3A gradient, golden radial glow,
 * repeating hexagonal star lattice (rgba 255,215,0,0.15), floating particles,
 * faint Kufic calligraphy texture.
 * All RAF/resize listeners cleaned up.
 */
export default function AndalusianBackground() {
  const ref = useRef<HTMLCanvasElement>(null);
  const raf = useRef<number>(0);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

    let w = 0, h = 0, dpr = 1;
    const particles: { x: number; y: number; r: number; vx: number; vy: number; a: number }[] = [];
    for (let i = 0; i < 42; i++) {
      particles.push({
        x: Math.random(), y: Math.random(), r: 0.6 + Math.random() * 1.6,
        vx: (Math.random() - 0.5) * 0.00035, vy: (Math.random() - 0.5) * 0.00035,
        a: 0.25 + Math.random() * 0.55,
      });
    }
    let t = 0;

    function resize() {
      // eslint-disable-next-line react-hooks/refs
      if (!canvas) return;
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = window.innerWidth; h = window.innerHeight;
      canvas.width = w * dpr; canvas.height = h * dpr;
      canvas.style.width = w + "px"; canvas.style.height = h + "px";
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    resize();
    window.addEventListener("resize", resize);

    function drawHex(x: number, y: number, r: number) {
      ctx!.beginPath();
      for (let i = 0; i < 6; i++) {
        const a = (Math.PI / 3) * i - Math.PI / 6;
        const px = x + Math.cos(a) * r;
        const py = y + Math.sin(a) * r;
        if (i === 0) ctx!.moveTo(px, py); else ctx!.lineTo(px, py);
      }
      ctx!.closePath();
      ctx!.stroke();
      // inner star
      ctx!.beginPath();
      for (let i = 0; i < 6; i++) {
        const a = (Math.PI / 3) * i - Math.PI / 6;
        const px = x + Math.cos(a) * r * 0.58;
        const py = y + Math.sin(a) * r * 0.58;
        if (i === 0) ctx!.moveTo(px, py); else ctx!.lineTo(px, py);
      }
      ctx!.closePath();
      ctx!.stroke();
      // cross lines
      ctx!.beginPath();
      for (let i = 0; i < 3; i++) {
        const a = (Math.PI / 3) * i;
        ctx!.moveTo(x + Math.cos(a) * r, y + Math.sin(a) * r);
        ctx!.lineTo(x - Math.cos(a) * r, y - Math.sin(a) * r);
      }
      ctx!.stroke();
    }

    const kufic = ["﷽", "✦", "◆", "✺"];

    function frame() {
      t += 0.008;
      // gradient bg
      const g = ctx!.createLinearGradient(0, 0, 0, h);
      g.addColorStop(0, "#020B1E");
      g.addColorStop(0.55, "#07152f");
      g.addColorStop(1, "#0A1A3A");
      ctx!.fillStyle = g;
      ctx!.fillRect(0, 0, w, h);

      // golden radial glow center top
      const rg = ctx!.createRadialGradient(w * 0.5, h * 0.42, 0, w * 0.5, h * 0.42, Math.max(w, h) * 0.85);
      rg.addColorStop(0, "rgba(255,215,0,0.09)");
      rg.addColorStop(0.35, "rgba(255,215,0,0.03)");
      rg.addColorStop(1, "rgba(0,0,0,0)");
      ctx!.fillStyle = rg;
      ctx!.fillRect(0, 0, w, h);

      // cyan orb faint behind mascot area
      const cg = ctx!.createRadialGradient(w * 0.5, h * 0.52, 0, w * 0.5, h * 0.52, w * 0.45);
      cg.addColorStop(0, "rgba(0,229,255,0.07)");
      cg.addColorStop(1, "rgba(0,0,0,0)");
      ctx!.fillStyle = cg;
      ctx!.fillRect(0, 0, w, h);

      // hex lattice
      ctx!.strokeStyle = "rgba(255,215,0,0.15)";
      ctx!.lineWidth = 0.85;
      // use r=34 for denser tiling
      const rr = 34;
      const stepX = rr * 1.5 * 2;
      const stepY = rr * Math.sqrt(3);
      const cols = Math.ceil(w / stepX) + 2;
      const rows = Math.ceil(h / stepY) + 2;
      const off = (t * 6) % stepX; // subtle drift
      for (let row = -1; row < rows; row++) {
        for (let col = -1; col < cols; col++) {
          const x = col * stepX + (row % 2 ? stepX / 2 : 0) - off * 0.15;
          const y = row * stepY - 14;
          // fade with distance from center
          const dist = Math.hypot(x - w * 0.5, y - h * 0.5) / (Math.max(w, h) * 0.7);
          const alpha = Math.max(0, 0.16 - dist * 0.12);
          if (alpha < 0.015) continue;
          ctx!.strokeStyle = `rgba(255,215,0,${alpha})`;
          drawHex(x, y, rr);
        }
      }

      // faint Kufic marks
      ctx!.fillStyle = "rgba(255,215,0,0.045)";
      ctx!.font = "12px serif";
      ctx!.textAlign = "center";
      for (let i = 0; i < 14; i++) {
        const x = (w * (0.08 + 0.84 * ((i * 0.618) % 1)));
        const y = (h * (0.12 + 0.78 * ((i * 0.392) % 1))) + Math.sin(t * 0.7 + i) * 6;
        ctx!.fillText(kufic[i % kufic.length], x, y);
      }

      // floating golden particles
      for (const p of particles) {
        p.x += p.vx + Math.sin(t + p.r) * 0.00008;
        p.y += p.vy + Math.cos(t * 0.6 + p.x * 6) * 0.00008;
        if (p.x < 0) p.x += 1; if (p.x > 1) p.x -= 1;
        if (p.y < 0) p.y += 1; if (p.y > 1) p.y -= 1;
        const px = p.x * w;
        const py = p.y * h;
        const tw = 0.5 + 0.5 * Math.sin(t * 1.2 + p.x * 10);
        ctx!.beginPath();
        ctx!.arc(px, py, p.r, 0, Math.PI * 2);
        ctx!.fillStyle = `rgba(255,215,0,${p.a * (0.5 + tw * 0.5)})`;
        ctx!.shadowColor = "rgba(255,215,0,0.9)";
        ctx!.shadowBlur = 6;
        ctx!.fill();
        ctx!.shadowBlur = 0;
      }

      raf.current = requestAnimationFrame(frame);
    }
    raf.current = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf.current);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <canvas
      ref={ref}
      aria-hidden
      className="pointer-events-none absolute inset-0 h-full w-full"
      style={{ zIndex: 0 }}
    />
  );
}
