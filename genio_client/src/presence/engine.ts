/**
 * Presence engine — the 9-state G6-B model, resolved ONLY from real
 * application/backend state. No timers, no randomness, no simulation.
 * Built ON resolvePresence (no duplicate machine): maps app facts to
 * the canonical presence contract, then to visual configuration.
 */
import { resolvePresence } from "./resolve";
import type { GenioPresenceState } from "./types";

export type EngineState =
  | "READY" | "LISTENING" | "THINKING" | "TASK_RUNNING" | "TOOL_ACTIVITY"
  | "COMPLETE" | "ERROR" | "OFFLINE" | "RECONNECTING";

export interface AppFacts {
  online: boolean;
  socket: "idle" | "connecting" | "connected" | "error" | "disconnected";
  agent: string;
  streaming: boolean;
  typing: boolean;
  taskActive: boolean;
  toolActive: boolean;
  needsInput: boolean;
  error?: string;
  lastOutcome?: "success" | "error";
  sessionAgeMin: number;
}

export interface VisualConfig {
  image: "base" | "wave" | "wink";
  motion: "none" | "breathe" | "pulse" | "signal";
  attention: "low" | "medium" | "high";
  statusTone: "ok" | "info" | "warn" | "error";
}

const VISUALS: Record<EngineState, VisualConfig> = {
  READY: { image: "base", motion: "breathe", attention: "low", statusTone: "ok" },
  LISTENING: { image: "wave", motion: "none", attention: "medium", statusTone: "info" },
  THINKING: { image: "base", motion: "pulse", attention: "high", statusTone: "info" },
  TASK_RUNNING: { image: "base", motion: "pulse", attention: "high", statusTone: "info" },
  TOOL_ACTIVITY: { image: "base", motion: "signal", attention: "high", statusTone: "info" },
  COMPLETE: { image: "wink", motion: "none", attention: "medium", statusTone: "ok" },
  ERROR: { image: "base", motion: "none", attention: "medium", statusTone: "error" },
  OFFLINE: { image: "base", motion: "none", attention: "low", statusTone: "warn" },
  RECONNECTING: { image: "base", motion: "pulse", attention: "medium", statusTone: "warn" },
};

export interface EngineOutput {
  engine: EngineState;
  presence: GenioPresenceState;
  visual: VisualConfig;
}

export function resolveEngine(facts: AppFacts): EngineOutput {
  let engine: EngineState;
  if (!facts.online || facts.socket === "disconnected") {
    engine = "OFFLINE";
  } else if (facts.socket === "error") {
    engine = "ERROR";
  } else if (facts.error) {
    engine = "ERROR";
  } else if (facts.socket === "connecting") {
    engine = "RECONNECTING";
  } else if (facts.needsInput) {
    engine = "LISTENING";
  } else if (facts.lastOutcome === "success") {
    engine = "COMPLETE";
  } else if (facts.lastOutcome === "error") {
    engine = "ERROR";
  } else if (facts.toolActive) {
    engine = "TOOL_ACTIVITY";
  } else if (facts.taskActive || facts.streaming) {
    // Streaming answer = work still in flight (never premature COMPLETE).
    engine = "TASK_RUNNING";
  } else if (facts.typing) {
    engine = "LISTENING";
  } else if (facts.agent === "thinking" || facts.agent === "planning") {
    engine = "THINKING";
  } else {
    engine = "READY";
  }
  const presence = resolvePresence({
    socket: facts.socket,
    agent: engine === "TASK_RUNNING" ? "executing" : engine === "THINKING" ? "thinking" : facts.agent,
    streaming: facts.streaming,
    typing: facts.typing,
    taskActive: facts.taskActive,
    needsInput: facts.needsInput,
    error: facts.error,
    lastOutcome: engine === "COMPLETE" ? "success" : undefined,
    sessionAgeMin: facts.sessionAgeMin,
  });
  return { engine, presence, visual: VISUALS[engine] };
}
