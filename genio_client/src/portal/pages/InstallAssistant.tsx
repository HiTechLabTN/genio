import { useState } from "react";
import { PortalLayout } from "../PortalLayout";
import { Accordion, ActionButton, Card, CodeBlock, Section, StatusBadge } from "../ui";
import { INSTALL_STATES, type InstallStateId, type Severity } from "../../lib/installStates";
import { parseEventLog } from "../../lib/installEvents";
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

export default function InstallAssistant() {
  const plat = platform();
  const [done, setDone] = useState<Record<string, boolean>>({ detecting: true, checking: true });
  const [logText, setLogText] = useState("");
  const [showViz, setShowViz] = useState(false);
  const toggle = (id: string) => setDone((d) => ({ ...d, [id]: !d[id] }));
  const cmd = COMMANDS[plat] ?? COMMANDS.Linux;
  const parsed = showViz ? parseEventLog(logText) : [];
  return (
    <PortalLayout title="Install" description="Install Genio: detected platform, real commands, honest states. Preview mode." path="/install">
      <Section title="Install Genio" sub="Installer Preview / Documentation Mode: this page guides a real installation — it does not install anything itself. Every state below mirrors the real installer state machine.">
        <Card label="detected platform">
          <p className="text-sm text-white/70">Detected platform (client-side only, nothing transmitted): <strong className="text-white">{plat}</strong></p>
          <div className="mt-3"><CodeBlock code={cmd} label={plat === "Docker" ? "docker command" : "install command"} /></div>
        </Card>
        <div className="mt-4 grid gap-3">
          {FLOW.map((id) => {
            const s = INSTALL_STATES[id];
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
                    <StatusBadge severity={sev}>{ok ? "UNDERSTOOD" : "PENDING"}</StatusBadge>
                    <button type="button" onClick={() => toggle(id)} aria-pressed={ok} aria-label={`Mark ${s.label} as ${ok ? "pending" : "understood"}`} className="g5-focusable rounded-full border border-white/15 px-3 py-1 text-xs text-white/80 hover:bg-white/10">
                      {ok ? "reset" : "got it"}
                    </button>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
        <div className="mt-4">
          <Accordion title="Visualize a real installer log (paste --json-events output)">
            <p className="text-xs text-white/60">
              Run <code className="font-mono text-cyan-200">genio install --json-events …</code> in your
              terminal, paste the output below. States render deterministically from real
              events — invalid lines are flagged, never hidden.
            </p>
            <label htmlFor="event-log" className="sr-only">Installer event log</label>
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
              Render timeline
            </button>
            {showViz && (
              <div className="mt-3 grid gap-2" role="log" aria-label="Installer event timeline">
                {parsed.length === 0 && <p className="text-xs text-white/50">Empty log — nothing rendered (honest).</p>}
                {parsed.map((p, i) => (
                  <div key={i} className="rounded-lg border border-[var(--g5-border)] p-2">
                    {p.invalid ? (
                      <p role="alert" className="font-mono text-[11px] text-rose-300">INVALID LINE: {p.invalid}</p>
                    ) : (
                      <>
                        <p className="font-mono text-[11px] text-white">
                          {p.event} → <span className="text-cyan-300">{p.state}</span>
                        </p>
                        {p.error && (
                          <div className="mt-1 text-[11px]">
                            <p className="font-mono text-rose-300">{p.error.code}: {p.error.message}</p>
                            {p.error.recovery && <p className="text-white/70">Recovery: {p.error.recovery}</p>}
                            {p.error.docs && <a href={p.error.docs} className="g5-focusable text-cyan-300">Docs →</a>}
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
          <Accordion title="Verify, recover, get help (real commands)">
            <div className="grid gap-3">
              <CodeBlock code="python3 installer/genio doctor --deep" label="verify" />
              <CodeBlock code="python3 installer/genio repair" label="repair" />
              <CodeBlock code="python3 installer/genio rollback" label="rollback" />
            </div>
          </Accordion>
        </div>
        <div className="mt-6 flex flex-wrap gap-3">
          <ActionButton to="/download">Download center</ActionButton>
          <ActionButton to="/docs">Installation docs</ActionButton>
        </div>
      </Section>
    </PortalLayout>
  );
}
