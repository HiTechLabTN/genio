import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { Container } from "./ui";
import productData from "../product-data.json";

/** Per-route SEO: title + description + canonical (no secrets, no infra). */
export function usePageMeta(title: string, description: string, path: string) {
  useEffect(() => {
    document.title = `${title} — Genio`;
    let desc = document.head.querySelector('meta[name="description"]') as HTMLMetaElement | null;
    if (!desc) {
      desc = document.createElement("meta");
      desc.setAttribute("name", "description");
      document.head.appendChild(desc);
    }
    desc.setAttribute("content", description);
    let canon = document.head.querySelector('link[rel="canonical"]') as HTMLLinkElement | null;
    if (!canon) {
      canon = document.createElement("link");
      canon.setAttribute("rel", "canonical");
      document.head.appendChild(canon);
    }
    canon.setAttribute("href", `https://genio.hitech.tn${path}`);
  }, [title, description, path]);
}

const LINKS = [
  { to: "/", label: "Genio", end: true },
  { to: "/explore", label: "Explore" },
  { to: "/security", label: "Security" },
  { to: "/docs", label: "Docs" },
  { to: "/download", label: "Download" },
  { to: "/install", label: "Install" },
  { to: "/app", label: "App" },
];

function Nav() {
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  useEffect(() => setOpen(false), [loc.pathname]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open ]);
  const cls = ({ isActive }: { isActive: boolean }) =>
    `g5-focusable rounded-full px-3 py-1.5 text-[13px] ${isActive ? "text-white font-bold" : "text-white/70 hover:text-white"}`;
  return (
    <header className="sticky top-0 z-40 border-b border-[var(--g5-border)] bg-[#020B1E]/85 backdrop-blur">
      <Container>
        <nav aria-label="Genio portal" className="flex h-14 items-center justify-between">
          <Link to="/" className="g5-focusable text-sm font-bold text-white" aria-label="Genio home">
            🇹🇳 Genio <span className="font-mono text-[10px] text-cyan-300">v{(productData as { version: string }).version}</span>
          </Link>
          <div className="hidden items-center gap-1 md:flex">
            {LINKS.map((l) => (
              <NavLink key={l.to} to={l.to} end={l.end} className={cls}>{l.label}</NavLink>
            ))}
          </div>
          <button
            type="button"
            className="g5-focusable rounded-full border border-white/15 px-3 py-1.5 text-[13px] text-white md:hidden"
            aria-expanded={open}
            aria-controls="portal-menu"
            aria-label="Open navigation menu"
            onClick={() => setOpen((v) => !v)}
          >
            ☰
          </button>
        </nav>
      </Container>
      {open && (
        <div id="portal-menu" role="dialog" aria-modal="true" aria-label="Navigation" className="border-t border-[var(--g5-border)] bg-[#020B1E] md:hidden">
          <Container>
            <div className="flex flex-col gap-1 py-3">
              {LINKS.map((l) => (
                <NavLink key={l.to} to={l.to} end={l.end} className={cls}>{l.label}</NavLink>
              ))}
            </div>
          </Container>
        </div>
      )}
    </header>
  );
}

export function PortalLayout({ title, description, path, children }: { title: string; description: string; path: string; children: ReactNode }) {
  usePageMeta(title, description, path);
  return (
    <div className="min-h-screen bg-[#020B1E] text-slate-200">
      <a href="#portal-main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-cyan-400 focus:px-3 focus:py-1 focus:text-slate-900">
        Skip to content
      </a>
      <Nav />
      <main id="portal-main">
        <Container>{children}</Container>
      </main>
      <footer className="mt-12 border-t border-[var(--g5-border)] py-6">
        <Container>
          <nav aria-label="Footer" className="flex flex-wrap gap-x-5 gap-y-2 text-xs text-white/50">
            <Link to="/docs" className="g5-focusable hover:text-white">Docs</Link>
            <Link to="/security" className="g5-focusable hover:text-white">Security</Link>
            <Link to="/api" className="g5-focusable hover:text-white">API</Link>
            <a href="https://github.com/HiTechLabTN/genio" className="g5-focusable hover:text-white" rel="noopener noreferrer">GitHub</a>
            <span className="font-mono">v{(productData as { version: string }).version} · sovereign · HiTechLab 🇹🇳</span>
          </nav>
        </Container>
      </footer>
    </div>
  );
}
