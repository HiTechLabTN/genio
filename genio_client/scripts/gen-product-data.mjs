/**
 * product-data generator — docs-as-contract (§17 charter, G1-C).
 * Reads ONLY authoritative sources, writes genio_client/src/product-data.json:
 *   repo/VERSION, installer/__init__ (INSTALLER_VERSION),
 *   genio_client/package.json, schemas/openapi-genio.json, schemas/ipc-v1.json,
 *   docs/release/RELEASE_NOTES_4.1.0.md, docs/release/KNOWN_LIMITATIONS_4.1.0.md,
 *   docs/ipc + capabilities (static list mirrors capabilities.py probes),
 *   release asset URLs for the current VERSION (GitHub release convention).
 * Fails closed on missing source. `node gen-product-data.mjs --check`
 * exits non-zero on drift (CI freshness gate).
 */
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const OUT = join(ROOT, "genio_client", "src", "product-data.json");

function read(p) {
  const f = join(ROOT, p);
  if (!existsSync(f)) throw new Error(`authoritative source missing: ${p}`);
  return readFileSync(f, "utf8");
}
function json(p) { return JSON.parse(read(p)); }
function section(md, h) {
  const m = md.match(new RegExp(`^#+\\s+${h}\\s*$([\\s\\S]*?)(?=^#+\\s|\\Z)`, "mi"));
  return (m ? m[1] : "").trim().slice(0, 4000);
}

const version = read("VERSION").trim();
const installerSrc = read("installer/__init__.py");
const installerVersion = (installerSrc.match(/INSTALLER_VERSION\s*=\s*"([^"]+)"/) || [])[1];
if (!installerVersion) throw new Error("INSTALLER_VERSION not found");
const clientPkg = json("genio_client/package.json");
const openapi = json("schemas/openapi-genio.json");
const ipc = json("schemas/ipc-v1.json");
const notes = read("docs/release/RELEASE_NOTES_4.1.0.md");
const limits = read("docs/release/KNOWN_LIMITATIONS_4.1.0.md");

const data = {
  generated_from: "authoritative repo sources (see scripts/gen-product-data.mjs)",
  product: "genio",
  version,
  installer_version: installerVersion,
  client_version: clientPkg.version,
  ipc_protocol: "1.0",
  api_routes: Object.keys(openapi.paths || {}).length,
  ipc_error_codes: ipc.definitions.error.properties.error.properties.code.enum,
  ipc_events: ["genio.ready", "genio.degraded", "genio.request", "genio.shutdown"],
  capabilities: ["agent", "planning", "memory", "tools", "sandbox", "browser",
    "computer", "voice", "models", "automation", "filesystem", "hitechos-integration"],
  capabilities_unavailable: ["vision"],
  artifacts: {
    base: `https://github.com/HiTechLabTN/genio/releases/tag/v${version}`,
    archive: `https://github.com/HiTechLabTN/genio/releases/download/v${version}/genio-${version}.tar.gz`,
    checksum: `https://github.com/HiTechLabTN/genio/releases/download/v${version}/genio-${version}.tar.gz.sha256`,
    manifest: `https://github.com/HiTechLabTN/genio/releases/download/v${version}/genio-${version}.release.json`,
    sbom: `https://github.com/HiTechLabTN/genio/releases/download/v${version}/sbom.json`,
    docker: "ghcr.io/hitechlabtn/genio:4.1.0",
  },
  platforms: {
    linux: { status: "supported", arch: ["x86_64", "aarch64"], method: "release archive + installer" },
    docker: { status: "supported", image: "ghcr.io/hitechlabtn/genio:4.1.0" },
    windows: { status: "unavailable", reason: "No signed EXE published for this release" },
    macos: { status: "unavailable", reason: "No signed DMG published for this release" },
    android: { status: "unavailable", reason: "APK requires release signing secrets (external)" },
  },
  release_notes: section(notes, "New") + "\n\n" + section(notes, "Fixed"),
  known_limitations: limits.split("\n").filter((l) => /^\d+\./.test(l)).slice(0, 12),
};

const prev = existsSync(OUT) ? readFileSync(OUT, "utf8") : null;
const next = JSON.stringify(data, null, 2) + "\n";
// Bundle the OpenAPI schema for the read-only API explorer (single truth).
const openapiDest = join(ROOT, "genio_client", "src", "schemas-openapi.json");
const openapiSrc = JSON.stringify(openapi);
if (process.argv.includes("--check")) {
  if (prev !== next) { console.error("product-data.json drifted — regenerate"); process.exit(1); }
  const curOpenapi = existsSync(openapiDest) ? readFileSync(openapiDest, "utf8") : null;
  if (curOpenapi !== openapiSrc) { console.error("schemas-openapi.json drifted — regenerate"); process.exit(1); }
  console.log("product-data.json fresh");
} else {
  writeFileSync(OUT, next);
  writeFileSync(openapiDest, openapiSrc);
  console.log(`wrote ${OUT} (v${version})`);
}
