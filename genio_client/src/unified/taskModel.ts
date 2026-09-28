/**
 * Typed task model — derived ONLY from real hook data (no duplicate machine).
 * Progress is 0..100 ONLY when the backend provides measurable progress;
 * otherwise UNKNOWN (never fabricated). Cancellation follows the real
 * backend contract: requested → confirmed by 'killed' event → CANCELLED.
 */
export type TaskStatus = "QUEUED" | "RUNNING" | "WAITING" | "COMPLETED" | "FAILED" | "CANCELLED";
export type Cancellation = "none" | "requested" | "confirmed";

export interface TaskEventLike {
  type: string;
  text?: string;
  message?: string;
  command?: string;
  result?: { returncode?: number; stdout?: string; stderr?: string; error?: string };
  timestamp?: number;
}

export interface TaskModel {
  id: string;
  title: string;
  status: TaskStatus;
  createdAt: number | null;
  startedAt: number | null;
  completedAt: number | null;
  currentStep: string | null;
  progress: number | "UNKNOWN";
  tool: string | null;
  result: string | null;
  error: string | null;
  cancellation: Cancellation;
  steps: { kind: string; text: string; seq: number }[];
}

export interface TaskInput {
  active: boolean;
  result: string;
  error: string | null;
  cancelRequested: boolean;
  events: TaskEventLike[];
  now?: number;
}

export function buildTaskModel(input: TaskInput): TaskModel {
  const now = input.now ?? Date.now();
  const steps = input.events
    .filter((e) => e.type === "thought" || e.type === "tool_call" || e.type === "tool_result")
    .map((e, i) => ({
      kind: e.type,
      text: (e.text || e.command || e.message || "").slice(0, 160),
      seq: i + 1,
    }));
  const killed = input.events.some((e) => e.type === "killed");
  const lastTool = [...input.events].reverse().find((e) => e.type === "tool_call");
  const firstTs = input.events.find((e) => typeof e.timestamp === "number")?.timestamp ?? null;

  let status: TaskStatus = "QUEUED";
  let cancellation: Cancellation = "none";
  if (killed || (input.cancelRequested && !input.active)) {
    status = "CANCELLED";
    cancellation = "confirmed";
  } else if (input.cancelRequested && input.active) {
    status = "RUNNING";
    cancellation = "requested";
  } else if (input.error) {
    status = "FAILED";
  } else if (input.result) {
    status = "COMPLETED";
  } else if (input.active) {
    status = "RUNNING";
  }
  const currentStep = status === "RUNNING" && steps.length > 0
    ? steps[steps.length - 1].text
    : null;
  const title = steps.length > 0
    ? (steps[0].text.slice(0, 80) || "Task")
    : status === "QUEUED" ? "No active task" : "Task";
  return {
    id: `task-${firstTs ?? "live"}`,
    title,
    status,
    createdAt: firstTs,
    startedAt: status === "QUEUED" ? null : (firstTs ?? now),
    completedAt: status === "COMPLETED" || status === "FAILED" || status === "CANCELLED" ? now : null,
    currentStep,
    progress: "UNKNOWN",
    tool: (lastTool?.command ?? null),
    result: input.result || null,
    error: input.error,
    cancellation,
    steps,
  };
}

/** Sanitize tool/evidence text: strip secrets, credentials, long paths. */
export function sanitizeToolText(s: string): string {
  return s
    .replace(/sk-[A-Za-z0-9]{8,}/g, "[redacted]")
    .replace(/ghp_[A-Za-z0-9]{8,}/g, "[redacted]")
    .replace(/Bearer\s+[A-Za-z0-9._~+/-]{8,}/gi, "Bearer [redacted]")
    .replace(/(api[_-]?key|token|password|secret|passwd)\s*[:=]\s*\S+/gi, "$1=[redacted]")
    .replace(/\/home\/[^\s:'"]+/g, "~")
    .replace(/\/root\/[^\s:'"]+/g, "~")
    .slice(0, 500);
}
