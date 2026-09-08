/**
 * chatSanitize — single source of truth for the chat render policy (2.5D upgrade).
 *
 * - Discard any message containing "pong" (heartbeats).
 * - Discard objects with type "stats".
 * - Strip <thought>...</thought> blocks and bare "thought:" prefixes.
 * - Render ONLY pure user queries and clean assistant answers.
 */

export type ChatLike = { type?: string; text?: string; message?: string };

export function isRenderableEvent(c: ChatLike): boolean {
  const t = (c as { type?: string }).type;
  if (t === "pong") return false;
  if (t === "stats") return false;
  if (t === "thought") return false;
  const raw = JSON.stringify(c).toLowerCase();
  if (raw.includes("pong")) {
    const txt = (c.text ?? (c as { message?: string }).message ?? "").toLowerCase();
    if (txt.includes("pong") || t === "pong") return false;
  }
  if (t !== "user" && t !== "answer") {
    // Allow the two Tunisian auth/cloud answers; hide everything else internal.
    const txt = c.text ?? "";
    if (txt === "سجّل بـ Google باش تكمّل في السحاب") return true;
    if (txt === "مشكل في الاتصال بالسحاب — عاود جرّب") return true;
    return false;
  }
  const txt2 = c.text ?? "";
  if (/<thought[\s>]/i.test(txt2)) return false;
  if (/^thought\s*:/i.test(txt2.trim())) return false;
  return true;
}

/** Remove thought blocks, thought prefixes and stats JSON leakage from answers. */
export function cleanAnswerText(rawText: string | undefined): string | undefined {
  if (!rawText) return rawText;
  let t = rawText;
  t = t.replace(/<thought[^>]*>[\s\S]*?<\/thought>/gi, "");
  t = t.replace(/<thought[^>]*>/gi, "");
  t = t.replace(/<\/thought>/gi, "");
  t = t.replace(/^thought\s*:\s*/im, "");
  t = t.replace(/^\s*\{"type"\s*:\s*"stats"[\s\S]*?\}\s*/i, "");
  return t.trim();
}
