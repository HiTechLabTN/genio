import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

/** Admin gate (G2 §17): no anonymous stats. The operator enters an API
 * key (stored in sessionStorage only, never embedded); it is verified
 * against GET /api/v1/safety (require_key). Stats render only after 200.
 * In dev-open backends an empty key validates — that is the documented
 * dev behavior, and the UI says so honestly. */
const KEY_SLOT = "genio_admin_key";

async function probe(base: string, key: string): Promise<boolean> {
  try {
    const r = await fetch(`${base}/api/v1/safety`, {
      headers: key ? { "X-API-Key": key } : {},
    });
    return r.status === 200;
  } catch {
    return false;
  }
}

function apiBase(): string {
  if (typeof window === "undefined") return "";
  return window.location.origin.includes("localhost") ? "http://localhost:8000" : window.location.origin;
}

export default function Admin() {
  const [stats, setStats] = useState<any>({});
  const [health, setHealth] = useState<any>({});
  const [key, setKey] = useState(() =>
    typeof window === "undefined" ? "" : (sessionStorage.getItem(KEY_SLOT) ?? ""));
  const [draft, setDraft] = useState("");
  const [authorized, setAuthorized] = useState<boolean | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;
    probe(apiBase(), key).then((ok) => {
      if (!live) return;
      setAuthorized(ok);
      if (!ok && key) setError("Key rejected or backend unreachable — still locked.");
    });
    return () => { live = false; };
  }, [key]);

  useEffect(() => {
    if (!authorized) return;
    const h = { ...(key ? { "X-API-Key": key } : {}) };
    fetch(`${apiBase()}/api/v1/system/telemetry`, { headers: h }).then(r=>r.json()).then(setStats).catch(()=> setStats({unavailable: true}));
    fetch("http://localhost:8001/health").then(r=>r.json()).then(setHealth).catch(()=> setHealth({status:"offline (local gestures service)"}));
  }, [authorized, key]);
  if (authorized === null) {
    return (
      <div className="min-h-screen bg-[#020B1E] p-6 text-white" dir="ltr">
        <p role="status" className="font-mono text-xs text-white/60">Checking authorization…</p>
      </div>
    );
  }
  if (!authorized) {
    return (
      <div className="min-h-screen bg-[#020B1E] p-6 text-white" dir="ltr">
        <div className="mx-auto max-w-md">
          <h1 className="text-xl font-bold">Restricted area</h1>
          <p className="mt-2 text-sm text-white/60">
            Internal stats require an operator API key, verified against the
            backend (<code className="font-mono text-[12px]">GET /api/v1/safety</code>).
            The key is kept in this tab only — never embedded, never sent elsewhere.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              sessionStorage.setItem(KEY_SLOT, draft);
              setKey(draft);
              setError("");
            }}
            className="mt-4"
          >
            <label htmlFor="admin-key" className="font-mono text-xs text-white/60">API key</label>
            <input
              id="admin-key"
              type="password"
              autoComplete="off"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="GENIO_API_KEY (empty only on dev-open backends)"
              className="mt-1 w-full rounded-lg border border-white/15 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-white/30"
            />
            <button type="submit" className="mt-3 rounded-full bg-cyan-400 px-5 py-2 text-sm font-bold text-slate-900 hover:bg-cyan-300">
              Unlock
            </button>
          </form>
          {error && <p role="alert" className="mt-2 text-sm text-rose-300">{error}</p>}
          <p className="mt-3 text-xs text-white/40">Wrong key or unreachable backend stays locked — no stats leak.</p>
        </div>
      </div>
    );
  }
  const lock = () => {
    sessionStorage.removeItem(KEY_SLOT);
    setKey("");
    setDraft("");
    setAuthorized(false);
  };
  return (
    <div className="min-h-screen bg-[#020B1E] text-white p-6" dir="ltr">
      <div className="mx-auto max-w-5xl">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">/genio/admin — Genio Body OS</h1>
          <button type="button" onClick={lock} className="rounded-full border border-white/15 px-3 py-1 text-xs text-white/70 hover:bg-white/10">
            Lock
          </button>
        </div>
        <p className="font-mono text-xs text-white/50">Model health • VRAM • Dataset • Top-10 • Cron logs</p>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <div className="rounded-xl border border-white/10 bg-white/5 p-4">
            <p className="font-mono text-xs text-cyan-300">Model Health</p>
            <p className="text-sm">{health.status || "unknown"} — {health.model || "qwen2.5:7b-instruct-q4_K_M"}</p>
            <p className="text-xs text-white/50">VRAM: {health.vram || "12GB"}</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-white/5 p-4">
            <p className="font-mono text-xs text-amber-300">Dataset</p>
            <p className="text-sm">Total {stats.total||0} (Real {stats.real||0} Synthetic {stats.synthetic||0})</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-white/5 p-4">
            <p className="font-mono text-xs text-emerald-300">Cron</p>
            <p className="text-xs">0 1 * * * — window 01:00-06:00</p>
            <a href="/reports/v4/cron.log" className="text-xs text-cyan-300">View logs</a>
          </div>
        </div>
        <div className="mt-6 rounded-xl border border-white/10 bg-white/5 p-4">
          <p className="font-mono text-xs text-white/70">Top-10 Gestures</p>
          <pre className="mt-2 max-h-64 overflow-auto text-xs">{JSON.stringify(stats.top10 || [], null, 2)}</pre>
        </div>
        <div className="mt-4 flex gap-3">
          <Link to="/" className="text-cyan-300 text-sm">Landing</Link>
          <Link to="/app" className="text-cyan-300 text-sm">App</Link>
        </div>
      </div>
    </div>
  );
}
