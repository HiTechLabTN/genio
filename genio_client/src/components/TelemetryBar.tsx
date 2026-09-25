import { useEffect, useRef, useState } from "react";

type Vitals = {
  cpu_percent: number;
  ram_percent: number;
  gpu_percent: number;
  net_up_kbs: number;
  net_down_kbs: number;
};

/**
 * Sovereign Top Telemetry Bar — sticky, compact, elegant.
 * - Status badge: 🟢 متصل / 🟡 يخمّم / 🔵 يجاوب / 🔴 غير متصل
 * - Ping (round-trip ms mesuré sur le poll lui-même), CPU/RAM/GPU %, Net ↑↓.
 * - Barre de progression animée dès qu'une requête est en vol.
 * Source : GET /api/v1/system/telemetry (same-origin → marche en local
 * comme derrière le tunnel). Zéro nom hardware/marque — pourcentages seuls.
 */
export default function TelemetryBar({
  status,
  connected,
}: {
  status: string;
  connected: boolean;
}) {
  const [v, setV] = useState<Vitals | null>(null);
  const [ping, setPing] = useState<number | null>(null);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    let alive = true;
    const poll = async () => {
      const t0 = performance.now();
      // 1) same-origin (production/tunnel : /api/* → :8000 via cloudflared).
      // 2) fallback :8000 même-host (preview locale / LAN dev sans proxy).
      const urls = ["/api/v1/system/telemetry"];
      try {
        const { protocol, hostname } = window.location;
        if (hostname !== "genio.hitech.tn") {
          urls.push(`${protocol}//${hostname}:8000/api/v1/system/telemetry`);
        }
      } catch { /* ignore */ }
      for (const u of urls) {
        try {
          const r = await fetch(u, { cache: "no-store" });
          if (!r.ok) continue;
          const j = (await r.json()) as Vitals;
          if (typeof j.cpu_percent !== "number") continue;
          if (!alive) return;
          setV(j);
          setPing(Math.round(performance.now() - t0));
          return;
        } catch { /* try next */ }
      }
      if (!alive) return;
      setV(null);
      setPing(null);
    };
    void poll();
    timer.current = window.setInterval(poll, 3000);
    return () => {
      alive = false;
      if (timer.current) window.clearInterval(timer.current);
    };
  }, []);

  const busy = status === "thinking" || status === "executing";
  const badge = !connected
    ? { dot: "bg-rose-400", txt: "🔴 غير متصل (Offline)" }
    : status === "thinking"
      ? { dot: "bg-amber-300", txt: "🟡 جينيو يخمّم... (Thinking)" }
      : status === "executing"
        ? { dot: "bg-sky-300", txt: "🔵 يجاوب (Streaming)" }
        : { dot: "bg-emerald-400", txt: "🟢 متصل (Ready)" };

  return (
    <div className="telemetry-bar pointer-events-none absolute inset-x-0 top-0 z-[65]">
      <div className="mx-auto flex w-fit max-w-[96vw] flex-wrap items-center justify-center gap-x-3 gap-y-1 rounded-b-2xl border border-white/10 bg-black/55 px-4 py-1.5 font-mono text-[10px] text-white/80 backdrop-blur-md">
        <span className="flex items-center gap-1.5 font-bold">
          <span className={`h-2 w-2 rounded-full ${badge.dot} ${busy ? "animate-ping" : "shadow-[0_0_8px_rgba(52,211,153,0.8)]"}`} />
          {badge.txt}
        </span>
        <span className="text-white/50">ping {ping === null ? "—" : `${ping}ms`}</span>
        <span>CPU {v === null ? "—" : `${v.cpu_percent}%`}</span>
        <span>RAM {v === null ? "—" : `${v.ram_percent}%`}</span>
        <span>GPU {v === null ? "—" : `${v.gpu_percent}%`}</span>
        <span className="text-white/50">
          Net ↑ {v === null ? "—" : `${v.net_up_kbs} KB/s`} ↓ {v === null ? "—" : `${v.net_down_kbs} KB/s`}
        </span>
      </div>
      {busy ? (
        <div className="h-[2px] w-full overflow-hidden bg-white/5">
          <div className="h-full w-1/3 animate-[telemetry-slide_1.1s_ease-in-out_infinite] bg-gradient-to-r from-transparent via-cyan-300 to-transparent" />
        </div>
      ) : null}
      <style>{`@keyframes telemetry-slide{0%{transform:translateX(-100%)}100%{transform:translateX(300%)}}`}</style>
    </div>
  );
}
