import { PortalLayout } from "../PortalLayout";
import { Accordion, Card, Section, StatusBadge } from "../ui";

type Level = "ok" | "warn" | "error" | "info";
const ITEMS: { title: string; level: Level; tag: string; body: string; proof: string }[] = [
  { title: "Fail-closed sandbox", level: "ok", tag: "IMPLEMENTED + VERIFIED", body: "Strict mode without Docker refuses host execution (rc 125, SANDBOX_UNAVAILABLE). Proven live in dev, prefix installs and containers.", proof: "tests/test_sandbox_security.py" },
  { title: "Policy engine", level: "ok", tag: "IMPLEMENTED + VERIFIED", body: "Every action passes a central ALLOW/DENY/ESCALATE gate. Destructive ops need confirmation.", proof: "tests/test_policy_engine.py" },
  { title: "Filesystem boundary", level: "ok", tag: "IMPLEMENTED + VERIFIED", body: "Authorization happens after realpath canonicalization (symlinks, .., /etc, devices blocked).", proof: "tests/test_filesystem_security.py" },
  { title: "Structured Bash", level: "ok", tag: "IMPLEMENTED + VERIFIED", body: "20 command classes validated structurally (injection, substitution, interpreters, fork bombs).", proof: "tests/test_bash_security.py" },
  { title: "Browser anti-SSRF", level: "ok", tag: "IMPLEMENTED + VERIFIED", body: "Private IPs, localhost, metadata endpoints and DNS-rebinding blocked fail-closed.", proof: "tests/test_browser_isolation.py" },
  { title: "Upload validation", level: "ok", tag: "IMPLEMENTED + VERIFIED", body: "Magic bytes (never client MIME), 50MB quota, 1h TTL, 0o600 storage.", proof: "tests/test_upload_security.py" },
  { title: "API authentication", level: "ok", tag: "IMPLEMENTED + VERIFIED", body: "Short-lived Bearer (15min HMAC), rate limits, strict/prod refuses keyless boot.", proof: "tests/test_api_security.py + test_rc_boot_guard.py" },
  { title: "Kill switch", level: "ok", tag: "IMPLEMENTED + VERIFIED", body: "Preemptive halt incl. child processes; re-arm always explicit.", proof: "tests/test_kill_switch_hard.py" },
  { title: "Telemetry scrubbing", level: "ok", tag: "IMPLEMENTED + VERIFIED", body: "Keys, tokens, cookies and secrets scrubbed; telemetry stays useful.", proof: "tests/test_telemetry_pipeline.py" },
  { title: "IPC security", level: "ok", tag: "IMPLEMENTED + VERIFIED", body: "Same-UID auth (localhost is not trusted), nonce anti-replay, rate limit, full audit.", proof: "tests/test_hitechos_ipc_v1x.py" },
  { title: "Container hardening", level: "ok", tag: "IMPLEMENTED + VERIFIED", body: "Non-root user, HEALTHCHECK, pinned deps, no secrets in layers.", proof: "digest sha256:61d4b42…" },
  { title: "Release integrity", level: "ok", tag: "IMPLEMENTED + VERIFIED", body: "Versioned archives + SHA-256 + manifests verified fail-closed (tamper-tested).", proof: "installer/tests/test_distribution.py" },
  { title: "Cloud routing", level: "info", tag: "CONDITIONAL", body: "Cloud backends stay disabled unless GENIO_ALLOW_CLOUD is explicitly set.", proof: "core/model_router.py" },
  { title: "Voice service", level: "info", tag: "CONDITIONAL", body: "External VODER; honest 422/400 errors, no silent 500, no orphans.", proof: "live matrix" },
  { title: "Admin page", level: "warn", tag: "PENDING — gated in 5.0", body: "/genio/admin currently has no auth gate. It must require a user-provided API key verified against the backend before showing internal stats.", proof: "G1 §8" },
  { title: "Production edge", level: "warn", tag: "PENDING", body: "Public traffic currently terminates at dev servers (vite preview + direct uvicorn). CSP/headers audit scheduled.", proof: "G0 finding" },
];

export default function SecurityCenter() {
  return (
    <PortalLayout title="Security" description="What Genio can and cannot do: sandbox, policy, auth, IPC, releases. No vague claims." path="/security">
      <Section title="Security Center" sub="Every claim links to a test, audit or implementation. Nothing here means “100% secure”.">
        <div className="grid gap-4 md:grid-cols-2">
          {ITEMS.map((it) => (
            <Card key={it.title} label={it.title}>
              <div className="flex items-center justify-between gap-2">
                <h3 className="font-bold text-white">{it.title}</h3>
                <StatusBadge severity={it.level}>{it.tag}</StatusBadge>
              </div>
              <Accordion title="Details & proof">
                <p>{it.body}</p>
                <p className="mt-2 font-mono text-[11px] text-cyan-300">Proof: {it.proof}</p>
              </Accordion>
            </Card>
          ))}
        </div>
      </Section>
    </PortalLayout>
  );
}
