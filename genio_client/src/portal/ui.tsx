import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

/** Minimal portal primitives on --g5-* tokens. No framework, no magic. */

export function Container({ children }: { children: ReactNode }) {
  return <div className="mx-auto w-full max-w-6xl px-4 sm:px-6">{children}</div>;
}

export function Section({ title, sub, children }: { title: string; sub?: string; children: ReactNode }) {
  return (
    <section className="py-8 sm:py-12" aria-label={title}>
      <h2 className="text-xl font-bold text-white sm:text-2xl">{title}</h2>
      {sub && <p className="mt-2 max-w-3xl text-sm text-white/60">{sub}</p>}
      <div className="mt-5">{children}</div>
    </section>
  );
}

export function Card({ children, label }: { children: ReactNode; label?: string }) {
  return (
    <div
      aria-label={label}
      className="min-w-0 rounded-[var(--g5-radius-m)] border border-[var(--g5-border)] bg-[var(--g5-carbon)] p-4 shadow-[var(--g5-elev-1)] sm:p-5"
    >
      {children}
    </div>
  );
}

export function Badge({ tone, children }: { tone: "ok" | "warn" | "error" | "info" | "neutral"; children: ReactNode }) {
  const map: Record<string, string> = {
    ok: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
    warn: "border-amber-400/30 bg-amber-400/10 text-amber-300",
    error: "border-rose-400/30 bg-rose-400/10 text-rose-300",
    info: "border-cyan-400/30 bg-cyan-400/10 text-cyan-300",
    neutral: "border-white/15 bg-white/5 text-white/60",
  };
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 font-mono text-[11px] font-bold ${map[tone]}`}>
      {children}
    </span>
  );
}

export function StatusBadge({ severity, children }: { severity: "ok" | "warn" | "error" | "info"; children: ReactNode }) {
  return (
    <span className="g5-status inline-flex items-center gap-1.5 font-mono text-xs font-bold" data-severity={severity}>
      <span aria-hidden="true">{severity === "ok" ? "●" : severity === "warn" ? "◐" : severity === "error" ? "■" : "○"}</span>
      {children}
    </span>
  );
}

export function ActionButton({ to, href, primary, children }: { to?: string; href?: string; primary?: boolean; children: ReactNode }) {
  const cls = primary
    ? "bg-cyan-400 text-slate-900 hover:bg-cyan-300 shadow-[0_0_16px_rgba(34,211,238,0.4)]"
    : "border border-white/15 bg-white/5 text-white/90 hover:bg-white/10";
  const c = `g5-focusable inline-flex items-center justify-center rounded-full px-6 py-3 text-sm font-bold ${cls}`;
  if (to) {
    return <Link to={to} className={c}>{children}</Link>;
  }
  return <a href={href} className={c} rel={href?.startsWith("http") ? "noopener noreferrer" : undefined}>{children}</a>;
}

export function Accordion({ title, children }: { title: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-[var(--g5-radius-m)] border border-[var(--g5-border)] bg-[var(--g5-carbon)]">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="g5-focusable flex w-full items-center justify-between p-4 text-left text-sm font-bold text-white"
      >
        {title}
        <span aria-hidden="true" className="text-cyan-300">{open ? "−" : "+"}</span>
      </button>
      {open && <div className="border-t border-[var(--g5-border)] p-4 text-sm text-white/70">{children}</div>}
    </div>
  );
}

export function CodeBlock({ code, label }: { code: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="min-w-0 max-w-full overflow-hidden rounded-[var(--g5-radius-m)] border border-[var(--g5-border)] bg-black/40">
      <div className="flex items-center justify-between gap-2 border-b border-[var(--g5-border)] px-3 py-1.5">
        <span className="min-w-0 flex-1 truncate font-mono text-[11px] text-white/50">{label ?? "command"}</span>
        <button
          type="button"
          aria-label="Copy command to clipboard"
          className="g5-focusable min-h-[28px] shrink-0 rounded px-2 font-mono text-[11px] text-cyan-300 hover:text-cyan-200"
          onClick={() => {
            void navigator.clipboard?.writeText(code).then(() => {
              setCopied(true);
              setTimeout(() => setCopied(false), 1500);
            });
          }}
        >
          {copied ? "copied ✓" : "copy"}
        </button>
      </div>
      <pre className="max-w-full overflow-x-auto p-3 font-mono text-xs text-emerald-200"><code>{code}</code></pre>
    </div>
  );
}
