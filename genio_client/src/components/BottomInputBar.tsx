import { motion } from "framer-motion";
import { Mic, Paperclip, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { Attachment, ServerNode } from "../lib/types";
import { setIntermediateTranscript, startVoiceRecording, stopVoiceRecording, speechRecognitionSupported, transcribeAudio } from "../lib/audio";

interface Props {
  onSendPrompt: (text: string, attachments?: Attachment[]) => void;
  onSendVoice: (dataB64: string, durationSec: number) => void;
  disabled?: boolean;
  /** P2: when a node is connected, blob POSTed to /api/v1/voice/transcribe language ar */
  isConnected?: boolean;
  target?: ServerNode | null;
}

export default function BottomInputBar({ onSendPrompt, onSendVoice, disabled, isConnected, target }: Props) {
  const [value, setValue] = useState("");
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [recording, setRecording] = useState(false);
  const [recTimer, setRecTimer] = useState(0);
  const [micError, setMicError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length) readFiles(files);
  }

  // auto-expanding textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [value]);

  useEffect(() => {
    if (!recording) {
      setRecTimer(0);
      return;
    }
    const t = setInterval(() => setRecTimer((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [recording]);

  function handleSubmit() {
    const text = value.trim();
    if (!text && attachments.length === 0) return;
    if (text) onSendPrompt(text, attachments.length ? attachments : undefined);
    setValue("");
    setAttachments([]);
    textareaRef.current?.focus();
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  async function toggleMic() {
    setMicError(null);
    if (recording) {
      const audio = await stopVoiceRecording();
      setRecording(false);
      // P2: Darija — when node connected, POST blob to /api/v1/voice/transcribe language ar
      // interimResults already gave Arabic-script live preview; final authoritative transcript from server overwrites
      if (audio?.blob && isConnected) {
        try {
          const base = target && target.host !== "genio.hitech.tn" && !target.host.includes("genio.hitech.tn")
            ? `http://${target.host}:${target.port}`
            : "";
          const apiBase = base || undefined;
          const key = target?.key;
          const transcribed = await transcribeAudio(audio.blob, apiBase, key);
          if (transcribed && transcribed.trim()) {
            setValue(transcribed.trim());
            // also keep transcript for send path
            audio.transcript = transcribed.trim();
          } else if (audio?.transcript && !value.trim()) {
            setValue(audio.transcript.trim());
          }
        } catch {
          if (audio?.transcript && !value.trim()) setValue(audio.transcript.trim());
        }
      } else if (audio?.transcript && !value.trim()) {
        setValue(audio.transcript.trim());
      }
      if (audio && audio.dataB64) onSendVoice(audio.dataB64, audio.durationSec);
    } else {
      setIntermediateTranscript("");
      try {
        await startVoiceRecording((text: string) => {
          // Live STT: stream recognized words into the input in real-time (ar-TN interim Arabic-script).
          setValue(text);
        });
        setRecording(true);
      } catch (err: unknown) {
        setRecording(false);
        setMicError(err instanceof Error ? err.message : "Microphone unavailable");
      }
    }
  }

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files) return;
    readFiles(Array.from(files));
    e.target.value = "";
  }

  function readFiles(files: File[]) {
    Promise.all(files.map(readFile)).then((newAtts) =>
      setAttachments((prev) => [...prev, ...newAtts]),
    );
  }

  function readFile(f: File): Promise<Attachment> {
    return new Promise((resolve) => {
      const id = crypto.randomUUID();
      const reader = new FileReader();
      if (isTextual(f)) {
        reader.onload = () => {
          resolve({ id, name: f.name, type: f.type, dataB64: "", size: f.size, content: String(reader.result) });
        };
        reader.readAsText(f);
      } else {
        reader.onload = () => {
          const dataB64 = String(reader.result).split(",")[1] || "";
          resolve({ id, name: f.name, type: f.type, dataB64, size: f.size });
        };
        reader.readAsDataURL(f);
      }
    });
  }

  function isTextual(f: File): boolean {
    if (!f.type) {
      const ext = f.name.split(".").pop()?.toLowerCase();
      return ["txt", "md", "html", "htm", "css", "js", "ts", "json", "py", "c", "cpp", "h", "java", "rs", "go", "rb", "sh", "yaml", "yml", "log", "csv", "xml", "sql", "ini", "toml"].includes(ext ?? "");
    }
    return f.type.startsWith("text/") || /json|xml|javascript|yaml/.test(f.type);
  }

  function removeAttachment(id: string) {
    setAttachments((prev) => prev.filter((a) => a.id !== id));
  }

  return (
    <div
      className={`w-full flex-none border-t border-slate-700/40 bg-slate-950/80 px-2 sm:px-4 py-3 backdrop-blur-lg transition-colors ${
        dragOver ? "ring-2 ring-inset ring-neon bg-slate-900/90" : ""
      }`}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
    >
      {/* attachments preview */}
      {dragOver && (
        <p className="mb-2 text-center text-[11px] font-mono text-neon">drop files to attach</p>
      )}
      {attachments.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1.5">
          {attachments.map((att) => (
            <span
              key={att.id}
              className="flex items-center gap-1 rounded-full border border-neon/20 bg-neon/5 px-2 py-0.5 text-[10px] font-mono text-neon-soft"
            >
              <Paperclip size={10} />
              {att.name}
              <button onClick={() => removeAttachment(att.id)} className="ml-0.5 text-slate-500 hover:text-rose-300">
                <X size={10} />
              </button>
            </span>
          ))}
        </div>
      )}

      <div className="flex w-full items-end gap-1 sm:gap-2">
        {/* attachment picker */}
        <label
          className="flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center rounded-xl border border-slate-700/50 bg-slate-900/60 text-slate-400 transition-all hover:border-neon/40 hover:bg-neon/5 hover:text-neon"
          title="Attach files"
        >
          <Paperclip size={16} />
          <input
            type="file"
            multiple
            className="hidden"
            onChange={handleFile}
            accept=".txt,.md,.py,.js,.ts,.json,.yaml,.yml,.log,.csv,.xml,.html,.css,.c,.cpp,.java,.rs,.go,.rb,.sh,.sql,.png,.jpg,.jpeg,.gif,.webp"
          />
        </label>

        {/* textarea */}
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder="Message Genio… (Enter to send, Shift+Enter for newline)"
          className="min-h-[40px] max-h-[160px] min-w-0 flex-1 resize-none rounded-xl border border-slate-700/60 bg-slate-950/60 px-3 sm:px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 outline-none transition-all focus:border-neon/60 focus:bg-slate-900/80 focus:shadow-neon font-mono"
          disabled={disabled || recording}
        />

        {/* voice - ÉCOUTE pill */}
        <button
          onClick={toggleMic}
          title={recording ? "Stop recording" : "Écoute"}
          className={`flex h-10 shrink-0 items-center justify-center gap-1.5 rounded-full border px-2.5 sm:px-4 text-[11px] sm:text-[12px] font-bold tracking-wider backdrop-blur transition-all duration-200 ${
            recording
              ? "border-red-500 bg-red-500/15 text-red-300 shadow-[0_0_16px_rgba(239,68,68,0.5)] animate-pulse"
              : "border-red-500/40 bg-red-500/5 text-red-300 hover:border-red-500/70 hover:bg-red-500/10 hover:shadow-[0_0_12px_rgba(239,68,68,0.25)]"
          }`}
        >
          <span className="flex items-center gap-1">
            <span className={`flex gap-0.5 ${recording ? "opacity-100" : "opacity-60"}`}>
              <span className="h-3 w-0.5 bg-red-400" style={{ animation: recording ? "equalizer 0.6s ease-in-out infinite" : undefined }} />
              <span className="h-4 w-0.5 bg-red-400" style={{ animation: recording ? "equalizer 0.6s 0.1s ease-in-out infinite" : undefined }} />
              <span className="h-3 w-0.5 bg-red-400" style={{ animation: recording ? "equalizer 0.6s 0.2s ease-in-out infinite" : undefined }} />
            </span>
            <Mic size={14} className={recording ? "text-red-300" : "text-red-400/70"} />
          </span>
          <span className="hidden sm:inline">ÉCOUTE</span>
        </button>

        {/* send - PRÊT pill */}
        <button
          onClick={handleSubmit}
          disabled={disabled || recording || (!value.trim() && attachments.length === 0)}
          className={`flex h-10 shrink-0 items-center justify-center gap-1.5 rounded-full border px-3 sm:px-5 text-[11px] sm:text-[12px] font-bold tracking-wider backdrop-blur transition-all ${
            !value.trim() && attachments.length === 0
              ? "border-slate-700/30 bg-slate-900/30 text-slate-600"
              : "border-cyan-400 bg-cyan-400/10 text-cyan-300 shadow-[0_0_16px_rgba(0,229,255,0.35)] hover:bg-cyan-400/15 hover:shadow-[0_0_20px_rgba(0,229,255,0.5)] active:scale-95"
          } disabled:opacity-40`}
        >
          <span className="text-cyan-300">✦✦</span>
          <span className="hidden sm:inline">PRÊT</span>
        </button>
      </div>

      {micError && (
        <p className="mt-2 text-center text-[11px] font-mono text-rose-400">
          ⚠ {micError}
        </p>
      )}

      {recording && (
        <motion.p
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-2 text-center text-[11px] font-mono text-danger"
        >
          ● recording {recTimer}s —{" "}
          {speechRecognitionSupported()
            ? "live transcription: speak…"
            : "release to send via Web Audio"}
        </motion.p>
      )}

      {/* GENIO APP footer — Midjourney fidelity */}
      <div className="mt-3 flex items-center justify-center gap-3 font-mono text-[10px] tracking-[0.2em] text-slate-500">
        <span className="h-1 w-1 rounded-full bg-slate-600" />
        GENIO APP
        <span className="h-1 w-1 rounded-full bg-slate-600" />
      </div>
    </div>
  );
}
