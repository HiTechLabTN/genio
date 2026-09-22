import { Pause, Play } from "lucide-react";
import { useEffect, useRef, useState } from "react";

interface Props {
  audioUrl?: string;
  base64Audio?: string;
  mime?: string;
  autoPlay?: boolean;
}

const activePlayers = new Set<() => void>();

/** Stop (pause) every currently-playing audio element. Called on agent Stop. */
export function stopAllAudio() {
  activePlayers.forEach((stop) => stop());
}

export default function AudioPlayer({ audioUrl, base64Audio, mime, autoPlay = true }: Props) {
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Resolve the playable source (base64 -> object URL or direct audioUrl).
  useEffect(() => {
    let objectUrl: string | null = null;
    if (base64Audio) {
      try {
        const byteCharacters = atob(base64Audio);
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
          byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        const blob = new Blob([byteArray], { type: mime || "audio/wav" });
        objectUrl = URL.createObjectURL(blob);
      } catch {
        /* invalid base64 — fall through */
      }
    }
    const audio = new Audio(objectUrl || audioUrl);
    audioRef.current = audio;

    const stop = () => { audio.pause(); setPlaying(false); };
    activePlayers.add(stop);

    audio.onended = () => setPlaying(false);
    audio.onerror = () => { setError(true); setPlaying(false); };
    audio.onplay = () => setPlaying(true);
    audio.onpause = () => setPlaying(false);

    if (autoPlay && (objectUrl || audioUrl)) {
      audio.play().catch(() => {
        // Autoplay blocked (no prior user gesture) — show the button so the user can play.
        setError(false);
      });
    }

    return () => {
      activePlayers.delete(stop);
      audio.pause();
      audio.src = "";
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      audioRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [audioUrl, base64Audio, mime]);

  function toggle() {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.paused) {
      audio.play().catch(() => setError(true));
    } else {
      audio.pause();
    }
  }

  return (
    <div className="mt-1.5 flex items-center gap-2 rounded-lg border border-neon/25 bg-slate-950/70 px-2.5 py-1.5 w-fit">
      <button
        onClick={toggle}
        disabled={!audioUrl && !base64Audio}
        className="flex h-7 w-7 items-center justify-center rounded-full bg-neon/15 text-neon transition-all hover:bg-neon/30 disabled:opacity-40"
        title={playing ? "Pause" : "Play"}
      >
        {playing ? <Pause size={13} /> : <Play size={13} />}
      </button>
      {/* pseudo waveform */}
      <div className="flex h-4 items-end gap-[2px]">
        {[3, 7, 5, 9, 4, 8, 6, 10, 5, 7, 3].map((h, i) => (
          <span
            key={i}
            className={`w-[2px] rounded-full ${playing ? "bg-neon animate-equalizer" : "bg-slate-700"}`}
            style={{ height: `${h * 2}px`, animationDelay: `${i * 0.08}s` }}
          />
        ))}
      </div>
      <span className="text-[10px] font-mono text-slate-500">{error ? "unavailable" : (playing ? "playing" : "audio")}</span>
    </div>
  );
}
