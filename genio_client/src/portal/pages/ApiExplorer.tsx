import { PortalLayout } from "../PortalLayout";
import { Accordion, Badge, Card, Section } from "../ui";
import openapi from "../../schemas-openapi.json";

type Spec = { paths: Record<string, Record<string, { summary?: string; parameters?: unknown[] }>> };

function methodsOf(path: string): string[] {
  const spec = openapi as unknown as Spec;
  return Object.keys(spec.paths[path] || {}).map((m) => m.toUpperCase());
}

export default function ApiExplorer() {
  const spec = openapi as unknown as Spec;
  const paths = Object.keys(spec.paths || {}).sort();
  const ws = { path: "/ws/agent", methods: ["WS"], note: "Prompt stream: send {action:'prompt', text} → receive stats/answer frames. Same auth model as HTTP." };
  return (
    <PortalLayout title="API" description="Genio HTTP API derived from the OpenAPI schema. Read-only explorer." path="/api">
      <Section title="API Explorer" sub={`Derived from schemas/openapi-genio.json (${paths.length} paths) plus the WebSocket route (not part of OpenAPI by nature). Authentication: API key header or short-lived Bearer where required. This explorer is read-only — no live console.`}>
        <div className="grid gap-3">
          <Card key={ws.path} label={ws.path}>
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="info">WS</Badge>
              <code className="font-mono text-xs text-emerald-200">{ws.path}</code>
            </div>
            <p className="mt-2 text-xs text-white/60">{ws.note}</p>
          </Card>
          {paths.map((p) => (
            <Card key={p} label={p}>
              <div className="flex flex-wrap items-center gap-2">
                {methodsOf(p).map((m) => (
                  <Badge key={m} tone={m === "GET" ? "info" : "warn"}>{m}</Badge>
                ))}
                <code className="font-mono text-xs text-emerald-200">{p}</code>
              </div>
              <Accordion title="Details">
                <p className="font-mono text-[11px] text-white/60">
                  {(spec.paths[p] ? Object.values(spec.paths[p])[0] as { summary?: string } : {}).summary || "See OpenAPI schema"}
                </p>
                <p className="mt-2 text-xs">Auth: endpoint-dependent (see docs/API.md). Errors: standard HTTP + sanitized JSON.</p>
              </Accordion>
            </Card>
          ))}
        </div>
      </Section>
    </PortalLayout>
  );
}
