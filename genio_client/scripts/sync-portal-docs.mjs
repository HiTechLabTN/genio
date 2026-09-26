/**
 * Sync curated docs into the portal (build-time, explicit list, fail closed).
 * Usage: node scripts/sync-portal-docs.mjs [--check]
 * Source of truth stays in docs/ — this only copies.
 */
import { readFileSync, writeFileSync, existsSync, mkdirSync, readdirSync, rmSync } from "node:fs";
import { join, dirname, basename } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const OUT = join(ROOT, "genio_client", "src", "portal", "docs-content");

const DOCS = [
  ["docs/install/INSTALLATION.md", "getting-started", "Getting Started"],
  ["docs/install/PRODUCTION_INSTALLATION.md", "installation", "Installation"],
  ["docs/install/RECOVERY.md", "recovery", "Recovery"],
  ["docs/install/TROUBLESHOOTING.md", "troubleshooting", "Troubleshooting"],
  ["docs/install/UPGRADE_AND_ROLLBACK.md", "updates", "Updates & Rollback"],
  ["docs/ARCHITECTURE.md", "architecture", "Architecture"],
  ["docs/SECURITY.md", "security", "Security"],
  ["docs/SANDBOX.md", "sandbox", "Sandbox"],
  ["docs/MEMORY.md", "memory", "Memory"],
  ["docs/MODEL_ROUTING.md", "models", "Model routing"],
  ["docs/API.md", "api", "API"],
  ["docs/ipc/IPC_V1.md", "ipc", "IPC v1.x"],
  ["docs/integration/HITECH_OS_INTEGRATION.md", "hitechos", "HiTech-OS"],
  ["docs/integration/CAPABILITIES.md", "capabilities", "Capabilities"],
  ["docs/operations/OPERATIONS.md", "operations", "Operations"],
  ["docs/release/RELEASE_NOTES_4.1.0.md", "changelog", "Changelog"],
  ["docs/releases/GENIO_5_MIGRATION.md", "migration", "Migration"],
  ["docs/security/SECURITY_BOUNDARY.md", "boundary", "Security boundary"],
];

const check = process.argv.includes("--check");
const have = existsSync(OUT) ? new Set(readdirSync(OUT)) : new Set();
let changed = false;
if (!check) {
  mkdirSync(OUT, { recursive: true });
  for (const f of have) {
    if (!DOCS.some(([, slug]) => `${slug}.md` === f) && f !== "index.json") {
      rmSync(join(OUT, f));
      changed = true;
    }
  }
}
const index = [];
for (const [src, slug, title] of DOCS) {
  const from = join(ROOT, src);
  if (!existsSync(from)) throw new Error(`docs source missing: ${src}`);
  const body = readFileSync(from, "utf8");
  index.push({ slug, title, source: src });
  const dest = join(OUT, `${slug}.md`);
  if (check) {
    if (!existsSync(dest) || readFileSync(dest, "utf8") !== body) {
      console.error(`docs drift: ${slug}`);
      process.exit(1);
    }
  } else if (!existsSync(dest) || readFileSync(dest, "utf8") !== body) {
    writeFileSync(dest, body);
    changed = true;
  }
}
const idxJson = JSON.stringify(index, null, 2) + "\n";
if (check) {
  const cur = existsSync(join(OUT, "index.json")) ? readFileSync(join(OUT, "index.json"), "utf8") : null;
  if (cur !== idxJson) { console.error("docs index drift"); process.exit(1); }
  console.log(`portal docs fresh (${DOCS.length} files)`);
} else {
  writeFileSync(join(OUT, "index.json"), idxJson);
  console.log(`synced ${DOCS.length} docs${changed ? "" : " (no changes)"}`);
}
