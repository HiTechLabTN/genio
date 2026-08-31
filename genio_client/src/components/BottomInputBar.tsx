import { motion } from "framer-motion";
import { Mic, Paperclip, Send, Square, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { Attachment } from "../lib/types";
import { startVoiceRecording, stopVoiceRecording } from "../lib/audio";

interface Props {
  onSendPrompt: (text: string, attachments?: Attachment[]) => void;
  onSendVoice: (dataB64: string, durationSec: number) => void;
  disabled?: boolean;
}

export default function BottomInputBar({ onSendPrompt, onSendVoice, disabled }: Props) {
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
      if (audio && audio.dataB64) onSendVoice(audio.dataB64, audio.durationSec);
    } else {
      try {
        await startVoiceRecording();
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
      className={`flex-none border-t border-slate-700/40 bg-slate-950/80 px-4 py-3 backdrop-blur-lg transition-colors ${
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

      <div className="flex items-end gap-2">
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
          className="min-h-[40px] max-h-[160px] flex-1 resize-none rounded-xl border border-slate-700/60 bg-slate-950/60 px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 outline-none transition-all focus:border-neon/60 focus:bg-slate-900/80 focus:shadow-neon font-mono"
          disabled={disabled || recording}
        />

        {/* voice */}
        <button
          onClick={toggleMic}
          title={recording ? "Stop recording" : "Voice prompt"}
          className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl transition-all duration-200 ${
            recording
              ? "bg-danger text-white shadow-neon-lg"
              : "border border-slate-700/50 bg-slate-900/60 text-slate-400 hover:border-neon/40 hover:bg-neon/5 hover:text-neon"
          }`}
        >
          {recording ? (
            <span className="relative flex items-center justify-center">
              <span className="absolute inset-0 animate-ping rounded-full bg-danger/40" />
              <Square size={14} />
            </span>
          ) : (
            <Mic size={16} />
          )}
        </button>

        {/* send */}
        <button
          onClick={handleSubmit}
          disabled={disabled || recording || (!value.trim() && attachments.length === 0)}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-neon text-slate-950 font-bold transition-all hover:bg-neon-soft hover:shadow-neon-lg active:scale-95 disabled:opacity-30 disabled:hover:shadow-none"
        >
          <Send size={16} />
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
          ● recording {recTimer}s — release to send via Web Audio
        </motion.p>
      )}
    </div>
  );
}
