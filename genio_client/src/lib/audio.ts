export interface VoicedAudio {
  dataB64: string;
  durationSec: number;
  mime: string;
  transcript?: string;
}

// Type augmentation for engines that expose webkitSpeechRecognition.
interface SpeechRecognitionAlternative {
  transcript: string;
  confidence: number;
}
interface SpeechRecognitionResultItem {
  isFinal: boolean;
  length: number;
  item(i: number): SpeechRecognitionAlternative;
  [i: number]: SpeechRecognitionAlternative;
}
interface SpeechRecognitionResultList {
  length: number;
  item(i: number): SpeechRecognitionResultItem;
  [i: number]: SpeechRecognitionResultItem;
}
interface SpeechRecognitionEvent {
  results: SpeechRecognitionResultList;
  resultIndex: number;
}
interface SpeechRecognitionErrorEvent {
  error: string;
}

let recorder: MediaRecorder | null = null;
let latestStream: MediaStream | null = null;
let audioCtx: AudioContext | null = null;
let recChunks: Blob[] = [];
let recordingStartedAt = 0;
let recognition: unknown = null;
let silenceTimer: ReturnType<typeof setTimeout> | null = null;
let onTranscriptCb: ((text: string, final: boolean) => void) | null = null;

function pickMime(): string {
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
  if (typeof MediaRecorder !== "undefined") {
    for (const c of candidates) if (MediaRecorder.isTypeSupported(c)) return c;
  }
  return "";
}

function writeString(view: DataView, offset: number, str: string): void {
  for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
}

function encodeWav(audio: AudioBuffer): Blob {
  const sampleRate = audio.sampleRate;
  const channel = audio.getChannelData(0);
  const numFrames = channel.length;
  const buffer = new ArrayBuffer(44 + numFrames * 2);
  const view = new DataView(buffer);

  writeString(view, 0, "RIFF");
  view.setUint32(4, 36 + numFrames * 2, true);
  writeString(view, 8, "WAVE");
  writeString(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(view, 36, "data");
  view.setUint32(40, numFrames * 2, true);

  for (let i = 0, offset = 44; i < numFrames; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, channel[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1]);
    reader.onerror = () => reject(new Error("failed to read audio blob"));
    reader.readAsDataURL(blob);
  });
}

export async function requestMicrophonePermission(): Promise<void> {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    stream.getTracks().forEach((t) => t.stop());
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    if (msg.includes("NotAllowedError") || msg.includes("Permission") || msg.includes("permission")) {
      throw new Error("Microphone permission denied — grant mic access in your browser/OS settings (Tauri + Android: Settings → App → Microphone), then try again.");
    }
    if (msg.includes("NotFoundError") || msg.includes("DevicesNotFound") || msg.includes("devices")) {
      throw new Error("No microphone detected — connect a mic and try again.");
    }
    if (msg.includes("ConstraintNotSatisfied") || msg.includes("Invalid constraint") || msg.includes("Overconstrained")) {
      throw new Error("Microphone constraint not supported on this device — retry with default settings.");
    }
    throw new Error(`Microphone error: ${msg}`);
  }
}

/** Start SpeechRecognition for live transcription — DEPRECATED (Phase 3 v2.1).
 *
 * Browser WebSpeech is non-functional on Android/Tauri WebView; we keep this
 * only as a best-effort live *preview* on desktop. The authoritative transcript
 * comes from the server-side `/api/v1/voice/transcribe` pipeline via
 * transcribeAudio() on the recorded blob.
 */
function startSpeechRecognition(onTranscript: (text: string, final: boolean) => void): boolean {
  const w = window as unknown as Record<string, unknown>;
  const SR = (w.SpeechRecognition || w.webkitSpeechRecognition) as
    | (new () => unknown)
    | undefined;
  if (!SR) return false;

  const sr = new SR() as {
    lang: string;
    continuous: boolean;
    interimResults: boolean;
    onresult: ((e: SpeechRecognitionEvent) => void) | null;
    onerror: ((e: SpeechRecognitionErrorEvent) => void) | null;
    onend: (() => void) | null;
    start: () => void;
    stop: () => void;
  };
  sr.lang = "en-US";
  sr.continuous = true;
  sr.interimResults = true;
  sr.onresult = (e) => {
    let interim = "";
    let finalText = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const result = e.results.item(i);
      const text = result.item(0).transcript;
      if (result.isFinal) finalText += text;
      else interim += text;
    }
    if (finalText) {
      intermediateTranscript += finalText;
      onTranscript(intermediateTranscript + (interim ? " " + interim : ""), true);
    } else if (interim) {
      onTranscript(intermediateTranscript + (interim ? " " + interim : ""), false);
    }
  };
  sr.onerror = () => { /* ignore; fall back to silence timer */ };
  sr.onend = () => {
    // If still recording and transcripts have stopped, auto-stop on silence.
    if (recorder && recorder.state === "recording") {
      scheduleSilenceStop();
    }
  };
  recognition = sr;
  try { sr.start(); } catch { /* already started */ }
  return true;
}

function scheduleSilenceStop() {
  // Auto-stop after ~2.5s of no final transcript while idle-audio.
  if (silenceTimer) clearTimeout(silenceTimer);
  silenceTimer = setTimeout(() => {
    if (recorder && recorder.state === "recording") {
      stopVoiceRecording().catch(() => {});
    }
  }, 2500);
}

