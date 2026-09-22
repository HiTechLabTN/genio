import { useEffect, useRef } from "react";

/**
 * AndalusianBackground — v3.1
 * Fidèle à l'image de référence du mascot (assets-pipeline/reference-views/original_hero.png) :
 * fond navy profond -> violet sombre, plusieurs grandes rosaces/médaillons cyan à
 * 8-12 branches (imbriquées, superposées, tailles variées) façon zellige andalou,
 * lueur radiale cyan centrale, poussière dorée flottante.
 * Canvas 2D, tout RAF/resize nettoyé au unmount.
 */
function drawStarMedallion(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  radius: number,
  points: number,
  rotation: number,
  alpha: number,
  color: string,
) {
  // Anneau extérieur (cercle fin)
  ctx.beginPath();
  ctx.arc(cx, cy, radius, 0, Math.PI * 2);
  ctx.strokeStyle = `rgba(${color},${alpha * 0.5})`;
  ctx.lineWidth = 1;
  ctx.stroke();

  // Étoile à N branches (2 couches imbriquées, rotation opposée) — motif rosace
  for (const layer of [0, 1]) {
    const layerRadius = radius * (layer === 0 ? 1 : 0.62);
    const layerRot = rotation + (layer === 1 ? Math.PI / points : 0);
    ctx.beginPath();
    for (let i = 0; i <= points * 2; i++) {
      const a = (Math.PI / points) * i + layerRot;
      const r = i % 2 === 0 ? layerRadius : layerRadius * 0.42;
      const px = cx + Math.cos(a) * r;
      const py = cy + Math.sin(a) * r;
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.closePath();
    ctx.strokeStyle = `rgba(${color},${alpha * (layer === 0 ? 0.55 : 0.4)})`;
    ctx.lineWidth = layer === 0 ? 1.1 : 0.8;
    ctx.stroke();
  }

  // Anneau intérieur fin
  ctx.beginPath();
  ctx.arc(cx, cy, radius * 0.68, 0, Math.PI * 2);
  ctx.strokeStyle = `rgba(${color},${alpha * 0.3})`;
  ctx.lineWidth = 0.7;
  ctx.stroke();
}

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

    // Médaillons cyan (rosaces à 8-12 branches) — dispersés comme dans la référence :
    // grands médaillons dans les coins/haut, plus petits ailleurs, rotation lente indépendante.
    // Alphas et rayons relevés d'un cran par rapport à la v3.1 — la référence
    // (assets-pipeline/reference-views/original_hero.png) a des rosaces bien plus
    // visibles/glow que ce que rendait la v3.1 en pratique (0.10-0.16 se voyait à peine).
    const medallions = [
      { x: 0.14, y: 0.16, r: 0.26, points: 8, speed: 0.012, phase: 0, alpha: 0.30 },
      { x: 0.87, y: 0.12, r: 0.19, points: 10, speed: -0.009, phase: 1.4, alpha: 0.26 },
      { x: 0.06, y: 0.62, r: 0.16, points: 8, speed: 0.015, phase: 2.6, alpha: 0.24 },
      { x: 0.92, y: 0.55, r: 0.23, points: 12, speed: -0.011, phase: 0.7, alpha: 0.27 },
      { x: 0.5, y: 0.08, r: 0.14, points: 8, speed: 0.02, phase: 3.1, alpha: 0.20 },
      { x: 0.22, y: 0.85, r: 0.18, points: 10, speed: -0.013, phase: 1.9, alpha: 0.22 },
      { x: 0.78, y: 0.86, r: 0.15, points: 8, speed: 0.016, phase: 0.3, alpha: 0.20 },
      { x: 0.5, y: 0.5, r: 0.30, points: 8, speed: 0.008, phase: 0.9, alpha: 0.16 },
    ];

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

      // touche dorée discrète (accent, pas dominante — la référence est cyan-dominante)
      const rg = ctx!.createRadialGradient(w * 0.5, h * 0.42, 0, w * 0.5, h * 0.42, Math.max(w, h) * 0.85);
      rg.addColorStop(0, "rgba(255,215,0,0.05)");
      rg.addColorStop(0.35, "rgba(255,215,0,0.02)");
      rg.addColorStop(1, "rgba(0,0,0,0)");
      ctx!.fillStyle = rg;
      ctx!.fillRect(0, 0, w, h);

      // halo cyan derrière le mascot — plus marqué, comme la plateforme lumineuse de la référence
      const cg = ctx!.createRadialGradient(w * 0.5, h * 0.58, 0, w * 0.5, h * 0.58, w * 0.5);
      cg.addColorStop(0, "rgba(34,211,238,0.22)");
      cg.addColorStop(0.5, "rgba(34,211,238,0.08)");
      cg.addColorStop(1, "rgba(0,0,0,0)");
      ctx!.fillStyle = cg;
      ctx!.fillRect(0, 0, w, h);

      // Rosaces / médaillons cyan à 8-12 branches — façon zellige andalou,
      // positions fixes en proportion de l'écran, tailles/vitesses variées,
      // fidèle à la composition de la référence (plusieurs médaillons superposés).
      for (const m of medallions) {
        const cx = m.x * w;
        const cy = m.y * h;
        const radius = m.r * Math.min(w, h);
        const rotation = t * m.speed + m.phase;
        drawStarMedallion(ctx!, cx, cy, radius, m.points, rotation, m.alpha, "34,211,238");
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
