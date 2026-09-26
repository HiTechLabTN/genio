import { useEffect, useMemo, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { PortalLayout } from "../PortalLayout";
import { Card, Section } from "../ui";
import docIndexJson from "../docs-content/index.json";

type DocIndex = { slug: string; title: string; source: string }[];

const modules = import.meta.glob("../docs-content/*.md", { query: "?raw", import: "default", eager: true }) as Record<string, string>;

function getIndex(): DocIndex {
  return docIndexJson as DocIndex;
}

function renderMarkdown(md: string): string {
  // Minimal safe renderer: headings, code fences, bold, links, lists.
  // No raw HTML passthrough (XSS-safe by construction).
  const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const lines = md.split("\n");
  let html = "";
  let inCode = false;
  let inList = false;
  for (const line of lines) {
    if (line.trim().startsWith("```")) {
      html += inCode ? "</code></pre>" : '<pre class="overflow-x-auto rounded bg-black/40 p-3 font-mono text-xs text-emerald-200"><code>';
      inCode = !inCode;
      continue;
    }
    if (inCode) { html += esc(line) + "\n"; continue; }
    const h = line.match(/^(#{1,4})\s+(.*)/);
    if (h) {
      if (inList) { html += "</ul>"; inList = false; }
      const lvl = h[1].length + 1;
      html += `<h${lvl} class="mt-4 font-bold text-white">${esc(h[2])}</h${lvl}>`;
      continue;
    }
    if (/^(\-|\*|\d+\.)\s+/.test(line)) {
      if (!inList) { html += '<ul class="list-disc pl-5 text-sm text-white/75">'; inList = true; }
      html += `<li>${esc(line.replace(/^(\-|\*|\d+\.)\s+/, ""))}</li>`;
      continue;
    }
    if (inList) { html += "</ul>"; inList = false; }
    if (!line.trim()) continue;
    let p = esc(line)
      .replace(/\*\*([^*]+)\*\*/g, "<strong class=\"text-white\">$1</strong>")
      .replace(/`([^`]+)`/g, "<code class=\"rounded bg-white/10 px-1 font-mono text-[12px] text-cyan-200\">$1</code>");
    p = p.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, t, u) =>
      String(u).startsWith("http") || String(u).startsWith("#") || String(u).startsWith("/")
        ? `<a href="${u}" class="text-cyan-300 hover:text-cyan-200" rel="noopener noreferrer">${t}</a>`
        : t);
    html += `<p class="mt-2 text-sm text-white/75">${p}</p>`;
  }
  if (inList) html += "</ul>";
  if (inCode) html += "</code></pre>";
  return html;
}

export function DocsIndex() {
  const index = useMemo(getIndex, []);
  const [q, setQ] = useState("");
  const filtered = index.filter((d) => (d.title + d.slug).toLowerCase().includes(q.toLowerCase()));
  return (
    <PortalLayout title="Docs" description="Genio documentation: install, use, recover. Tested with Genio 4.1.0." path="/docs">
      <Section title="Documentation" sub="Curated from docs/ at build time. Tested with Genio 4.1.0.">
        <label htmlFor="docs-search" className="sr-only">Search documentation</label>
        <input
          id="docs-search"
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search docs…"
          className="g5-focusable w-full max-w-md rounded-full border border-white/15 bg-white/5 px-4 py-2 text-sm text-white placeholder:text-white/40"
        />
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {filtered.map((d) => (
            <Card key={d.slug} label={d.title}>
              <Link to={`/docs/${d.slug}`} className="g5-focusable text-sm font-bold text-white hover:text-cyan-200">{d.title}</Link>
              <p className="mt-1 font-mono text-[11px] text-white/40">source: {d.source}</p>
            </Card>
          ))}
        </div>
        {filtered.length === 0 && <p role="alert" className="mt-4 text-sm text-white/60">No documentation matches.</p>}
      </Section>
    </PortalLayout>
  );
}

export function DocPage() {
  const { slug } = useParams();
  const [body, setBody] = useState<string | null>(null);
  useEffect(() => {
    const key = `../docs-content/${slug}.md`;
    setBody(typeof modules[key] === "string" ? (modules[key] as string) : null);
  }, [slug]);
  const index = useMemo(getIndex, []);
  const meta = index.find((d) => d.slug === slug);
  return (
    <PortalLayout title={meta?.title ?? "Docs"} description="Genio documentation page." path={`/docs/${slug ?? ""}`}>
      <nav aria-label="Breadcrumb" className="pt-6 text-xs text-white/50">
        <Link to="/docs" className="g5-focusable hover:text-white">Docs</Link>
        <span aria-hidden="true"> / </span>
        <span aria-current="page">{meta?.title ?? slug}</span>
      </nav>
      <section aria-label={meta?.title ?? "document"} className="py-4">
        {body === null ? (
          <p role="alert" className="text-sm text-white/60">Document not found.</p>
        ) : (
          <>
            <p className="font-mono text-[11px] text-white/40">tested with Genio 4.1.0 · source: {meta?.source}</p>
            <div dangerouslySetInnerHTML={{ __html: renderMarkdown(body) }} />
          </>
        )}
      </section>
    </PortalLayout>
  );
}