export function speechRecognitionSupported(): boolean {
  const w = window as unknown as Record<string, unknown>;
  return Boolean(w.SpeechRecognition || w.webkitSpeechRecognition);
}

/** POST a raw audio blob to the server-side transcription pipeline.
 *
 * Phase 3 v2.1: sends the recorded blob to `/api/v1/voice/transcribe` and
 * returns the transcript text (or "" on any failure). The server prefers
 * faster-whisper/whisper and falls back deterministically so the agent prompt
 * flow is unaffected on devices without a local STT backend.
 */
export async function transcribeAudio(
  blob: Blob,
  apiBase?: string,
  apiKey?: string,
): Promise<string> {
  try {
    const base = (apiBase ?? "").replace(/\/+$/, "") || "http://localhost:8000";
    const form = new FormData();
    const name = blob.type.includes("wav") ? "audio.wav" : `audio.${extFromMime(blob.type)}`;
    form.append("audio", blob, name);
    form.append("language", "auto");
    const headers: Record<string, string> = {};
    if (apiKey) headers["X-API-Key"] = apiKey;
    const resp = await fetch(`${base}/api/v1/voice/transcribe`, {
      method: "POST",
      headers,
      body: form,
    });
    if (!resp.ok) return "";
    const data = (await resp.json()) as { text?: string; status?: string };
    return data.text ?? "";
  } catch {
    return "";
  }
}

function extFromMime(mime: string): string {
  const m = (mime || "").toLowerCase();
  if (m.includes("wav")) return "wav";
  if (m.includes("m4a") || m.includes("mp4")) return "m4a";
  return "webm";
}

/** Start collecting microphone audio with optional live transcription callback. */
export async function startVoiceRecording(
  onTranscript?: (text: string, final: boolean) => void,
): Promise<void> {
  await requestMicrophonePermission();
  latestStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  // Defer MediaRecorder instantiation to next microtask so the render cycle stays snappy
  await new Promise<void>((resolve) => queueMicrotask(() => {
    const mime = pickMime();
    const rec = new MediaRecorder(latestStream!, mime ? { mimeType: mime } : undefined);
    recChunks = [];
    rec.ondataavailable = (e) => {
      if (e.data.size > 0) recChunks.push(e.data);
    };
    recorder = rec;
    recordingStartedAt = performance.now();
    rec.start();
    resolve();
  }));

  onTranscriptCb = onTranscript ?? null;
  if (onTranscript) {
    if (!startSpeechRecognition(onTranscript)) {
      scheduleSilenceStop();
    }
  }
}

function collectBlob(): Promise<{ blob: Blob; mime: string }> {
  const rec = recorder;
  if (!rec) return Promise.resolve({ blob: new Blob([], { type: "audio/webm" }), mime: "audio/webm" });
  return new Promise((resolve) => {
    const done = rec.onstop;
    rec.onstop = () => {
      if (typeof done === "function") (done as () => void).call(rec);
      resolve({ blob: new Blob(recChunks, { type: rec.mimeType || "audio/webm" }), mime: rec.mimeType || "audio/webm" });
    };
    try { rec.stop(); } catch { resolve({ blob: new Blob(recChunks, { type: rec.mimeType || "audio/webm" }), mime: rec.mimeType || "audio/webm" }); }
    // Safety: never hang forever — resolve with whatever we have after 3s.
    setTimeout(() => {
      resolve({ blob: new Blob(recChunks, { type: rec.mimeType || "audio/webm" }), mime: rec.mimeType || "audio/webm" });
    }, 3000);
  });
}

/**
 * Stop, try to decode to PCM WAV; fall back to the raw recorded blob base64
 * so the client NEVER freezes stuck on "recording…".
 */
export async function stopVoiceRecording(): Promise<VoicedAudio | null> {
  if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }
  if (recognition) {
    try { (recognition as { stop?: () => void }).stop?.(); } catch { /* noop */ }
    recognition = null;
  }
  const durationSec = Math.round(((performance.now() - recordingStartedAt) / 1000) * 100) / 100;
  const transcript = onTranscriptCb ? intermediateTranscript : undefined;

  const { blob, mime } = recChunks.length || recorder
    ? await collectBlob()
    : { blob: new Blob([], { type: "audio/webm" }), mime: "audio/webm" };
  latestStream?.getTracks().forEach((t) => t.stop());
  latestStream = null;
  recorder = null;
  onTranscriptCb = null;

  if (blob.size === 0) return null;

  // Prefer WAV (backend expects wav via _save_wav); fall back to the raw blob.
  try {
    audioCtx = audioCtx ?? new AudioContext();
    const arrayBuffer = await blob.arrayBuffer();
    const decoded = await audioCtx.decodeAudioData(arrayBuffer);
    await audioCtx.close().catch(() => void 0);
    audioCtx = null;
    const wav = encodeWav(decoded);
    const dataB64 = await blobToBase64(wav);
    return { dataB64, durationSec, mime: "audio/wav", transcript };
  } catch {
    audioCtx?.close().catch(() => void 0);
    audioCtx = null;
    const dataB64 = await blobToBase64(blob).catch(() => "");
    if (!dataB64) return null;
    return { dataB64, durationSec, mime, transcript };
  }
}

let intermediateTranscript = "";

export function setIntermediateTranscript(text: string) {
  intermediateTranscript = text;
}

/** Whether a voice session is actively capturing. */
export function voiceRecording(): boolean {
  return recorder !== null && recorder.state === "recording";
}
