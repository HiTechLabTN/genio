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

export type AgentStatus =
  | { kind: "idle" }
  | { kind: "thinking" }
  | { kind: "executing"; tool: string }
  | { kind: "completed" };

export interface Attachment {
  id: string;
  name: string;
  type: string;
  dataB64: string;
  size: number;
  content?: string;
}

export interface ToolResultMap {
  command?: string;
  stdout?: string;
  stderr?: string;
  returncode?: number;
  duration?: number;
  timed_out?: boolean;
  success?: boolean;
  error?: string;
  output?: string;
  [key: string]: unknown;
}

export interface AudioPayload {
  url?: string;
  dataB64?: string;
  mime?: string;
}

export type ChatEvent =
  | { type: "thought"; text: string }
  | { type: "answer"; text: string; audio?: AudioPayload }
  | { type: "tool_call"; command: string }
  | { type: "tool_result"; result: ToolResultMap }
  | { type: "stats"; tokens?: number; tok_per_s?: number }
  | { type: "error"; message: string }
  | { type: "attached"; kind?: string; path?: string; name?: string }
  | { type: "killed" | "armed" }
  | { type: "artifact"; title?: string; content?: string; artifact_type?: string; mime?: string }
  | { type: "session"; session?: Record<string, unknown> }
  | { type: "user"; text: string; attachments?: { name: string; content?: string }[]; audio?: AudioPayload; timestamp?: number };

export type GenioEvent =
  | ({ type: "telemetry" } & Record<string, unknown>)
  | ({ type: "pong" } & Record<string, unknown>)
  | { type: "screen"; data_b64: string }
  | { type: "browser_view"; data_b64: string }
  | { type: "screen_stream"; active?: boolean; interval?: number }
  | { type: "voice_ready"; path?: string; duration?: number }
  | { type: string; [key: string]: unknown } // tolerant fallback — unknown future types don't crash
  | ChatEvent;

export interface TelemetrySnapshot {
  node?: string;
  hostname?: string;
  uptime_s?: number;
  cpu_percent?: number;
  ram_percent?: number;
  ram_used_gb?: number;
  ram_total_gb?: number;
  gpu?: { name?: string; used_gb?: number; total_gb?: number; vram_pct?: number };
  model?: string;
  mode?: string;
  last_tok_per_s?: number;
  clients?: number;
  armed?: boolean;
  ts?: number;
  [key: string]: unknown;
}

export interface UseGenioSocket {
  status: SocketStatus;
  agentStatus: AgentStatus;
  socket: unknown;
  telemetry: TelemetrySnapshot | null;
  telemetryStale: boolean;
  chat: ChatEvent[];
  screen: string | null;
  streaming: boolean;
  addChat: Dispatch<SetStateAction<ChatEvent[]>>;
  connect: (target: ServerNode) => Promise<boolean>;
  disconnect: () => void;
  send: (payload: Record<string, unknown>) => boolean;
  sendPrompt: (text: string, attachments?: Attachment[]) => boolean;
  kill: () => boolean;
  continuePrompt: (lastPrompt: string) => boolean;
  requestScreenshot: () => boolean;
  toggleScreenStream: (active: boolean) => boolean;
  error?: string;
  connectionToast?: string | null;
}