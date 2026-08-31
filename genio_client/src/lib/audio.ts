export interface VoicedAudio {
  dataB64: string;
  durationSec: number;
}

let recorder: MediaRecorder | null = null;
let latestStream: MediaStream | null = null;
let audioCtx: AudioContext | null = null;
let recChunks: Blob[] = [];
let recordingStartedAt = 0;

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

/** Start collecting microphone audio. Call once; pairing with `stopVoiceRecording`. */
export async function startVoiceRecording(): Promise<void> {
  latestStream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
  });
  const mime = pickMime();
  const rec = new MediaRecorder(latestStream, mime ? { mimeType: mime } : undefined);
  recChunks = [];
  rec.ondataavailable = (e) => {
    if (e.data.size > 0) recChunks.push(e.data);
  };
  recorder = rec;
  recordingStartedAt = performance.now();
  rec.start();
}

/** Stop, decode to PCM, re-encode as real WAV and return base64 for `voice_wav`. */
export async function stopVoiceRecording(): Promise<VoicedAudio | null> {
  const rec = recorder;
  if (!rec || rec.state === "inactive") return null;
  const durationSec = Math.round(((performance.now() - recordingStartedAt) / 1000) * 100) / 100;

  const blob = await new Promise<Blob>((resolve) => {
    rec.onstop = () => resolve(new Blob(recChunks, { type: rec.mimeType || "audio/webm" }));
    rec.stop();
  });
  latestStream?.getTracks().forEach((t) => t.stop());

  try {
    audioCtx = audioCtx ?? new AudioContext();
    const arrayBuffer = await blob.arrayBuffer();
    const decoded = await audioCtx.decodeAudioData(arrayBuffer);
    await audioCtx.close().catch(() => void 0);
    audioCtx = null;

    const wav = encodeWav(decoded);
    const dataB64 = await blobToBase64(wav);
    recorder = null;
    latestStream = null;
    return { dataB64, durationSec };
  } catch {
    recorder = null;
    latestStream = null;
    return null;
  }
}

/** Whether a voice session is actively capturing. */
export function voiceRecording(): boolean {
  return recorder !== null && recorder.state === "recording";
}