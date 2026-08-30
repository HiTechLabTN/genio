import type { Dispatch, SetStateAction } from "react";

export interface NodeTarget {
  id: string;
  label: string;
  host: string;
  port: number;
  key?: string;
}

export interface ServerNode {
  id: string;
  label: string;
  host: string;
  port: number;
  key?: string;
}

export type SocketStatus =
  | { kind: "idle" }
  | { kind: "connecting" }
  | { kind: "connected"; node?: string }
  | { kind: "error"; message: string };

/** A chat-relevant event pushed by the Genio backend agent loop. */
export type ChatEvent =
  | { type: "thought"; text: string }
  | { type: "answer"; text: string }
  | { type: "tool_call"; command: string }
  | { type: "tool_result"; result: Record<string, unknown> }
  | { type: "stats"; tokens?: number; tok_per_s?: number }
  | { type: "error"; message: string }
  | { type: "attached"; kind?: string; path?: string; name?: string }
  | { type: "killed" | "armed" };

/** Raw event received on the /ws/agent socket (superset of ChatEvent). */
export type GenioEvent =
  | ({ type: "telemetry" } & Record<string, unknown>)
  | ({ type: "pong" } & Record<string, unknown>)
  | ChatEvent;

export interface TelemetrySnapshot {
  cpu?: { percent: number; cores: number; temp_c?: number };
  ram?: { used_bytes: number; total_bytes: number };
  gpu?: { name: string; used_gb: number; total_gb: number };
  armed?: boolean;
  mode?: string;
  model?: string;
  uptime_s?: number;
  [key: string]: unknown;
}

export interface UseGenioSocket {
  status: SocketStatus;
  socket: unknown;
  telemetry: TelemetrySnapshot | null;
  chat: ChatEvent[];
  addChat: Dispatch<SetStateAction<ChatEvent[]>>;
  connect: (target: ServerNode) => Promise<boolean>;
  disconnect: () => void;
  send: (payload: Record<string, unknown>) => boolean;
  error?: string;
}