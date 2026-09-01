/**
 * Gemini Engine Provider — Phase 1.
 * Maps Genio internal execution schema (streaming, tool calls) to Gemini API natively.
 * User never sees Gemini interface — Genio UI is sole interface.
 */

import type { Attachment, ChatEvent } from "../types";
import { GENIO_PERSONA_PROMPT } from "../persona";
import { getGoogleToken } from "../googleAuth";

export const GEMINI_MODEL = "gemini-2.0-flash";
export const GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta";

export interface GeminiConfig {
  apiKey?: string;
  oauthToken?: string;
  model?: string;
}

function resolveAuth(config?: GeminiConfig): string | null {
  if (config?.apiKey) return config.apiKey;
  if (config?.oauthToken) return config.oauthToken;
  const token = getGoogleToken();
  if (token) return token;
  return (import.meta.env.VITE_GEMINI_API_KEY as string) || null;
}

function buildUrl(model: string, auth: string | null, stream: boolean): string {
  const m = model || GEMINI_MODEL;
  const base = `${GEMINI_API_BASE}/models/${m}:${stream ? "streamGenerateContent" : "generateContent"}`;
  if (!auth) return base;
  // OAuth token uses Authorization header, API key uses ?key=
  if (auth.startsWith("mock-") || auth.startsWith("ya29.") || auth.includes(".")) {
    return base;
  }
  return `${base}?key=${encodeURIComponent(auth)}`;
}

function toGeminiParts(prompt: string, attachments?: Attachment[]): Array<Record<string, unknown>> {
  const parts: Array<Record<string, unknown>> = [{ text: prompt }];
  if (attachments?.length) {
    for (const a of attachments) {
      if (a.content) parts.push({ text: `\n[FILE ${a.name}]\n${a.content.slice(0, 4000)}` });
      else if (a.dataB64 && a.type.startsWith("image/")) {
        parts.push({ inlineData: { mimeType: a.type, data: a.dataB64 } });
      }
    }
  }
  return parts;
}

function mapToolCallsToDeclarations(): Array<Record<string, unknown>> {
  return [
    {
      name: "bash",
      description: "Execute a shell command on the device",
      parameters: { type: "OBJECT", properties: { command: { type: "STRING", description: "Shell command" } }, required: ["command"] },
    },
    {
      name: "browser",
      description: "Headless browsing",
      parameters: { type: "OBJECT", properties: { action: { type: "STRING" }, url: { type: "STRING" } }, required: ["action"] },
    },
    {
      name: "computer",
      description: "GUI control",
      parameters: { type: "OBJECT", properties: { action: { type: "STRING" } }, required: ["action"] },
    },
  ];
}

export interface GeminiStreamChunk {
  text?: string;
  toolCall?: { name: string; args: Record<string, unknown> };
  done?: boolean;
  raw?: unknown;
}

/**
 * Stream Gemini with persona injection. Yields text chunks mapped to Genio ChatEvent types.
 */
export async function* streamGemini(
  prompt: string,
  opts?: { config?: GeminiConfig; attachments?: Attachment[]; signal?: AbortSignal }
): AsyncGenerator<GeminiStreamChunk> {
  const auth = resolveAuth(opts?.config);
  const url = buildUrl(opts?.config?.model || GEMINI_MODEL, auth, true);

  const body = {
    contents: [{ role: "user", parts: toGeminiParts(prompt, opts?.attachments) }],
    systemInstruction: { parts: [{ text: GENIO_PERSONA_PROMPT }] },
    generationConfig: { temperature: 0.7, maxOutputTokens: 2048, topP: 0.9 },
    tools: [{ functionDeclarations: mapToolCallsToDeclarations() }],
  };

  // If no auth (offline CI/build), emit mock Darija streaming to satisfy UI without network
  if (!auth || auth.startsWith("mock-")) {
    const mock = "Ya ahla, ena Genio men HiTechLab! 🚀 Chnowa n3awnk lyoum? (mock Gemini stream, Darija persona active)";
    for (const w of mock.split(" ")) {
      await new Promise((r) => setTimeout(r, 18));
      if (opts?.signal?.aborted) break;
      yield { text: w + " " };
    }
    yield { done: true };
    return;
  }

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (auth && (auth.startsWith("ya29.") || auth.includes("."))) headers.Authorization = `Bearer ${auth}`;

  const resp = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    signal: opts?.signal,
  });

  if (!resp.ok) {
    const err = await resp.text().catch(() => resp.statusText);
    throw new Error(`Gemini ${resp.status}: ${err.slice(0, 400)}`);
  }

  if (!resp.body) {
    const data = (await resp.json()) as { candidates?: Array<{ content?: { parts?: Array<{ text?: string }> } }> };
    const text = data.candidates?.[0]?.content?.parts?.map((p) => p.text).join("") ?? "";
    if (text) yield { text };
    yield { done: true };
    return;
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop() ?? "";
      for (const line of lines) {
        const t = line.trim();
        if (!t || t === "[" || t === "]" || t === ",") continue;
        try {
          const json = JSON.parse(t.replace(/,$/, ""));
          const cands = (json.candidates || []) as Array<{ content?: { parts?: Array<{ text?: string; functionCall?: { name: string; args: Record<string, unknown> } }> } }>;
          for (const c of cands) {
            for (const p of c.content?.parts ?? []) {
              if (p.text) yield { text: p.text, raw: json };
              if (p.functionCall) yield { toolCall: { name: p.functionCall.name, args: p.functionCall.args }, raw: json };
            }
          }
        } catch {
          // ignore partial JSON
        }
      }
      if (opts?.signal?.aborted) break;
    }
  } finally {
    reader.releaseLock();
  }
  yield { done: true };
}

/**
 * Non-streaming helper — returns full text.
 */
export async function generateGemini(prompt: string, opts?: { config?: GeminiConfig; attachments?: Attachment[] }): Promise<string> {
  let out = "";
  for await (const chunk of streamGemini(prompt, opts)) {
    if (chunk.text) out += chunk.text;
  }
  return out.trim();
}

/**
 * Map Gemini chunks to Genio ChatEvents for UI consumption.
 */
export function geminiToGenioEvents(chunk: GeminiStreamChunk): ChatEvent[] {
  if (chunk.toolCall) {
    const cmd = JSON.stringify({ tool: chunk.toolCall.name, command: JSON.stringify(chunk.toolCall.args) });
    return [{ type: "tool_call", command: cmd }];
  }
  if (chunk.text) return [{ type: "thought", text: chunk.text }];
  return [];
}

export function getGeminiAuthHeader(): Record<string, string> {
  const t = getGoogleToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}
