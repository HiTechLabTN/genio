import { memo, useEffect, useRef, useState } from "react";
import { motion, useMotionValue, useSpring, useTransform, AnimatePresence } from "framer-motion";
import heroImg from "../../assets/mascot/genio-hero.webp";
import waveImg from "../../assets/mascot/genio-wave.webp";
import listenImg from "../../assets/mascot/genio-listen.webp";
import thinkImg from "../../assets/mascot/genio-think.webp";
import speakImg from "../../assets/mascot/genio-speak.webp";

type AvatarState = "hero" | "wave" | "listen" | "think" | "speak";
type Props = { status?: string; audioLevel?: number };

const SRC: Record<AvatarState, string> = {
  hero: heroImg,
  wave: waveImg,
  listen: listenImg,
  think: thinkImg,
  speak: speakImg,
};

function derive(status: string | undefined, lvl: number): AvatarState {
  if (status === "greeting" || status === "waving") return "wave";
  if (status === "listening") return "listen";
  if (status === "thinking" || status === "executing") return "think";
  if (status === "answering" || status === "completed" || lvl > 0.05) return "speak";
  return "hero";
}

/**
 * AliveGenio3D — نفس الكاراكتير بالذات حي 100%
 * 5 تصاور أصلية (Hero/Wave/Listen/Think/Speak) + cross-fade 200ms 60fps
 * + رمش + شفايف مع الصوت + تنفس + parallax — فقط على طبقة الماسكوت
 * الخلفية full-screen ثابتة 100%، بلا مستطيلات، بلا TripoSR مشوّه
 */
