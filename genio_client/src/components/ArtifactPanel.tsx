import type { ChatEvent } from "../lib/types";

export interface Artifact {
  id: string;
  type: "code" | "markdown" | "image" | "table" | "file";
  title?: string;
  content: string;
  language?: string;
  mime?: string;
}

interface Props {
  artifacts: Artifact[];
  chat?: ChatEvent[];
}

export default function ArtifactPanel({ artifacts }: Props) {
  if (!artifacts || artifacts.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-sm text-slate-500">
        No artifacts yet
      </div>
    );
  }
  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto p-4">
      {artifacts.map((a) => (
        <div
          key={a.id}
          className="rounded-xl border border-slate-700/60 bg-slate-900/40 p-3"
        >
          {a.title && (
            <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-slate-400">
              <span className="rounded bg-neon/10 px-1.5 py-0.5 text-neon text-[10px] uppercase">{a.type}</span>
              {a.title}
            </div>
          )}
          {a.type === "code" && (
            <pre className="overflow-x-auto rounded bg-slate-950 p-3 text-xs text-slate-200">
              <code>{a.content}</code>
            </pre>
          )}
          {a.type === "markdown" && (
            <div className="prose prose-invert prose-sm max-w-none whitespace-pre-wrap text-slate-200">
              {a.content}
            </div>
          )}
          {a.type === "image" && (
            <img src={a.content} alt={a.title || "artifact"} className="max-w-full rounded" />
          )}
          {a.type === "table" && (
            <div className="overflow-x-auto text-xs text-slate-300 whitespace-pre-wrap">{a.content}</div>
          )}
          {a.type === "file" && (
            <div className="text-xs text-cyan-300">📎 {a.title} → {a.content}</div>
          )}
        </div>
      ))}
    </div>
  );
}

/** Extract artifacts from chat events (tool results that contain code/markdown). */
export function artifactsFromChat(chat: ChatEvent[]): Artifact[] {
  const arts: Artifact[] = [];
  for (let i = 0; i < chat.length; i++) {
    const ev = chat[i] as unknown as Record<string, unknown>;
    if (ev.type === "tool_result" && typeof ev.result === "object" && ev.result) {
      const r = ev.result as Record<string, unknown>;
      const out = (r.stdout as string) || (r.output as string) || "";
      if (out && out.length > 20) {
        const isCode = out.includes("```") || out.trimStart().startsWith("{") || out.includes("def ") || out.includes("import ");
        arts.push({
          id: `tool-${i}`,
          type: isCode ? "code" : "markdown",
          title: `Tool output #${i}`,
          content: out.slice(0, 4000),
          language: isCode ? "text" : "markdown",
        });
      }
    }
    if (ev.type === "artifact" && typeof ev.content === "string") {
      arts.push({
        id: `artifact-${i}`,
        type: (ev.artifact_type as Artifact["type"]) || "markdown",
        title: (ev.title as string) || undefined,
        content: ev.content as string,
      });
    }
  }
  return arts;
}
