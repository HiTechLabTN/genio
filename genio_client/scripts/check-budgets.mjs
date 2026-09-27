/** Bundle budget gate: node scripts/check-budgets.mjs [--dist <dir>] */
import { readdirSync, statSync, existsSync, readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const budgets = JSON.parse(readFileSync(join(ROOT, "budgets.json"), "utf8"));
const idx = process.argv.indexOf("--dist");
const DIST = idx > 0 ? process.argv[idx + 1] : join(ROOT, "dist");

function bytesOf(dir, ext) {
  let total = 0;
  for (const f of readdirSync(dir, { withFileTypes: true, recursive: true })) {
    if (f.isFile() && (!ext || f.name.endsWith(ext))) {
      total += statSync(join(f.parentPath ?? f.path, f.name)).size;
    }
  }
  return total;
}

function dirBytes(dir) {
  let total = 0;
  const walk = (d) => {
    for (const e of readdirSync(d, { withFileTypes: true })) {
      const p = join(d, e.name);
      if (e.isDirectory()) walk(p);
      else total += statSync(p).size;
    }
  };
  walk(dir);
  return total;
}

const failures = [];
const check = (name, actual, max) => {
  const ok = actual <= max;
  console.log(`${ok ? "PASS" : "FAIL"} ${name}: ${actual} <= ${max}`);
  if (!ok) failures.push(`${name} exceeded: ${actual} > ${max} (see budgets.json)`);
};

if (!existsSync(DIST)) { console.error(`dist missing: ${DIST} (run build first)`); process.exit(2); }
const MB = 1024 * 1024;
check("dist_total_mb", +(dirBytes(DIST) / MB).toFixed(1), budgets.dist_total_mb);
check("js_total_mb", +(bytesOf(join(DIST, "assets"), ".js") / MB).toFixed(2), budgets.js_total_mb);
check("css_total_kb", Math.round(bytesOf(join(DIST, "assets"), ".css") / 1024), budgets.css_total_kb);
const assets = join(DIST, "assets");
let worstRoute = 0, worst3d = 0;
const is3d = (f) => /rapier|three|drei|fiber|MascotStage|PostProcessing|maath/i.test(f);
for (const f of readdirSync(assets)) {
  if (!f.endsWith(".js")) continue;
  const kb = statSync(join(assets, f)).size / 1024;
  if (is3d(f)) worst3d = Math.max(worst3d, kb);
  else worstRoute = Math.max(worstRoute, kb);
}
check("route_chunk_kb", Math.round(worstRoute), budgets.route_chunk_kb);
check("app_3d_chunk_kb", Math.round(worst3d), budgets.app_3d_chunk_kb);
if (failures.length) { console.error(failures.join("\n")); process.exit(1); }
console.log("budgets green");
