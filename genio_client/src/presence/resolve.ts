/**
 * Presence resolver — REAL app/socket states → GenioPresenceState (§9).
 * Pure function, no side effects. Same object drives 2D dot, 3D mascot
 * and panels (§24 contract). Calm by default: low intensity unless
 * error/celebration demand attention.
 */
import type { AttentionTarget, GenioPresenceState, Intensity, LayoutMode, PresenceStateId } from "./types";

export interface AppContext {
  socket: "idle" | "connecting" | "connected" | "error" | "disconnected";
  agent: string;
  streaming: boolean;
  typing: boolean;
  error?: string;
  taskActive: boolean;
  needsInput: boolean;
  lastOutcome?: "success" | "error";
  sessionAgeMin: number;
}

export function resolvePresence(ctx: AppContext): GenioPresenceState {
  let semanticState: PresenceStateId = "idle";
  let attentionTarget: AttentionTarget = "user";
  let intensity: Intensity = "low";

  if (ctx.socket === "error" || ctx.socket === "disconnected") {
    semanticState = "disconnected";
    attentionTarget = "system-state";
    intensity = "medium";
  } else if (ctx.error) {
    semanticState = "error";
    attentionTarget = "question";
    intensity = "medium";
  } else if (ctx.needsInput) {
    semanticState = "asking_user";
    attentionTarget = "user";
  } else if (ctx.lastOutcome === "success") {
    semanticState = "success";
    attentionTarget = "success-result";
  } else if (ctx.lastOutcome === "error") {
    semanticState = "error";
    attentionTarget = "question";
    intensity = "medium";
  } else if (ctx.streaming) {
    semanticState = "explaining";
    attentionTarget = "chat";
  } else if (ctx.taskActive) {
    semanticState = "executing";
    attentionTarget = "task";
  } else if (ctx.typing) {
    semanticState = "listening";
    attentionTarget = "user";
  } else if (ctx.agent === "thinking" || ctx.agent === "planning") {
    semanticState = ctx.agent as PresenceStateId;
    attentionTarget = "task";
  } else if (ctx.socket === "connecting") {
    semanticState = "waiting";
    attentionTarget = "system-state";
  } else if (ctx.sessionAgeMin < 2) {
    semanticState = "greeting";
    attentionTarget = "user";
  }
  // Long sessions stay calm by default (pair dynamics, §10).
  // Nothing inferred about the user — only interaction context is used.
  return {
    semanticState,
    attentionTarget,
    intensity,
    gesture: semanticState,
    mood: semanticState === "error" ? "serious-calm" : semanticState === "success" ? "warm-brief" : "calm",
    focusPanel: attentionTarget === "task" ? "task" : attentionTarget === "chat" ? "chat" : "status",
    showResources: ctx.taskActive,
    showTaskDetails: ctx.taskActive || semanticState === "error",
  };
}

/** Adaptive layout mode from presence (§12). Pure advisor, never forces. */
export function layoutModeFor(state: GenioPresenceState, advanced: boolean): LayoutMode {
  if (advanced) return "developer";
  switch (state.semanticState) {
    case "thinking":
    case "planning":
      return "thinking";
    case "executing":
    case "waiting":
      return "execution";
    case "success":
    case "error":
      return "result";
    default:
      return "conversation";
  }
}
