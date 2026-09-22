import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
export default function Admin() {
  const [stats, setStats] = useState<any>({});
  const [health, setHealth] = useState<any>({});
  useEffect(() => {
    fetch("http://localhost:8001/health").then(r=>r.json()).then(setHealth).catch(()=> setHealth({status:"offline"}));
    fetch("http://localhost:8001/stats").then(r=>r.json()).then(setStats).catch(()=> setStats({}));
  }, []);
  return (
    <div className="min-h-screen bg-[#020B1E] text-white p-6" dir="ltr">
      <div className="mx-auto max-w-5xl">
        <h1 className="text-2xl font-bold">/genio/admin — Genio Body OS</h1>
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
