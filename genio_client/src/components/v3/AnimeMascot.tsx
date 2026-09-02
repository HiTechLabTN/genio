import { useEffect, useRef, useState } from "react";

interface Props {
  listening?: boolean;
  isThinking?: boolean;
  faceTrack?: boolean;
  size?: number;
  className?: string;
}

/**
 * AnimeMascot — 2D div/SVG based, no three.js.
 * Red Tarboush (Fez) + tassel, anime eyes with tracking, breathing, blink.
 * Intro hologram 2.2s then settles. Eyes follow mouse or MediaPipe if available.
 */
export default function AnimeMascot({ listening = false, isThinking = false, faceTrack = true, size = 320, className = "" }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [intro, setIntro] = useState(true);
  const [eye, setEye] = useState({ x: 0, y: 0 });
  const [blink, setBlink] = useState(false);
  const targetRef = useRef({ x: 0, y: 0 });

  // intro timer
  useEffect(() => {
    const t = window.setTimeout(() => setIntro(false), 2200);
    return () => clearTimeout(t);
  }, []);

  // blink loop
  useEffect(() => {
    let id: number;
    function schedule() {
      id = window.setTimeout(() => {
        setBlink(true);
        window.setTimeout(() => setBlink(false), 130);
        schedule();
      }, 2200 + Math.random() * 2800);
    }
    schedule();
    return () => clearTimeout(id);
  }, []);

  // face/mouse tracking
  useEffect(() => {
    if (!faceTrack) return;
    let raf = 0;
    let smoothX = 0, smoothY = 0;

    function onMouse(e: MouseEvent) {
      const el = wrapRef.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;
      const nx = (e.clientX - cx) / (r.width * 0.5);
      const ny = (e.clientY - cy) / (r.height * 0.5);
      targetRef.current = { x: Math.max(-1, Math.min(1, nx)), y: Math.max(-1, Math.min(1, ny)) };
    }
    function onTouch(e: TouchEvent) {
      if (!e.touches[0]) return;
      const el = wrapRef.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;
      const nx = (e.touches[0].clientX - cx) / (r.width * 0.5);
      const ny = (e.touches[0].clientY - cy) / (r.height * 0.5);
      targetRef.current = { x: Math.max(-1, Math.min(1, nx)), y: Math.max(-1, Math.min(1, ny)) };
    }

    // MediaPipe FaceMesh stub — keep mouse fallback to avoid extra bundle weight.
    // If @mediapipe/face_mesh is needed later, dynamic import can be added here.

    window.addEventListener("mousemove", onMouse, { passive: true });
    window.addEventListener("touchmove", onTouch, { passive: true });

    function loop() {
      const tx = targetRef.current.x;
      const ty = targetRef.current.y;
      smoothX += (tx - smoothX) * 0.09;
      smoothY += (ty - smoothY) * 0.09;
      setEye({ x: smoothX, y: smoothY });
      raf = requestAnimationFrame(loop);
    }
    raf = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("mousemove", onMouse);
      window.removeEventListener("touchmove", onTouch);
    };
  }, [faceTrack]);

  const s = size;
  const breath = listening ? 1.035 : 1;
  const eyeDx = eye.x * 7;
  const eyeDy = eye.y * 4.5;

  return (
    <div
      ref={wrapRef}
      className={`relative select-none ${className}`}
      style={{ width: s, height: s * 1.18, display: "flex", alignItems: "center", justifyContent: "center" }}
    >
      {/* holographic intro overlay */}
      {intro && (
        <div className="pointer-events-none absolute inset-0 z-20 overflow-hidden rounded-[2.2rem]">
          <div className="absolute inset-0 animate-pulse bg-gradient-to-b from-cyan-400/25 via-transparent to-cyan-400/15" style={{ animationDuration: "0.28s" }} />
          <div className="absolute inset-0 opacity-40" style={{ backgroundImage: "repeating-linear-gradient(0deg, transparent 0 2px, rgba(0,229,255,0.18) 2px, transparent 3px)" }} />
          <div className="absolute inset-x-0 top-1/2 h-[2px] -translate-y-1/2 bg-cyan-300 shadow-[0_0_18px_rgba(0,229,255,0.9)] animate-[scan_0.9s_linear_infinite]" />
          <style>{`@keyframes scan{0%{top:8%}100%{top:92%}}`}</style>
        </div>
      )}

      {/* breathing wrapper */}
      <div
        className="relative"
        style={{
          transform: `scale(${breath})`,
          transition: "transform 0.45s ease",
          filter: intro ? "brightness(1.25) drop-shadow(0 0 22px rgba(0,229,255,0.9)) contrast(1.1)" : "drop-shadow(0 18px 28px rgba(0,0,0,0.55))",
          opacity: intro ? 0.92 : 1,
        }}
      >
        {/* glow rings */}
        <div className="pointer-events-none absolute left-1/2 top-[88%] h-10 w-[78%] -translate-x-1/2 rounded-full bg-cyan-400/18 blur-[14px]" />
        <div className="pointer-events-none absolute left-1/2 top-[92%] h-6 w-[62%] -translate-x-1/2 rounded-full bg-cyan-400/25 blur-[10px]" />

        {/* === SVG mascot — Fez + robot === */}
        <svg
          viewBox="0 0 280 320"
          width={s * 0.92}
          height={s * 1.05}
          className="block"
          style={{
            overflow: "visible",
            animation: isThinking ? "floatThink 1.2s ease-in-out infinite" : "floatIdle 3.2s ease-in-out infinite",
          }}
        >
          <style>{`
            @keyframes floatIdle{0%,100%{transform:translateY(0)}50%{transform:translateY(-7px)}}
            @keyframes floatThink{0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}
          `}</style>

          {/* body / robe */}
          <ellipse cx="140" cy="298" rx="56" ry="9" fill="rgba(0,229,255,0.18)" />
          <path d="M78 158 C 78 158 92 248 140 254 C 188 248 202 158 202 158 L 196 148 L 84 148 Z" fill="#8B0F1A" stroke="#FFD700" strokeWidth="1.2" />
          <path d="M84 148 L 86 172 L 74 176 L 68 156 Z" fill="#8B0F1A" stroke="#FFD700" strokeWidth="0.9" />
          <path d="M196 148 L 194 172 L 206 176 L 212 156 Z" fill="#8B0F1A" stroke="#FFD700" strokeWidth="0.9" />
          {/* gold trim */}
          <path d="M140 150 L 138 248" stroke="#FFD700" strokeWidth="1.6" opacity="0.95" />
          <path d="M108 150 Q 112 190 118 246" stroke="#FFD700" strokeWidth="1" opacity="0.8" />
          <path d="M172 150 Q 168 190 162 246" stroke="#FFD700" strokeWidth="1" opacity="0.8" />
          <path d="M84 148 Q 140 168 196 148" stroke="#FFC94A" strokeWidth="1" fill="none" opacity="0.9" />
          {/* emblem */}
          <g transform="translate(140 196)">
            <path d="M0 -18 L8 -8 L12 4 L0 16 L-12 4 L-8 -8 Z" fill="none" stroke="#FFD700" strokeWidth="1.4" />
            <path d="M0 -14 C 6 -10 10 -4 6 2 C 2 6 -2 6 -6 2 C -10 -4 -6 -10 0 -14" fill="#FFD700" opacity="0.95" />
            <circle cx="0" cy="-2" r="1.8" fill="#8B0F1A" />
            <path d="M-10 8 Q 0 14 10 8" stroke="#FFD700" strokeWidth="1" fill="none" />
          </g>
          {/* G badge */}
          <g transform="translate(140 222)">
            <circle r="18" fill="#F8F3E6" stroke="#FFD700" strokeWidth="1.3" />
            <text x="0" y="7" textAnchor="middle" fontFamily="serif" fontWeight="800" fontSize="20" fill="#8B0F1A">G</text>
          </g>

          {/* arms — listening pose */}
          <g opacity={listening ? 1 : 0.98}>
            {/* right arm waving / hand cup ear when listening */}
            <g transform={listening ? "translate(58 132) rotate(-18)" : "translate(50 138) rotate(-8)"}>
              <rect x="-14" y="0" width="28" height="54" rx="12" fill="#E8EEF6" stroke="#9CA3AF" strokeWidth="0.9" />
              <rect x="-10" y="46" width="20" height="10" rx="5" fill="#B8C0CC" />
              {/* hand */}
              <g transform="translate(0 4)">
                <ellipse cx="0" cy="-2" rx="22" ry="18" fill="#F1F5F9" stroke="#9CA3AF" strokeWidth="0.9" />
                {/* fingers */}
                <ellipse cx="-12" cy="-10" rx="5.5" ry="10" fill="#F1F5F9" stroke="#9CA3AF" strokeWidth="0.7" />
                <ellipse cx="-3" cy="-14" rx="5.5" ry="11" fill="#F1F5F9" stroke="#9CA3AF" strokeWidth="0.7" />
                <ellipse cx="7" cy="-13" rx="5.2" ry="10" fill="#F1F5F9" stroke="#9CA3AF" strokeWidth="0.7" />
                <ellipse cx="15" cy="-7" rx="4.8" ry="8.5" fill="#F1F5F9" stroke="#9CA3AF" strokeWidth="0.7" />
                <ellipse cx="11" cy="6" rx="7" ry="6" fill="#F1F5F9" stroke="#9CA3AF" strokeWidth="0.7" />
              </g>
            </g>
            {/* left arm */}
            <g transform="translate(222 146) rotate(12)">
              <rect x="-14" y="0" width="28" height="52" rx="12" fill="#E8EEF6" stroke="#9CA3AF" strokeWidth="0.9" />
              <circle cx="0" cy="58" r="14" fill="#1F2937" stroke="#4B5563" strokeWidth="0.9" />
              <circle cx="0" cy="58" r="6" fill="#0F172A" />
            </g>
          </g>

          {/* legs */}
          <g transform="translate(0 248)">
            <rect x="110" y="0" width="26" height="34" rx="11" fill="#E8EEF6" stroke="#9CA3AF" strokeWidth="0.9" />
            <rect x="144" y="0" width="26" height="34" rx="11" fill="#E8EEF6" stroke="#9CA3AF" strokeWidth="0.9" />
            <ellipse cx="123" cy="36" rx="16" ry="7" fill="#0F172A" />
            <ellipse cx="157" cy="36" rx="16" ry="7" fill="#0F172A" />
          </g>

          {/* head */}
          <g transform="translate(140 96)">
            {/* side earphones */}
            <ellipse cx="-62" cy="12" rx="10" ry="20" fill="#E8EEF6" stroke="#9CA3AF" strokeWidth="1" />
            <ellipse cx="62" cy="12" rx="10" ry="20" fill="#E8EEF6" stroke="#9CA3AF" strokeWidth="1" />
            <ellipse cx="-62" cy="12" rx="4" ry="10" fill="#FF3B30" />
            <ellipse cx="62" cy="12" rx="4" ry="10" fill="#FF3B30" />
            {/* helmet shell */}
            <ellipse cx="0" cy="10" rx="74" ry="66" fill="#F8FAFC" stroke="#CBD5E1" strokeWidth="1.2" />
            {/* fez */}
            <path d="M-46 -18 L -38 -58 L 38 -58 L 46 -18 Z" fill="#B91C1C" stroke="#7F1D1D" strokeWidth="1.1" />
            <ellipse cx="0" cy="-58" rx="38" ry="7" fill="#991B1B" />
            <path d="M36 -54 Q 52 -44 46 -18" stroke="#7F1D1D" strokeWidth="1" fill="none" />
            {/* tassel */}
            <g transform="translate(38 -46)">
              <path d="M0 0 L 18 10 L 12 26 L -2 18 Z" fill="#111827" />
              <line x1="0" y1="0" x2="10" y2="12" stroke="#111827" strokeWidth="2" />
              {/* fringe */}
              <g stroke="#111827" strokeWidth="1.1" strokeLinecap="round">
                <line x1="14" y1="12" x2="12" y2="22" />
                <line x1="16" y1="13" x2="15" y2="23" />
                <line x1="12" y1="14" x2="10" y2="24" />
                <line x1="9" y1="15" x2="7" y2="24" />
              </g>
            </g>
            {/* face plate */}
            <ellipse cx="0" cy="18" rx="58" ry="44" fill="#020617" stroke="#1E293B" strokeWidth="1.1" />
            {/* red brow glow */}
            <ellipse cx="-22" cy="-6" rx="18" ry="5" fill="#FF3B30" opacity="0.9" />
            <ellipse cx="22" cy="-6" rx="18" ry="5" fill="#FF3B30" opacity="0.9" />
            {/* eyes */}
            <g>
              <ellipse cx="-22" cy="12" rx={blink ? 16 : 18} ry={blink ? 1.2 : 16} fill="#FFFBEB" stroke="#FF3B30" strokeWidth="1.2" />
              <ellipse cx="22" cy="12" rx={blink ? 16 : 18} ry={blink ? 1.2 : 16} fill="#FFFBEB" stroke="#FF3B30" strokeWidth="1.2" />
              {!blink && (
                <>
                  <circle cx={-22 + eyeDx * 0.55} cy={12 + eyeDy * 0.45} r="10" fill="#7C2D12" />
                  <circle cx={22 + eyeDx * 0.55} cy={12 + eyeDy * 0.45} r="10" fill="#7C2D12" />
                  <circle cx={-22 + eyeDx * 0.55 + 3} cy={12 + eyeDy * 0.45 - 3} r="3.2" fill="white" opacity="0.95" />
                  <circle cx={22 + eyeDx * 0.55 + 3} cy={12 + eyeDy * 0.45 - 3} r="3.2" fill="white" opacity="0.95" />
                  <circle cx={-22 + eyeDx * 0.55} cy={12 + eyeDy * 0.45} r="4.5" fill="#0F172A" />
                  <circle cx={22 + eyeDx * 0.55} cy={12 + eyeDy * 0.45} r="4.5" fill="#0F172A" />
                  <circle cx={-22 + eyeDx * 0.55 + 1} cy={12 + eyeDy * 0.45 - 1} r="1.4" fill="white" />
                  <circle cx={22 + eyeDx * 0.55 + 1} cy={12 + eyeDy * 0.45 - 1} r="1.4" fill="white" />
                </>
              )}
            </g>
            {/* mustache */}
            <path d="M-26 28 C -16 18 -8 18 0 26 C 8 18 16 18 26 28 C 14 34 -14 34 -26 28 Z" fill="#DC2626" stroke="#991B1B" strokeWidth="0.9" />
            <path d="M-6 32 Q 0 38 6 32" stroke="#7F1D1D" strokeWidth="0.9" fill="none" />
            {/* beard */}
            <path d="M-28 30 C -24 52 -12 62 0 62 C 12 62 24 52 28 30 L 18 36 L 0 44 L -18 36 Z" fill="#B91C1C" />
            <path d="M-18 40 Q 0 56 18 40" stroke="#7F1D1D" strokeWidth="0.7" fill="none" opacity="0.7" />
            {/* smile */}
            <path d="M-8 48 Q 0 54 8 48" stroke="#FCA5A5" strokeWidth="1.4" fill="none" strokeLinecap="round" />
          </g>

          {/* intro text bubble */}
          {intro && (
            <g transform="translate(42 74)">
              <rect x="0" y="0" width="128" height="40" rx="12" fill="rgba(2,11,30,0.92)" stroke="rgba(0,229,255,0.55)" strokeWidth="1.1" />
              <text x="64" y="16" textAnchor="middle" fontSize="11" fontWeight="700" fill="white">السلام عليكم</text>
              <text x="64" y="29" textAnchor="middle" fontSize="9" fill="#7DD3FC">Hello — I am Genio</text>
            </g>
          )}
        </svg>

        {/* listening pulse dots */}
        {listening && (
          <div className="absolute -right-2 top-1/2 flex -translate-y-1/2 flex-col gap-1">
            <span className="h-1.5 w-1.5 animate-ping rounded-full bg-red-500" />
            <span className="h-1.5 w-1.5 animate-ping rounded-full bg-red-500 [animation-delay:120ms]" />
            <span className="h-1.5 w-1.5 animate-ping rounded-full bg-red-500 [animation-delay:240ms]" />
          </div>
        )}
      </div>

      {/* chromatic aberration on intro */}
      {intro && (
        <div className="pointer-events-none absolute inset-0 opacity-30 mix-blend-screen" style={{ transform: "translateX(1.2px)", filter: "hue-rotate(180deg)" }} />
      )}
    </div>
  );
}
