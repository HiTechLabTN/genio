/**
 * GenioPresenceEngine — types (§4 charter, §24 contract).
 * Semantic states only. No business logic, no commands, no rendering here.
 * UI (2D dot, 3D mascot, panels) consumes the SAME state object.
 */
export type PresenceStateId =
  | "idle" | "greeting" | "listening" | "understanding" | "thinking"
  | "planning" | "explaining" | "executing" | "waiting" | "asking_user"
  | "success" | "warning" | "error" | "recovering" | "celebrating"
  | "sleeping" | "disconnected" | "attention";

export type Intensity = "low" | "medium" | "high";

export type AttentionTarget =
  | "user" | "chat" | "task" | "tool-output" | "security-warning"
  | "success-result" | "question" | "system-state";

export interface GenioPresenceState {
  semanticState: PresenceStateId;
  attentionTarget?: AttentionTarget;
  intensity: Intensity;
  gesture?: string;
  mood?: string;
  focusPanel?: string;
  showResources?: boolean;
  showTaskDetails?: boolean;
}

export type LayoutMode =
  | "conversation" | "thinking" | "execution" | "developer" | "result";
