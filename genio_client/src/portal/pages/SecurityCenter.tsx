import { PortalLayout } from "../PortalLayout";
import { Accordion, Card, Section, StatusBadge } from "../ui";
import { t, useLang, type Lang } from "../../lib/lang";

type Level = "ok" | "warn" | "error" | "info";
type ItemId = "sandbox" | "policy" | "filesystem" | "bash" | "ssrf" | "upload" | "auth" | "killswitch" | "telemetry" | "ipc" | "container" | "release" | "cloud" | "voice" | "admin" | "edge";
const ITEMS: { id: ItemId; level: Level; tagKey: string; proof: string }[] = [
  { id: "sandbox", level: "ok", tagKey: "security.tag_verified", proof: "tests/test_sandbox_security.py" },
  { id: "policy", level: "ok", tagKey: "security.tag_verified", proof: "tests/test_policy_engine.py" },
  { id: "filesystem", level: "ok", tagKey: "security.tag_verified", proof: "tests/test_filesystem_security.py" },
  { id: "bash", level: "ok", tagKey: "security.tag_verified", proof: "tests/test_bash_security.py" },
  { id: "ssrf", level: "ok", tagKey: "security.tag_verified", proof: "tests/test_browser_isolation.py" },
  { id: "upload", level: "ok", tagKey: "security.tag_verified", proof: "tests/test_upload_security.py" },
  { id: "auth", level: "ok", tagKey: "security.tag_verified", proof: "tests/test_api_security.py + test_rc_boot_guard.py" },
  { id: "killswitch", level: "ok", tagKey: "security.tag_verified", proof: "tests/test_kill_switch_hard.py" },
  { id: "telemetry", level: "ok", tagKey: "security.tag_verified", proof: "tests/test_telemetry_pipeline.py" },
  { id: "ipc", level: "ok", tagKey: "security.tag_verified", proof: "tests/test_hitechos_ipc_v1x.py" },
  { id: "container", level: "ok", tagKey: "security.tag_verified", proof: "digest sha256:61d4b42…" },
  { id: "release", level: "ok", tagKey: "security.tag_verified", proof: "installer/tests/test_distribution.py" },
  { id: "cloud", level: "info", tagKey: "security.tag_conditional", proof: "core/model_router.py" },
  { id: "voice", level: "info", tagKey: "security.tag_conditional", proof: "live matrix" },
  { id: "admin", level: "warn", tagKey: "security.tag_pending_gated", proof: "G1 §8" },
  { id: "edge", level: "warn", tagKey: "security.tag_pending", proof: "G0 finding" },
];

function itemText(lang: Lang, id: ItemId): { title: string; body: string } {
  return { title: t(lang, `security.${id}.title`), body: t(lang, `security.${id}.body`) };
}

export default function SecurityCenter() {
  const [lang] = useLang();
  return (
    <PortalLayout title={t(lang, "security.page_title")} description={t(lang, "security.sub")} path="/security">
      <Section title={t(lang, "security.title")} sub={t(lang, "security.sub")}>
        <div className="grid gap-4 md:grid-cols-2">
          {ITEMS.map((it) => {
            const txt = itemText(lang, it.id);
            return (
              <Card key={it.id} label={txt.title}>
                <div className="flex items-center justify-between gap-2">
                  <h3 className="font-bold text-white">{txt.title}</h3>
                  <StatusBadge severity={it.level}>{t(lang, it.tagKey)}</StatusBadge>
                </div>
                <Accordion title={t(lang, "security.details")}>
                  <p>{txt.body}</p>
                  <p className="mt-2 font-mono text-[11px] text-cyan-300">{t(lang, "security.proof")} {it.proof}</p>
                </Accordion>
              </Card>
            );
          })}
        </div>
      </Section>
    </PortalLayout>
  );
}
