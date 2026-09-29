import { useState } from "react";
import { PortalLayout } from "../PortalLayout";
import { Accordion, ActionButton, Card, CodeBlock, Section, StatusBadge } from "../ui";
import { INSTALL_STATES, type InstallStateId, type Severity } from "../../lib/installStates";
import { parseEventLog } from "../../lib/installEvents";
import { t, useLang, type Lang } from "../../lib/lang";
import productData from "../../product-data.json";

function platform(): string {
  if (typeof navigator === "undefined") return "unknown";
  const ua = navigator.userAgent.toLowerCase();
  if (/android/.test(ua)) return "Android";
  if (/iphone|ipad/.test(ua)) return "iOS";
  if (/win/.test(ua)) return "Windows";
  if (/mac/.test(ua)) return "macOS";
  if (/linux/.test(ua)) return "Linux";
  return "unknown";
}

const FLOW: InstallStateId[] = ["detecting", "checking", "ready", "downloading", "verifying", "installing", "configuring", "securing", "health_check", "complete"];

const COMMANDS: Record<string, string> = {
  Linux: "curl -fsSL https://raw.githubusercontent.com/HiTechLabTN/genio/main/installer/bootstrap/install.sh | bash",
  Docker: `docker pull ${(productData as { artifacts: { docker: string } }).artifacts.docker}`,
  Server: `curl -fsSL -o genio.tar.gz ${(productData as { artifacts: { archive: string } }).artifacts.archive}`,
};

/**
 * Localized installer-state labels/descriptions.
 * INSTALL_STATES (lib/installStates.ts) is locked by mirror tests and stays
 * English as the technical source of truth; these keys are the user-facing
 * layer and fall back to it if a translation is ever missing.
 */
function stateText(lang: Lang, id: InstallStateId): { label: string; explanation: string } {
  const fb = INSTALL_STATES[id];
  const l = t(lang, `install.state_${id}_label`);
  const e = t(lang, `install.state_${id}_desc`);
  return {
    label: l === `install.state_${id}_label` ? fb.label : l,
    explanation: e === `install.state_${id}_desc` ? fb.explanation : e,
  };
}

export default function InstallAssistant() {
  const [lang] = useLang();
  const plat = platform();
  const [done, setDone] = useState<Record<string, boolean>>({ detecting: true, checking: true });
  const [logText, setLogText] = useState("");
  const [showViz, setShowViz] = useState(false);
  const toggle = (id: string) => setDone((d) => ({ ...d, [id]: !d[id] }));
  const cmd = COMMANDS[plat] ?? COMMANDS.Linux;
  const parsed = showViz ? parseEventLog(logText) : [];
  return (
    <PortalLayout title={t(lang, "install.page_title")} description={t(lang, "install.sub")} path="/install">
      <Section title={t(lang, "install.title")} sub={t(lang, "install.sub")}>
        <Card label={t(lang, "install.platform_card")}>
          <p className="text-sm text-white/70">{t(lang, "install.platform_line")} <strong className="text-white">{plat}</strong></p>
          <div className="mt-3"><CodeBlock code={cmd} label={plat === "Docker" ? t(lang, "install.cmd_docker") : t(lang, "install.cmd_install")} /></div>
        </Card>
        <div className="mt-4 grid gap-3">
          {FLOW.map((id) => {
            const s = stateText(lang, id);
            const ok = !!done[id];
            const sev: Severity = ok ? "ok" : "info";
            return (
              <Card key={id} label={id}>
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="text-sm font-bold text-white">{s.label}</p>
                    <p className="text-xs text-white/60">{s.explanation}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <StatusBadge severity={sev}>{ok ? t(lang, "install.understood") : t(lang, "install.pending")}</StatusBadge>
                    <button type="button" onClick={() => toggle(id)} aria-pressed={ok} aria-label={ok ? t(lang, "install.mark_pending") : t(lang, "install.mark_understood")} className="g5-focusable rounded-full border border-white/15 px-3 py-1 text-xs text-white/80 hover:bg-white/10">
                      {ok ? t(lang, "install.reset") : t(lang, "install.gotit")}
                    </button>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
        <div className="mt-4">
          <Accordion title={t(lang, "install.viz_title")}>
            <p className="text-xs text-white/60">
              {t(lang, "install.viz_help")}
            </p>
            <label htmlFor="event-log" className="sr-only">{t(lang, "install.viz_log_label")}</label>
            <textarea
              id="event-log"
              rows={6}
              value={logText}
              onChange={(e) => { setLogText(e.target.value); setShowViz(false); }}
              placeholder='{"protocol":"genio-installer-events/1","event":"INSTALL_STARTED",…}'
              className="g5-focusable mt-2 w-full rounded-lg border border-white/15 bg-black/40 p-2 font-mono text-[11px] text-emerald-200"
            />
            <button
              type="button"
              onClick={() => setShowViz(true)}
              className="g5-focusable mt-2 rounded-full border border-white/15 px-4 py-1.5 text-xs text-white hover:bg-white/10"
            >
              {t(lang, "install.viz_render")}
            </button>
            {showViz && (
              <div className="mt-3 grid gap-2" role="log" aria-label={t(lang, "install.viz_timeline")}>
                {parsed.length === 0 && <p className="text-xs text-white/50">{t(lang, "install.viz_empty")}</p>}
                {parsed.map((p, i) => (
                  <div key={i} className="rounded-lg border border-[var(--g5-border)] p-2">
                    {p.invalid ? (
                      <p role="alert" className="font-mono text-[11px] text-rose-300">{t(lang, "install.viz_invalid")} {p.invalid}</p>
                    ) : (
                      <>
                        <p className="font-mono text-[11px] text-white">
                          {p.event} → <span className="text-cyan-300">{p.state}</span>
                        </p>
                        {p.error && (
                          <div className="mt-1 text-[11px]">
                            <p className="font-mono text-rose-300">{p.error.code}: {p.error.message}</p>
                            {p.error.recovery && <p className="text-white/70">{t(lang, "install.viz_recovery")} {p.error.recovery}</p>}
                            {p.error.docs && <a href={p.error.docs} className="g5-focusable text-cyan-300">{t(lang, "install.viz_docs")}</a>}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Accordion>
        </div>
        <div className="mt-4">
          <Accordion title={t(lang, "install.help_title")}>
            <div className="grid gap-3">
              <CodeBlock code="python3 installer/genio doctor --deep" label={t(lang, "install.code_verify")} />
              <CodeBlock code="python3 installer/genio repair" label={t(lang, "install.code_repair")} />
              <CodeBlock code="python3 installer/genio rollback" label={t(lang, "install.code_rollback")} />
            </div>
          </Accordion>
        </div>
        <div className="mt-6 flex flex-wrap gap-3">
          <ActionButton to="/download">{t(lang, "install.go_download")}</ActionButton>
          <ActionButton to="/docs">{t(lang, "install.go_docs")}</ActionButton>
        </div>
      </Section>
    </PortalLayout>
  );
}
