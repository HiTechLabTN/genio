import { useEffect, useRef } from "react";
import { runDesktopCommand } from "./bridge";

/**
 * Task → notification pipeline (OUTPUT ONLY).
 * Watches real task lifecycle transitions and emits typed notifications:
 * TASK_COMPLETED / TASK_FAILED. Bodies carry status only — never task
 * content, never secrets. No-op when notifications unavailable.
 */
export type TaskLifecycle = "idle" | "running" | "completed" | "failed" | "cancelled";

export function lifecycleOf(isProcessing: boolean, result: string, error: string | null): TaskLifecycle {
  if (isProcessing) return "running";
  if (error) return "failed";
  if (result) return "completed";
  return "idle";
}

export function useTaskNotifications(isProcessing: boolean, result: string, error: string | null): void {
  const prev = useRef<TaskLifecycle>("idle");
  useEffect(() => {
    const cur = lifecycleOf(isProcessing, result, error);
    const was = prev.current;
    prev.current = cur;
    if (was === cur) return;
    if (was === "running" && cur === "completed") {
      void runDesktopCommand({ cmd: "desktop.notification", title: "Genio task completed", body: "Your task finished successfully." });
    } else if (was === "running" && cur === "failed") {
      void runDesktopCommand({ cmd: "desktop.notification", title: "Genio task failed", body: "The task ended with an error. See details in the app." });
    }
  }, [isProcessing, result, error]);
}
