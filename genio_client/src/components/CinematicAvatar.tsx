import { useEffect, useRef, useState } from "react";

type AvatarState = "idle" | "thinking" | "streaming" | "listening";

const SRC: Record<AvatarState, string> = {
  idle: "/media/states/idle.webm",
  thinking: "/media/states/listen.webm",
  streaming: "/media/states/talk.webm",
  listening: "/media/states/listen.webm",
};

/**
 * CinematicAvatar — 2.5D cinématique (remplace le canvas Three.js/GLB lourd).
 * - Vidéos WebM en boucle par état, crossfade CSS (aucun WebGL, mobile-safe).
 * - Follow-focus : perspective(600px) rotateX/Y liés au curseur/tactile.
 * - Ready : respiration (scale) + clignement (scaleY bref) + dérives de tête.
 * - Thinking : halo violet pulsé, synchronisé avec la telemetry bar.
 * - Streaming : talk.webm + pulsation couplée à `audioLevel` (VODER).
 */
export default function CinematicAvatar({
  audioLevel = 0,
  status = "idle",
}: {
  audioLevel?: number;
  status?: string;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [tilt, setTilt] = useState({ x: 0, y: 0 });
  const [blink, setBlink] = useState(false);

  const state: AvatarState =
    status === "thinking"
      ? "thinking"
      : status === "answering" || status === "executing" || status === "completed"
        ? "streaming"
        : status === "listening"
          ? "listening"
          : "idle";

  // Follow-focus (souris + tactile), borné à ±7°.
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    let raf = 0;
    const onMove = (cx: number, cy: number) => {
      const r = el.getBoundingClientRect();
      const nx = (cx - (r.left + r.width / 2)) / (r.width / 2);
      const ny = (cy - (r.top + r.height / 2)) / (r.height / 2);
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() =>
        setTilt({
          x: Math.max(-7, Math.min(7, -ny * 7)),
          y: Math.max(-7, Math.min(7, nx * 7)),
        }),
      );
    };
    const mouse = (e: MouseEvent) => onMove(e.clientX, e.clientY);
    const touch = (e: TouchEvent) => {
      const t = e.touches[0];
      if (t) onMove(t.clientX, t.clientY);
    };
    const leave = () => setTilt({ x: 0, y: 0 });
    window.addEventListener("mousemove", mouse, { passive: true });
    window.addEventListener("touchmove", touch, { passive: true });
    window.addEventListener("mouseout", leave);
    return () => {
      window.removeEventListener("mousemove", mouse);
      window.removeEventListener("touchmove", touch);
      window.removeEventListener("mouseout", leave);
      cancelAnimationFrame(raf);
    };
  }, []);

  // Clignement toutes les ~4s (état Ready uniquement).
  useEffect(() => {
    if (state !== "idle") return;
    const id = window.setInterval(() => {
      setBlink(true);
      window.setTimeout(() => setBlink(false), 140);
    }, 4000);
    return () => window.clearInterval(id);
  }, [state]);

  const glow =
    state === "thinking"
      ? "0 0 60px rgba(167,139,250,0.55), 0 0 140px rgba(167,139,250,0.25)"
      : state === "streaming"
        ? `0 0 ${30 + audioLevel * 60}px rgba(52,211,153,${0.25 + audioLevel * 0.5})`
        : "0 0 40px rgba(34,211,238,0.20)";

  return (
    <div ref={wrapRef} className="cinematic-avatar relative h-full w-full overflow-hidden">
      {(Object.keys(SRC) as AvatarState[]).map((k) => (
        <video
          key={k}
          src={SRC[k]}
          autoPlay
          muted
          loop
          playsInline
          preload={k === "idle" ? "auto" : "metadata"}
          className="absolute inset-0 h-full w-full object-cover transition-opacity duration-700"
          style={{ opacity: state === k ? 1 : 0 }}
        />
      ))}
      <div
        className="absolute inset-0 transition-transform duration-150 ease-out"
        style={{
          transform: `perspective(600px) rotateX(${tilt.x}deg) rotateY(${tilt.y}deg) scale(${state === "idle" ? 1.015 : 1}) scaleY(${blink ? 0.985 : 1})`,
          boxShadow: `inset ${glow}`,
        }}
      />
      {state === "thinking" ? (
        <div className="absolute inset-0 animate-pulse bg-violet-500/10" />
      ) : null}
      <style>{`@keyframes cinematic-breathe{0%,100%{transform:scale(1)}50%{transform:scale(1.02)}} .cinematic-avatar video{animation:cinematic-breathe 4.5s ease-in-out infinite}`}</style>
    </div>
  );
}
