/**
 * MascotEventBridge — clean event API between Genio and the mascot (§16).
 *
 * Adapts the existing architecture (useGenioSocket AgentStatus + chat +
 * connection state) to canonical mascot events. All payloads are sanitized;
 * animation names are validated against an allowlist (§31 — never execute
 * arbitrary animation code from user input, never build filesystem paths).
 */

export type MascotEventName =
  | "user.message.started"
  | "user.message.received"
  | "assistant.thinking.started"
  | "assistant.thinking.updated"
  | "assistant.speaking.started"
  | "assistant.speaking.viseme"
  | "assistant.speaking.ended"
  | "tool.started"
  | "tool.progress"
  | "tool.success"
  | "tool.error"
  | "task.started"
  | "task.success"
  | "task.failed"
  | "warning"
  | "notification"
  | "system.ready"
  | "system.busy"
  | "system.idle";

export type MascotEvent = {
  name: MascotEventName;
  at: number;
  text?: string;
  viseme?: string;
  progress?: number;
};

/** Allowlist of playable animation clips (master GLB + legacy runtime). */
const KNOWN_CLIPS = new Set([
  // master library
  "idle", "idle_variant_01", "idle_variant_02", "idle_thinking", "greeting",
  "wave", "listen", "listen_attentive", "think", "speak", "speak_emphasis",
  "laugh", "smile", "surprised", "happy", "sad", "angry", "confused",
  "curious", "excited", "apologize", "agree", "disagree", "nod", "shake_head",
  "point", "invite", "celebrate", "success", "error_reaction", "warning",
  "wait", "sleep", "wake", "walk", "run", "turn_left", "turn_right",
  "step_forward", "step_backward", "sit", "stand", "look_left", "look_right",
  "look_up", "look_down", "hero",
  // legacy runtime aliases
  "listening", "thinking", "executing", "error", "speaking",
]);

/** Validate an animation name — unknown names fall back to idle (§30). */
export function sanitizeClipName(name: unknown): string {
  if (typeof name !== "string") return "idle";
  const clean = name.trim().slice(0, 64);
  if (!/^[a-z0-9_]+$/i.test(clean)) return "idle";
  return KNOWN_CLIPS.has(clean) ? clean : "idle";
}

/** Map canonical event → master clip (data-driven default; memory may override). */
const EVENT_TO_CLIP: Record<MascotEventName, string> = {
  "user.message.started": "listen_attentive",
  "user.message.received": "listen",
  "assistant.thinking.started": "think",
  "assistant.thinking.updated": "idle_thinking",
  "assistant.speaking.started": "speak",
  "assistant.speaking.viseme": "speak",
  "assistant.speaking.ended": "idle",
  "tool.started": "executing",
  "tool.progress": "executing",
  "tool.success": "success",
  "tool.error": "error_reaction",
  "task.started": "executing",
  "task.success": "celebrate",
  "task.failed": "apologize",
  warning: "warning",
  notification: "curious",
  "system.ready": "greeting",
  "system.busy": "wait",
  "system.idle": "idle",
};

export function clipForEvent(name: MascotEventName): string {
  return EVENT_TO_CLIP[name] ?? "idle";
}

export type AgentStatusLike = { kind: string };
export type ChatLike = { type?: string };

/**
 * Derive canonical events from existing Genio state (AgentStatus + chat tail).
 * Pure function — easy to unit test, no socket dependency.
 */
export function deriveEvents(
  status: AgentStatusLike,
  prevStatus: AgentStatusLike | null,
  chatLength: number,
  prevChatLength: number,
  listening: boolean,
  speaking: boolean,
): MascotEvent[] {
  const now = Date.now();
  const out: MascotEvent[] = [];
  if (chatLength > prevChatLength) {
    out.push({ name: "user.message.received", at: now });
  }
  if (listening) {
    out.push({ name: "user.message.started", at: now });
    return out;
  }
  if (speaking) {
    if (!prevStatus || (prevStatus as { kind: string }).kind !== "executing") {
      out.push({ name: "assistant.speaking.started", at: now });
    }
    return out;
  }
  if (status.kind !== prevStatus?.kind) {
    switch (status.kind) {
      case "thinking":
        out.push({ name: "assistant.thinking.started", at: now });
        break;
      case "executing":
        out.push({ name: "tool.started", at: now });
        break;
      case "completed":
        out.push({ name: "task.success", at: now });
        break;
      case "error":
        out.push({ name: "tool.error", at: now });
        break;
      case "idle":
        out.push({ name: "system.idle", at: now });
        break;
      default:
        break;
    }
  }
  return out;
}