const StateLoopAvatar = memo(function StateLoopAvatar({ status = "idle", audioLevel = 0 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const lvl = audioLevel ?? 0;
  const isSpeaking = lvl > 0.05;
  const target = derive(status, lvl);

  // wave يلعب مرة ويرجع — greeting/completed
  const [effective, setEffective] = useState<AvatarState>(target);
  const waveTimer = useRef<number | null>(null);
  useEffect(() => {
    if (target === "wave" && effective !== "wave") {
      setEffective("wave");
      if (waveTimer.current) window.clearTimeout(waveTimer.current);
      waveTimer.current = window.setTimeout(() => setEffective("hero"), 2800) as unknown as number;
      return;
    }
    if (target === "wave" && effective === "wave") return;
    if (effective === "wave" && target !== "wave") {
      if (target === "speak") {
        if (waveTimer.current) window.clearTimeout(waveTimer.current);
        setEffective(target);
      }
      return;
    }
    if (effective !== target) setEffective(target);
  }, [target, effective]);

  const [ready, setReady] = useState(false);
  const [isBlinking, setIsBlinking] = useState(false);
  const [mouthOpen, setMouthOpen] = useState(0);

  // preload الخمسة باش ما فماش فلاش
  useEffect(() => {
    let n = 0;
    const total = Object.keys(SRC).length;
    Object.values(SRC).forEach((s) => {
      const im = new Image();
      im.src = s;
      im.onload = im.onerror = () => { n++; if (n >= total) setReady(true); };
    });
    const t = window.setTimeout(() => setReady(true), 600);
    return () => window.clearTimeout(t);
  }, []);

  // رمش عضوي كل 2.8-5 ث
  useEffect(() => {
    let t: number | undefined;
    let alive = true;
    const schedule = () => {
      t = window.setTimeout(() => {
        if (!alive) return;
        setIsBlinking(true);
        window.setTimeout(() => alive && setIsBlinking(false), 140);
        schedule();
      }, 2800 + Math.random() * 2200) as unknown as number;
    };
    schedule();
    return () => { alive = false; if (t) window.clearTimeout(t); };
  }, []);

  // فم مع الصوت
  useEffect(() => {
    if (!isSpeaking) { setMouthOpen(0); return; }
    const id = window.setInterval(() => {
      setMouthOpen(0.35 + lvl * 1.1 + Math.random() * 0.15);
    }, 70);
    return () => window.clearInterval(id);
  }, [isSpeaking, lvl]);

  // parallax فقط للماسكوت
  const mx = useMotionValue(0);
  const my = useMotionValue(0);
  const springX = useSpring(mx, { stiffness: 42, damping: 18 });
  const springY = useSpring(my, { stiffness: 42, damping: 18 });
  const rotateY = useTransform(springX, [-1, 1], [-9, 9]);
  const rotateX = useTransform(springY, [-1, 1], [5, -5]);
  const translateX = useTransform(springX, [-1, 1], [-14, 14]);
  const translateY = useTransform(springY, [-1, 1], [-10, 10]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const onMouse = (e: MouseEvent) => {
      const r = el.getBoundingClientRect();
      mx.set(Math.max(-1, Math.min(1, (e.clientX - (r.left + r.width / 2)) / (r.width * 0.45))));
      my.set(Math.max(-1, Math.min(1, (e.clientY - (r.top + r.height / 2)) / (r.height * 0.45))));
    };
    const onGyro = (e: DeviceOrientationEvent) => {
      const g = e.gamma ?? 0, b = e.beta ?? 45;
      if (Math.abs(g) < 0.1 && Math.abs(b - 45) < 0.1) return;
      mx.set(Math.max(-1, Math.min(1, g / 25)));
      my.set(Math.max(-1, Math.min(1, (b - 45) / 30)));
    };
    window.addEventListener("mousemove", onMouse, { passive: true });
    window.addEventListener("deviceorientation", onGyro, { passive: true });
    return () => {
      window.removeEventListener("mousemove", onMouse);
      window.removeEventListener("deviceorientation", onGyro);
    };
  }, [mx, my]);

  const isWaving = effective === "wave";
  const isListening = effective === "listen";

  return (
    <div
      ref={containerRef}
      role="img"
      aria-label="جينيو — المساعد التونسي الحي"
      className="relative flex h-full w-full items-center justify-center overflow-hidden bg-[#020B1E] select-none"
      style={{ perspective: "1100px" }}
    >
      {/* LAYER 0 — خلفية ثابتة full-screen */}
      <div className="fixed inset-0 w-full h-full bg-[#020B1E]" />
      <div
        className="pointer-events-none fixed inset-0 w-full h-full opacity-[0.55]"
        style={{ background: "radial-gradient(ellipse at 50% 72%, rgba(34,211,238,0.16) 0%, transparent 62%), radial-gradient(ellipse at 35% 22%, rgba(255,215,0,0.10) 0%, transparent 55%), radial-gradient(ellipse at 50% 50%, rgba(99,102,241,0.06) 0%, transparent 72%)" }}
      />
      <div className="pointer-events-none fixed inset-0 z-[1] w-full h-full">
        <div className="absolute inset-0 opacity-[0.34]">
          <svg className="h-full w-full" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid slice" aria-hidden>
            <defs>
              <pattern id="alive-arabesque" width="140" height="140" patternUnits="userSpaceOnUse">
                <g stroke="#00E5FF" strokeWidth="1.15" fill="none" opacity={1}>
                  <path d="M70 16 L76 32 L92 32 L80 43 L84 60 L70 50 L56 60 L60 43 L48 32 L64 32 Z" />
                  <path d="M70 16 L70 60 M48 32 L92 32 M53 20 L87 48 M87 20 L53 48" opacity={0.45} />
                </g>
                <g stroke="#FFD700" strokeWidth="0.9" fill="none" opacity={0.9}>
                  <path d="M70 36 L73 43 L80 43 L74 48 L76 55 L70 51 L64 55 L66 48 L60 43 L67 43 Z" />
                </g>
              </pattern>
              <radialGradient id="alive-glow" cx="50%" cy="50%" r="70%">
                <stop offset="0%" stopColor="rgba(0,229,255,0.10)" />
                <stop offset="55%" stopColor="rgba(255,215,0,0.04)" />
                <stop offset="100%" stopColor="transparent" />
              </radialGradient>
            </defs>
            <rect width="100%" height="100%" fill="url(#alive-arabesque)" />
            <rect width="100%" height="100%" fill="url(#alive-glow)" />
          </svg>
        </div>
        <motion.div
          className="absolute inset-0"
          animate={{ opacity: [0.42, 0.78, 0.42] }}
          transition={{ duration: 3.2, repeat: Infinity, ease: "easeInOut" }}
          style={{ background: "radial-gradient(ellipse at 50% 68%, rgba(34,211,238,0.10) 0%, transparent 58%), radial-gradient(ellipse at 50% 18%, rgba(255,215,0,0.06) 0%, transparent 52%)" }}
        />
      </div>
      <div className="pointer-events-none fixed inset-0" style={{ background: "radial-gradient(ellipse at center, transparent 56%, rgba(0,0,0,0.58) 100%)" }} />

      {/* FRAME موحد — هولوغرام + ماسكوت بنفس المحور */}
      <motion.div
        className="relative flex flex-col items-center justify-end h-[85vh] max-h-[850px] w-auto mx-auto select-none bg-transparent border-0 shadow-none z-10"
        style={{ rotateX, rotateY, x: translateX, y: translateY, transformStyle: "preserve-3d" } as never}
      >
        <motion.div
          className="relative flex flex-col items-center justify-end bg-transparent border-0 shadow-none"
          animate={isWaving ? { y: [0, -8, 0], rotateZ: [0, -1.2, 1.2, -1.2, 0], scale: [1, 1.02, 1] } : { y: [0, -8, 0], scale: [1, 1.015, 1] }}
          transition={isWaving ? { duration: 1.2, repeat: Infinity, ease: "easeInOut" } : { duration: 3.2, repeat: Infinity, ease: "easeInOut" }}
          style={{ transformOrigin: "50% 88%" }}
        >
          {/* glow خلف الماسكوت */}
          <motion.div
            className="pointer-events-none absolute bottom-[6%] left-1/2 h-[42%] w-[78%] -translate-x-1/2 rounded-full blur-[32px] bg-transparent border-0"
            animate={{ opacity: isSpeaking ? [0.32, 0.58, 0.32] : [0.25, 0.38, 0.25], scale: isSpeaking ? 1 + lvl * 0.18 : 1 }}
            transition={{ duration: isSpeaking ? 0.4 : 3.6, repeat: Infinity, ease: "easeInOut" }}
            style={{ background: "radial-gradient(ellipse at center, rgba(34,211,238,0.18) 0%, rgba(255,215,0,0.06) 38%, transparent 72%)" }}
          />

          {/* هولوغرام لاصق تحت الصباط */}
          <div className="absolute bottom-2 left-1/2 -translate-x-1/2 pointer-events-none z-0" style={{ perspective: "800px" } as React.CSSProperties}>
            <div className="relative flex items-center justify-center" style={{ transform: "rotateX(72deg)", transformStyle: "preserve-3d" } as React.CSSProperties}>
              <motion.div
                className="w-72 h-72 rounded-full border border-cyan-400/60 bg-transparent"
                style={{ boxShadow: "0 0 25px rgba(34,211,238,0.7), inset 0 0 12px rgba(34,211,238,0.18)" }}
                animate={{ rotateZ: 360 }} transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
              />
              <motion.div
                className="absolute w-52 h-52 rounded-full border-2 border-white/80 bg-transparent"
                style={{ boxShadow: "0 0 30px rgba(255,255,255,0.8), 0 0 30px rgba(34,211,238,0.55)" }}
                animate={{ rotateZ: -360 }} transition={{ duration: 5, repeat: Infinity, ease: "linear" }}
              />
              <div className="absolute w-32 h-32 rounded-full bg-cyan-400/20 blur-md" style={{ boxShadow: "0 0 40px rgba(34,211,238,0.9)" }}>
                <div className="absolute inset-0 rounded-full blur-[1px]" style={{ background: "radial-gradient(circle at center, rgba(255,255,255,0.9) 0%, transparent 62%)" }} />
                <div className="absolute left-1/2 top-1/2 h-[42px] w-[42px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-white/90" style={{ boxShadow: "0 0 14px rgba(255,255,255,1), 0 0 22px rgba(34,211,238,0.7)" }} />
              </div>
            </div>
            <div className="absolute left-1/2 top-[68%] h-[14px] w-[160%] -translate-x-1/2 rounded-full blur-[12px] opacity-50" style={{ background: "radial-gradient(ellipse at center, rgba(0,229,255,0.22) 0%, transparent 72%)" }} />
          </div>

          {/* الماسكوت — 5 طبقات cross-fade */}
          <div className="relative z-10 bg-transparent border-0 shadow-none" style={{ width: "min(72vh, 520px)", height: "min(72vh, 700px)" }}>
            {(Object.keys(SRC) as AvatarState[]).map((k) => (
              <img
                key={k}
                src={SRC[k]}
                alt={k === effective ? "Genio" : ""}
                aria-hidden={k !== effective}
                draggable={false}
                className="absolute inset-0 h-full w-full object-contain object-bottom pointer-events-none select-none bg-transparent border-0 shadow-none"
                style={{
                  opacity: ready && k === effective ? 1 : 0,
                  transition: "opacity 200ms ease",
                  WebkitMaskImage: "linear-gradient(to bottom, black 75%, transparent 100%)",
                  maskImage: "linear-gradient(to bottom, black 75%, transparent 100%)",
                  filter: isSpeaking && k === effective ? `brightness(${1.04 + lvl * 0.1}) saturate(1.06)` : "brightness(1.02) saturate(1.05)",
                } as React.CSSProperties}
              />
            ))}

            {/* رمش — فوق نفس الوجه */}
            <div className="pointer-events-none absolute z-20 select-none" style={{ top: "31.5%", left: "41.5%", width: "17%", height: "5.5%", display: "flex", justifyContent: "space-between", alignItems: "center" } as React.CSSProperties}>
              {[0, 1].map((i) => (
                <div key={i} className="relative h-full w-[42%] overflow-hidden rounded-full">
                  <motion.div
                    className="absolute inset-0 rounded-full"
                    style={{ background: "linear-gradient(to bottom, #D8C4A8 0%, #C9B090 100%)", transformOrigin: "top" }}
                    animate={{ scaleY: isBlinking ? 1 : 0, opacity: isBlinking ? 1 : 0 }}
                    transition={{ duration: 0.07 }}
                  />
                  <motion.div className="absolute left-[32%] top-[28%] h-[22%] w-[18%] rounded-full bg-white/85 blur-[0.5px]" animate={{ opacity: isBlinking ? 0 : 0.9 }} transition={{ duration: 0.05 }} />
                </div>
              ))}
            </div>

            {/* فم — يتحرك مع الصوت */}
            <div className="pointer-events-none absolute z-20 overflow-hidden" style={{ top: "41.8%", left: "47.2%", width: "6.2%", height: "3.2%", transform: "translateX(-50%)", borderRadius: "50% / 60%" } as React.CSSProperties}>
              <motion.div
                className="absolute inset-0 rounded-full"
                style={{ background: "radial-gradient(ellipse at 50% 30%, #2A0A0A 0%, #1A0505 55%, #000 100%)", boxShadow: "inset 0 1px 2px rgba(255,255,255,0.25)" }}
                animate={{ scaleY: isSpeaking ? Math.max(0.35, Math.min(1.2, mouthOpen)) : 0.22, scaleX: isSpeaking ? 1 + mouthOpen * 0.08 : 1, opacity: isSpeaking ? 1 : 0.75 }}
                transition={{ duration: 0.07 }}
              />
              <motion.div
                className="absolute left-1/2 top-[58%] h-[38%] w-[52%] -translate-x-1/2 rounded-full blur-[0.3px]"
                style={{ background: "radial-gradient(ellipse at center, #C94A4A 0%, #8B2222 70%, transparent 100%)" }}
                animate={{ opacity: isSpeaking ? 0.65 + mouthOpen * 0.25 : 0.35, scaleY: isSpeaking ? mouthOpen : 0.5 }}
                transition={{ duration: 0.07 }}
              />
            </div>

            {/* يد على الوذن كي يسمع */}
            <AnimatePresence>
              {isListening && (
                <motion.div
                  initial={{ x: 24, y: 12, opacity: 0, rotate: -18 }}
                  animate={{ x: 0, y: 0, opacity: 1, rotate: 0 }}
                  exit={{ x: 18, y: 8, opacity: 0, transition: { duration: 0.22 } }}
                  transition={{ type: "spring", stiffness: 220, damping: 18 }}
                  className="pointer-events-none absolute z-20 select-none"
                  style={{ top: "33%", right: "18%", width: "18%", height: "18%" } as React.CSSProperties}
                >
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="relative">
                      <div className="h-14 w-10 rounded-[14px] bg-gradient-to-b from-[#E8D5C0] to-[#D4B89A]" style={{ transform: "rotate(-14deg)", boxShadow: "0 0 18px rgba(34,211,238,0.25)" }} />
                      <div className="absolute -bottom-1 left-1/2 h-3 w-11 -translate-x-1/2 rounded-full bg-white/90" style={{ boxShadow: "0 0 12px rgba(34,211,238,0.3)" }} />
                    </div>
                  </div>
                  <motion.div className="absolute -inset-2 rounded-full border border-cyan-300/30" animate={{ scale: [0.9, 1.15, 0.9], opacity: [0.25, 0.55, 0.25] }} transition={{ duration: 1.4, repeat: Infinity }} />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>
      </motion.div>

      {isSpeaking && (
        <motion.div
          className="pointer-events-none absolute bottom-[10%] left-1/2 z-[2] h-16 w-16 -translate-x-1/2 rounded-full border border-white/25 bg-transparent"
          animate={{ scale: [0.7, 1.35, 0.7], opacity: [0.35, 0, 0.35] }}
          transition={{ duration: 1.0, repeat: Infinity, ease: "easeOut" }}
        />
      )}
    </div>
  );
});

export default StateLoopAvatar;
