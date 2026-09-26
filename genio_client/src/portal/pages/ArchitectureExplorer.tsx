import { PortalLayout } from "../PortalLayout";
import { Accordion, ActionButton, Card, Section, StatusBadge } from "../ui";

/** Factual area cards: purpose, boundary, status. Blocked ones never look ready. */
const AREAS: { id: string; title: string; what: string; boundary: string; status: "ok" | "warn" | "error" | "info"; statusLabel: string; docs: string }[] = [
  { id: "agent", title: "Agent runtime", what: "Multi-step task execution (≤5 iterations, budgets enforced).", boundary: "Every step passes policy; tools are allow-listed.", status: "ok", statusLabel: "PRODUCTION", docs: "/docs#architecture" },
  { id: "policy", title: "Policy engine", what: "Central ALLOW / DENY / ESCALATE gate for every action.", boundary: "Policy lives in Genio; OS and UI can only request.", status: "ok", statusLabel: "PRODUCTION", docs: "/docs#security" },
  { id: "router", title: "Model router", what: "local → Ollama → HiTech-OS → cloud (explicit opt-in).", boundary: "Cloud closed by default; no silent data transfer.", status: "ok", statusLabel: "PRODUCTION", docs: "/docs#models" },
  { id: "memory", title: "Memory", what: "Session recall with audit metadata and poisoning guards.", boundary: "Per-session isolation; provenance tracked.", status: "ok", statusLabel: "PRODUCTION", docs: "/docs#memory" },
  { id: "tools", title: "Tools", what: "Bash (structured), filesystem (bounded), browser, computer-use.", boundary: "Each tool has capability + policy + audit.", status: "ok", statusLabel: "PRODUCTION", docs: "/docs#api" },
  { id: "sandbox", title: "Sandbox", what: "Docker containers, quotas, read-only FS. Fail-closed.", boundary: "Sandbox failure = no host execution, always.", status: "ok", statusLabel: "PRODUCTION", docs: "/docs#sandbox" },
  { id: "ipc", title: "IPC v1.x", what: "UDS contract: hello/capabilities/infer, errors, events.", boundary: "Same-UID auth, nonce, rate-limit, audit.", status: "ok", statusLabel: "PRODUCTION", docs: "/docs#ipc" },
  { id: "installer", title: "Installer", what: "Manifests, backups, repair/update/rollback, doctor.", boundary: "Never deletes user data silently; confirmations required.", status: "ok", statusLabel: "PRODUCTION", docs: "/docs#installation" },
  { id: "docker", title: "Docker", what: "Hardened image: non-root, HEALTHCHECK, pinned deps.", boundary: "No secrets in layers; socket only when sandbox needed.", status: "ok", statusLabel: "PRODUCTION", docs: "/docs#operations" },
  { id: "models", title: "Models", what: "Local Ollama (gemma4:12b resident); honest UNAVAILABLE states.", boundary: "VRAM contention declared; no fake readiness.", status: "info", statusLabel: "CONDITIONAL", docs: "/docs#models" },
  { id: "voice", title: "Voice", what: "STT + VODER TTS (auto language; explicit 422 otherwise).", boundary: "External service; degrades honestly.", status: "info", statusLabel: "CONDITIONAL", docs: "/docs#api" },
  { id: "desktop", title: "Desktop (Tauri)", what: "Native client via HTTP API + WS (contract validated).", boundary: "No secrets embedded; no privileged IPC from UI.", status: "warn", statusLabel: "BLOCKED — no Rust toolchain here", docs: "/docs#hitechos" },
  { id: "mobile", title: "Mobile (Capacitor)", what: "Same API contract; secure storage, TLS, degraded mode.", boundary: "APK signing requires release secrets.", status: "warn", statusLabel: "BLOCKED — signing external", docs: "/docs#hitechos" },
  { id: "hitechos", title: "HiTech-OS", what: "OS consumes Genio over IPC; both stay independent.", boundary: "Contract only; daemon IPC implementation pending OS-side.", status: "warn", statusLabel: "CONTRACT READY / IMPL PENDING", docs: "/docs#hitechos" },
];

export default function ArchitectureExplorer() {
  return (
    <PortalLayout title="Explore" description="How Genio works: agent, policy, tools, sandbox, IPC. Factual statuses only." path="/explore">
      <Section title="How Genio works" sub="Click any area for purpose, boundary and honest status. Blocked areas never look ready.">
        <div className="grid gap-4 md:grid-cols-2">
          {AREAS.map((a) => (
            <Card key={a.id} label={a.title}>
              <div className="flex items-center justify-between gap-2">
                <h3 className="font-bold text-white">{a.title}</h3>
                <StatusBadge severity={a.status}>{a.statusLabel}</StatusBadge>
              </div>
              <Accordion title="Purpose & boundary">
                <p><strong className="text-white">What:</strong> {a.what}</p>
                <p className="mt-2"><strong className="text-white">Boundary:</strong> {a.boundary}</p>
                <p className="mt-2"><a href={a.docs} className="g5-focusable text-cyan-300 hover:text-cyan-200">Documentation →</a></p>
              </Accordion>
            </Card>
          ))}
        </div>
        <div className="mt-6 flex flex-wrap gap-3">
          <ActionButton to="/security">Security Center</ActionButton>
          <ActionButton to="/api">API Explorer</ActionButton>
        </div>
      </Section>
    </PortalLayout>
  );
}
