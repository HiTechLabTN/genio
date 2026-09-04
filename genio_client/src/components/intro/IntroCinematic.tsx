import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import genioHero from "../../assets/mascot/genio-hero.webp";
import genioWave from "../../assets/mascot/genio-wave.webp";
import genioListen from "../../assets/mascot/genio-listen.webp";
import genioThink from "../../assets/mascot/genio-think.webp";
import genioSpeak from "../../assets/mascot/genio-speak.webp";
import introAudio from "../../assets/audio/intro_voiceover.m4a";

const SCENES = [
  { from: 0, to: 10, src: genioWave, label: "موجة" },
  { from: 10, to: 25, src: genioListen, label: "إصغاء" },
  { from: 25, to: 45, src: genioThink, label: "تفكير" },
  { from: 45, to: 70, src: genioSpeak, label: "حديث" },
  { from: 70, to: 80, src: genioHero, label: "جاهز" },
] as const;

function sceneForTime(t: number): string {
  for (const s of SCENES) if (t >= s.from && t < s.to) return s.src;
  if (t >= 80) return genioHero;
  return genioWave;
}

interface Props {
  onComplete: () => void;
  onSkip: () => void;
}

export default function IntroCinematic({ onComplete, onSkip }: Props) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [current, setCurrent] = useState(0);
  const [duration, setDuration] = useState(80);
  const [playing, setPlaying] = useState(false);
  const [needsTap, setNeedsTap] = useState(false);

  useEffect(() => {
    const a = audioRef.current;
    if (!a) return;
    const onTime = () => setCurrent(a.currentTime);
    const onLoaded = () => setDuration(a.duration || 80);
    const onEnded = () => onComplete();
    a.addEventListener("timeupdate", onTime);
    a.addEventListener("loadedmetadata", onLoaded);
    a.addEventListener("ended", onEnded);
    // try autoplay
    a.play()
      .then(() => {
        setPlaying(true);
        setNeedsTap(false);
      })
      .catch(() => {
        setNeedsTap(true);
        setPlaying(false);
      });
    return () => {
      a.removeEventListener("timeupdate", onTime);
      a.removeEventListener("loadedmetadata", onLoaded);
      a.removeEventListener("ended", onEnded);
    };
  }, [onComplete]);

  const handleFirstTap = () => {
    const a = audioRef.current;
    if (!a) return;
    if (needsTap) {
      a.play()
        .then(() => {
          setPlaying(true);
          setNeedsTap(false);
        })
        .catch(() => {});
    }
  };

  const activeSrc = sceneForTime(current);
  const progress = duration ? (current / duration) * 100 : 0;
  const isHero = activeSrc === genioHero && current >= 70;

  return (
    <div
      onPointerDown={handleFirstTap}
      className="fixed inset-0 z-[60] flex flex-col items-center justify-center bg-[#020B1E] overflow-hidden"
      dir="rtl"
    >
      <audio ref={audioRef} src={introAudio} preload="auto" playsInline />

      {/* skip top-right */}
      <button
        onClick={onSkip}
        className="absolute right-4 top-4 z-20 rounded-full border border-white/20 bg-white/5 px-4 py-1.5 font-mono text-[12px] text-white/80 backdrop-blur hover:bg-white/10 md:right-6 md:top-6"
      >
        تخطي
      </button>

      {/* stage — puppet images with mask+screen, crossfade 250ms */}
      <div className="relative flex h-[52vh] w-full max-w-[520px] items-center justify-center px-6 md:h-[58vh]">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeSrc}
            initial={{ opacity: 0, scale: 0.97 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.97 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
            className="relative flex h-full w-full items-center justify-center"
          >
            <img
              src={activeSrc}
              alt="Genio intro"
              className="h-full w-full object-contain object-bottom"
              style={{
                WebkitMaskImage: "radial-gradient(ellipse at 50% 55%, black 62%, transparent 82%)",
                maskImage: "radial-gradient(ellipse at 50% 55%, black 62%, transparent 82%)",
                mixBlendMode: "screen",
                filter: "contrast(1.05) saturate(1.05)",
              }}
              draggable={false}
            />
            {/* hero CTA overlay at 70-80s */}
            {isHero && (
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                className="absolute bottom-2 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2"
              >
                <p style={{ fontFamily: "Reem Kufi, sans-serif" }} className="text-[15px] font-bold text-cyan-300">
                  جاهز تنطلق؟
                </p>
                <button
                  onClick={onComplete}
                  className="rounded-full bg-cyan-400 px-6 py-2 text-[14px] font-black text-slate-900 shadow-[0_0_18px_rgba(34,211,238,0.5)]"
                >
                  ابدأ الآن
                </button>
              </motion.div>
            )}
          </motion.div>
        </AnimatePresence>

        {/* scanline shimmer */}
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            background: "repeating-linear-gradient(0deg, transparent 0 2px, rgba(34,211,238,0.04) 2px 3px)",
            WebkitMaskImage: "radial-gradient(ellipse at 50% 50%, black 60%, transparent 85%)",
            maskImage: "radial-gradient(ellipse at 50% 50%, black 60%, transparent 85%)",
            mixBlendMode: "screen",
          }}
        />
      </div>

      {/* playing hint if autoplay blocked */}
      {needsTap && !playing && (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="mt-2 font-mono text-[12px] text-cyan-300"
        >
          اضغط في أي مكان لتشغيل الصوت ←
        </motion.p>
      )}

      {/* progress bar */}
      <div className="absolute bottom-0 left-0 right-0 h-[3px] bg-white/10">
        <motion.div className="h-full bg-cyan-400" style={{ width: `${progress}%` }} transition={{ duration: 0.1 }} />
      </div>

      {/* scene dots */}
      <div className="pointer-events-none absolute bottom-4 left-1/2 flex -translate-x-1/2 gap-1.5">
        {SCENES.map((s) => (
          <span
            key={s.label}
            className={`h-1.5 w-6 rounded-full transition-colors ${current >= s.from && current < s.to ? "bg-cyan-400" : "bg-white/20"}`}
          />
        ))}
      </div>
    </div>
  );
}
