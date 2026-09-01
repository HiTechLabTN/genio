/**
 * Native Android & Web permission orchestration — Phase 1.
 *
 * Covers: CAMERA (face tracking), RECORD_AUDIO (voice), INTERNET/ACCESS_NETWORK_STATE,
 * READ_EXTERNAL_STORAGE / READ_MEDIA_* (attachments). Gracefully degrades on desktop/web.
 */

export type PermissionKind = "camera" | "microphone" | "storage" | "network";

export interface PermissionStatus {
  kind: PermissionKind;
  granted: boolean;
  message: string;
  canRequest: boolean;
}

export interface PermissionSnapshot {
  camera: PermissionStatus;
  microphone: PermissionStatus;
  storage: PermissionStatus;
  network: PermissionStatus;
  allGranted: boolean;
}

async function queryPermission(name: string): Promise<PermissionState | null> {
  try {
    if (!navigator.permissions?.query) return null;
    // @ts-ignore - some browsers support camera/mic permission names
    const result = await navigator.permissions.query({ name: name as PermissionName });
    return result.state;
  } catch {
    return null;
  }
}

export async function checkCamera(): Promise<PermissionStatus> {
  const state = await queryPermission("camera");
  if (state === "granted") return { kind: "camera", granted: true, message: "granted", canRequest: true };
  if (state === "denied") return { kind: "camera", granted: false, message: "denied – check OS settings", canRequest: false };
  // Fallback: probe getUserMedia without keeping stream
  try {
    if (!navigator.mediaDevices?.getUserMedia) return { kind: "camera", granted: false, message: "not supported", canRequest: false };
    const s = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } });
    s.getTracks().forEach((t) => t.stop());
    return { kind: "camera", granted: true, message: "granted", canRequest: true };
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    if (msg.includes("NotAllowedError") || msg.includes("Permission denied")) {
      return { kind: "camera", granted: false, message: "permission denied", canRequest: true };
    }
    if (msg.includes("NotFoundError")) return { kind: "camera", granted: false, message: "no camera", canRequest: false };
    return { kind: "camera", granted: false, message: msg, canRequest: true };
  }
}

export async function checkMicrophone(): Promise<PermissionStatus> {
  const state = await queryPermission("microphone");
  if (state === "granted") return { kind: "microphone", granted: true, message: "granted", canRequest: true };
  if (state === "denied") return { kind: "microphone", granted: false, message: "denied – check OS settings", canRequest: false };
  // try direct probe
  try {
    if (!navigator.mediaDevices?.getUserMedia) return { kind: "microphone", granted: false, message: "not supported", canRequest: false };
    const s = await navigator.mediaDevices.getUserMedia({ audio: true });
    s.getTracks().forEach((t) => t.stop());
    return { kind: "microphone", granted: true, message: "granted", canRequest: true };
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    if (msg.includes("NotAllowedError") || msg.includes("Permission")) return { kind: "microphone", granted: false, message: "permission denied", canRequest: true };
    if (msg.includes("NotFoundError")) return { kind: "microphone", granted: false, message: "no microphone", canRequest: false };
    return { kind: "microphone", granted: false, message: msg, canRequest: true };
  }
}

export async function checkStorage(): Promise<PermissionStatus> {
  // On web, File System Access is implicit; on Android, we treat as granted if FileReader works.
  // Best-effort: if navigator.storage exists, assume granted.
  const hasFile = typeof FileReader !== "undefined";
  return {
    kind: "storage",
    granted: hasFile,
    message: hasFile ? "granted" : "File API unavailable",
    canRequest: hasFile ? false : true,
  };
}

export async function checkNetwork(): Promise<PermissionStatus> {
  const online = typeof navigator !== "undefined" ? navigator.onLine : true;
  return {
    kind: "network",
    granted: online,
    message: online ? "online" : "offline",
    canRequest: !online,
  };
}

export async function verifyCapabilities(): Promise<PermissionSnapshot> {
  const [camera, microphone, storage, network] = await Promise.all([
    checkCamera(),
    checkMicrophone(),
    checkStorage(),
    checkNetwork(),
  ]);
  const allGranted = camera.granted && microphone.granted && storage.granted && network.granted;
  return { camera, microphone, storage, network, allGranted };
}

export async function requestCamera(): Promise<PermissionStatus> {
  try {
    const s = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user", width: 320, height: 240 } });
    s.getTracks().forEach((t) => t.stop());
    return { kind: "camera", granted: true, message: "granted", canRequest: true };
  } catch (e: unknown) {
    return { kind: "camera", granted: false, message: e instanceof Error ? e.message : String(e), canRequest: false };
  }
}

export async function requestMicrophone(): Promise<PermissionStatus> {
  try {
    const s = await navigator.mediaDevices.getUserMedia({ audio: true });
    s.getTracks().forEach((t) => t.stop());
    return { kind: "microphone", granted: true, message: "granted", canRequest: true };
  } catch (e: unknown) {
    return { kind: "microphone", granted: false, message: e instanceof Error ? e.message : String(e), canRequest: false };
  }
}

export async function requestAll(): Promise<PermissionSnapshot> {
  // Sequential to avoid concurrent getUserMedia collisions on Android WebView
  const cam = await requestCamera().catch(() => ({ kind: "camera" as const, granted: false, message: "failed", canRequest: false }));
  const mic = await requestMicrophone().catch(() => ({ kind: "microphone" as const, granted: false, message: "failed", canRequest: false }));
  const storage = await checkStorage();
  const network = await checkNetwork();
  return { camera: cam, microphone: mic, storage, network, allGranted: cam.granted && mic.granted && storage.granted && network.granted };
}

export const REQUIRED_PERMISSIONS: PermissionKind[] = ["camera", "microphone", "storage", "network"];
