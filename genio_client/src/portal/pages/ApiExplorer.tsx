import { PortalLayout } from "../PortalLayout";
import { Accordion, Badge, Card, Section } from "../ui";
import { t, tt, useLang } from "../../lib/lang";
import openapi from "../../schemas-openapi.json";

type Spec = { paths: Record<string, Record<string, { summary?: string; parameters?: unknown[] }>> };

function methodsOf(path: string): string[] {
  const spec = openapi as unknown as Spec;
  return Object.keys(spec.paths[path] || {}).map((m) => m.toUpperCase());
}

export default function ApiExplorer() {
  const [lang] = useLang();
  const spec = openapi as unknown as Spec;
  const paths = Object.keys(spec.paths || {}).sort();
  const ws = { path: "/ws/agent", methods: ["WS"] };
  return (
    <PortalLayout title={t(lang, "api.page_title")} description={t(lang, "api.sub")} path="/api">
      <Section title={t(lang, "api.title")} sub={tt(lang, "api.sub", { n: String(paths.length) })}>
        <div className="grid gap-3">
          <Card key={ws.path} label={ws.path}>
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="info">WS</Badge>
              <code className="font-mono text-xs text-emerald-200">{ws.path}</code>
            </div>
            <p className="mt-2 text-xs text-white/60">{t(lang, "api.ws_note")}</p>
          </Card>
          {paths.map((p) => (
            <Card key={p} label={p}>
              <div className="flex flex-wrap items-center gap-2">
                {methodsOf(p).map((m) => (
                  <Badge key={m} tone={m === "GET" ? "info" : "warn"}>{m}</Badge>
                ))}
                <code className="font-mono text-xs text-emerald-200">{p}</code>
              </div>
              <Accordion title={t(lang, "api.details")}>
                <p className="font-mono text-[11px] text-white/60">
                  {(spec.paths[p] ? Object.values(spec.paths[p])[0] as { summary?: string } : {}).summary || t(lang, "api.no_summary")}
                </p>
                <p className="mt-2 text-xs">{t(lang, "api.auth_line")}</p>
              </Accordion>
            </Card>
          ))}
        </div>
      </Section>
    </PortalLayout>
  );
}
