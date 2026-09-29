import { PortalLayout } from "../PortalLayout";
import { Accordion, ActionButton, Card, Section, StatusBadge } from "../ui";
import { t, useLang, type Lang } from "../../lib/lang";

/** Factual area cards: purpose, boundary, status. Blocked ones never look ready. */
type AreaId = "agent" | "policy" | "router" | "memory" | "tools" | "sandbox" | "ipc" | "installer" | "docker" | "models" | "voice" | "desktop" | "mobile" | "hitechos";
const AREAS: { id: AreaId; title: string; status: "ok" | "warn" | "error" | "info"; statusKey: string; docs: string }[] = [
  { id: "agent", title: "Agent runtime", status: "ok", statusKey: "explore.status_production", docs: "/docs/architecture" },
  { id: "policy", title: "Policy engine", status: "ok", statusKey: "explore.status_production", docs: "/docs/security" },
  { id: "router", title: "Model router", status: "ok", statusKey: "explore.status_production", docs: "/docs/models" },
  { id: "memory", title: "Memory", status: "ok", statusKey: "explore.status_production", docs: "/docs/memory" },
  { id: "tools", title: "Tools", status: "ok", statusKey: "explore.status_production", docs: "/docs/api" },
  { id: "sandbox", title: "Sandbox", status: "ok", statusKey: "explore.status_production", docs: "/docs/sandbox" },
  { id: "ipc", title: "IPC v1.x", status: "ok", statusKey: "explore.status_production", docs: "/docs/ipc" },
  { id: "installer", title: "Installer", status: "ok", statusKey: "explore.status_production", docs: "/docs/installation" },
  { id: "docker", title: "Docker", status: "ok", statusKey: "explore.status_production", docs: "/docs/operations" },
  { id: "models", title: "Models", status: "info", statusKey: "explore.status_conditional", docs: "/docs/models" },
  { id: "voice", title: "Voice", status: "info", statusKey: "explore.status_conditional", docs: "/docs/api" },
  { id: "desktop", title: "Desktop (Tauri)", status: "warn", statusKey: "explore.status_desktop", docs: "/docs/hitechos" },
  { id: "mobile", title: "Mobile (Capacitor)", status: "warn", statusKey: "explore.status_mobile", docs: "/docs/hitechos" },
  { id: "hitechos", title: "HiTech-OS", status: "warn", statusKey: "explore.status_hitechos", docs: "/docs/hitechos" },
];

export default function ArchitectureExplorer() {
  const [lang] = useLang();
  const txt = (lang_: Lang, id: AreaId): { what: string; boundary: string } => ({
    what: t(lang_, `explore.${id}.what`),
    boundary: t(lang_, `explore.${id}.boundary`),
  });
  return (
    <PortalLayout title={t(lang, "explore.page_title")} description={t(lang, "explore.sub")} path="/explore">
      <Section title={t(lang, "explore.title")} sub={t(lang, "explore.sub")}>
        <div className="grid gap-4 md:grid-cols-2">
          {AREAS.map((a) => {
            const w = txt(lang, a.id);
            return (
              <Card key={a.id} label={a.title}>
                <div className="flex items-center justify-between gap-2">
                  <h3 className="font-bold text-white">{a.title}</h3>
                  <StatusBadge severity={a.status}>{t(lang, a.statusKey)}</StatusBadge>
                </div>
                <Accordion title={t(lang, "explore.purpose")}>
                  <p><strong className="text-white">{t(lang, "explore.what")}</strong> {w.what}</p>
                  <p className="mt-2"><strong className="text-white">{t(lang, "explore.boundary")}</strong> {w.boundary}</p>
                  <p className="mt-2"><a href={a.docs} className="g5-focusable text-cyan-300 hover:text-cyan-200">{t(lang, "explore.docs")}</a></p>
                </Accordion>
              </Card>
            );
          })}
        </div>
        <div className="mt-6 flex flex-wrap gap-3">
          <ActionButton to="/security">{t(lang, "explore.go_security")}</ActionButton>
          <ActionButton to="/api">{t(lang, "explore.go_api")}</ActionButton>
        </div>
      </Section>
    </PortalLayout>
  );
}
