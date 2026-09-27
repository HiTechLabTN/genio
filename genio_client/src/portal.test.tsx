/** Portal tests — SSR markup assertions (no new deps: react-dom/server ships with react).
 * Effects don't run server-side, so these prove structure, honesty copy,
 * schema derivation and the admin gate-first render (no stats leak in markup).
 */
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import DownloadCenter from "./portal/pages/DownloadCenter";
import ArchitectureExplorer from "./portal/pages/ArchitectureExplorer";
import SecurityCenter from "./portal/pages/SecurityCenter";
import ApiExplorer from "./portal/pages/ApiExplorer";
import InstallAssistant from "./portal/pages/InstallAssistant";
import { DocsIndex } from "./portal/pages/DocsViewer";
import Admin from "./pages/Admin";
import { INSTALL_STATES } from "./lib/installStates";
import productData from "./product-data.json";
import openapi from "./schemas-openapi.json";

function renderAt(path: string, el: React.ReactNode): string {
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={[path]}>
      <Routes><Route path="*" element={el} /></Routes>
    </MemoryRouter>
  );
}

describe("portal routes resolve", () => {
  it("/download renders real artifacts only", () => {
    const html = renderAt("/download", <DownloadCenter />);
    expect(html).toMatch(/Download Genio/);
    expect(html).toMatch(/NOT AVAILABLE/);
    expect(html).toMatch(/No fake download button/);
    expect(html).toContain("github.com/HiTechLabTN/genio/releases");
    const pd = productData as { artifacts: { archive: string } };
    expect(pd.artifacts.archive).toContain("4.1.0");
  });
  it("/explore shows blocked areas honestly", () => {
    const html = renderAt("/explore", <ArchitectureExplorer />);
    expect(html).toMatch(/BLOCKED/);
    expect(html).toMatch(/CONTRACT READY \/ IMPL PENDING/);
  });
  it("/security separates levels, no vague marketing", () => {
    const html = renderAt("/security", <SecurityCenter />);
    expect(html).toMatch(/PENDING/);
    expect(html).toMatch(/Nothing here means/);
    expect(html).not.toMatch(/military-grade|bank-level|unhackable/i);
  });
  it("/api derives from schema (17 paths)", () => {
    const html = renderAt("/api", <ApiExplorer />);
    const n = Object.keys((openapi as { paths: object }).paths).length;
    expect(n).toBe(17);
    expect(html).toContain("/api/v1/status");
    expect(html).toContain("/ws/agent");
  });
  it("/install is preview-labeled, no fake progress", () => {
    const html = renderAt("/install", <InstallAssistant />);
    expect(html).toMatch(/does not install anything itself/);
    expect(html).not.toMatch(/Downloading\.\.\./);
  });
  it("/docs index lists bundled guides + search", () => {
    const html = renderAt("/docs", <DocsIndex />);
    expect(html).toMatch(/Getting Started/);
    expect(html).toContain('type="search"');
  });
  it("/genio/admin renders gate-first (no stats leak)", () => {
    const html = renderAt("/genio/admin", <Admin />);
    expect(html).toMatch(/Checking authorization/);
    expect(html).not.toMatch(/Top-10 Gestures/);
  });
});

describe("state rendering is deterministic", () => {
  it("all 18 states have severity mapping", () => {
    const html = renderToStaticMarkup(
      <div>
        {(Object.keys(INSTALL_STATES) as (keyof typeof INSTALL_STATES)[]).map((id) => (
          <span key={id} className="g5-status" data-severity={INSTALL_STATES[id].severity}>{id}</span>
        ))}
      </div>
    );
    expect((html.match(/g5-status/g) || []).length).toBe(18);
    expect(html).toContain('data-severity="error"');
  });
});

describe("a11y basics", () => {
  it("portal nav has labels, skip link and main landmark", () => {
    const html = renderAt("/download", <DownloadCenter />);
    expect(html).toContain('aria-label="Genio portal"');
    expect(html).toContain('href="#portal-main"');
    expect(html).toContain('id="portal-main"');
  });
  it("copy buttons are labelled", () => {
    const html = renderAt("/install", <InstallAssistant />);
    expect(html).toContain('aria-label="Copy command to clipboard"');
  });
});

describe("presence contract live in TelemetryBar", () => {
  it("exposes data-presence/data-attention from real props", async () => {
    const { default: TelemetryBar } = await import("./components/TelemetryBar");
    const { renderToStaticMarkup: render } = await import("react-dom/server");
    const React = await import("react");
    const off = render(React.createElement(TelemetryBar, { status: "idle", connected: false }));
    expect(off).toContain('data-presence="disconnected"');
    const on = render(React.createElement(TelemetryBar, { status: "thinking", connected: true }));
    expect(on).toContain('data-presence="thinking"');
  });
});
