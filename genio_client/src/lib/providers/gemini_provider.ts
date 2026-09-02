/**
 * Gemini Engine Provider — Phase C (server-proxied).
 * Client never holds the Gemini API key and never calls
 * generativelanguage.googleapis.com directly. All Gemini traffic
 * is routed through the Genio server via ModelRouter (GENIO_GEMINI_API_KEY
 * lives only in the server env). This file is the client-side
 * adapter that calls the server proxy.
 */

import type { Attachment, ChatEvent } from "../types";
import { GENIO_PERSONA_PROMPT } from "../persona";
import { getGoogleToken } from "../googleAuth";

export const GEMINI_MODEL = "gemini-2.0-flash";
// Server proxy base — never the Google endpoint directly
export const GEMINI_API_BASE = "/api/v1/gemini";

export interface GeminiConfig {
  apiKey?: string;
  oauthToken?: string;
  model?: string;
  /** Optional server base to proxy through (e.g. http://TN_VPS:8000) */
  serverBase?: string;
}

function resolveAuth(config?: GeminiConfig): string | null {
  if (config?.apiKey) return config.apiKey;
  if (config?.oauthToken) return config.oauthToken;
  const token = getGoogleToken();
  if (token) return token;
  return null;
}

function buildUrl(config?: GeminiConfig, stream: boolean = true): string {
  const base = (config?.serverBase?.replace(/\/$/, "") ?? "") + GEMINI_API_BASE;
  const m = config?.model || GEMINI_MODEL;
  return `${base}/models/${m}:${stream ? "streamGenerateContent" : "generateContent"}`;
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
 * Stream Gemini via the Genio server proxy (never direct to Google).
 * The server reads GENIO_GEMINI_API_KEY from its env and forwards
 * to generativelanguage.googleapis.com using ModelRouter.
 */
export async function* streamGemini(
  prompt: string,
  opts?: { config?: GeminiConfig; attachments?: Attachment[]; signal?: AbortSignal }
): AsyncGenerator<GeminiStreamChunk> {
  const auth = resolveAuth(opts?.config);
  // Server proxy URL — no key in query, auth via header forwarded to server
  const url = buildUrl(opts?.config, true);

  const body = {
    contents: [{ role: "user", parts: toGeminiParts(prompt, opts?.attachments) }],
    systemInstruction: { parts: [{ text: GENIO_PERSONA_PROMPT }] },
    generationConfig: { temperature: 0.7, maxOutputTokens: 2048, topP: 0.9 },
    tools: [{ functionDeclarations: mapToolCallsToDeclarations() }],
  };

  if (!auth) {
    throw new Error("السيرفر طايح توا، ما نجمش نكوّنكتي.");
  }
  if (auth.startsWith("mock-")) {
    throw new Error("السيرفر طايح توا، ما نجمش نكوّنكتي.");
  }

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (auth && (auth.startsWith("ya29.") || auth.includes("."))) headers.Authorization = `Bearer ${auth}`;

  let resp: Response;
  try {
    resp = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      signal: opts?.signal,
    });
  } catch {
    throw new Error("السيرفر طايح توا، ما نجمش نكوّنكتي.");
  }

  if (!resp.ok) {
    if (resp.status >= 500 || resp.status === 0) {
      throw new Error("السيرفر طايح توا، ما نجمش نكوّنكتي.");
    }
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
  let thinkingStreak = 0;
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
              if (p.text) {
                const trimmed = p.text.trim();
                const isThinking = trimmed === "/* thinking */" || trimmed.includes("/* thinking */");
                if (isThinking) {
                  thinkingStreak++;
                  if (thinkingStreak > 3) {
                    yield { text: "السيرفر طايح توا، ما نجمش نكوّنكتي.", done: true } as GeminiStreamChunk;
                    try { await reader.cancel(); } catch {}
                    return;
                  }
                  continue;
                }
                thinkingStreak = 0;
                yield { text: p.text, raw: json };
              }
              if (p.functionCall) {
                thinkingStreak = 0;
                yield { toolCall: { name: p.functionCall.name, args: p.functionCall.args }, raw: json };
              }
            }
          }
        } catch {
          // ignore partial JSON
        }
      }
      if (opts?.signal?.aborted) break;
    }
  } finally {
    try { reader.releaseLock(); } catch {}
  }
  yield { done: true };
}

/**
 * Non-streaming helper — returns full text via server proxy.
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
