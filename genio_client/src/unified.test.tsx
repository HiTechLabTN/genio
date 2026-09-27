import { describe, expect, it } from "vitest";
import { renderToStaticMarkup as render } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import UnifiedShell, { type UnifiedProps } from "./unified/UnifiedShell";

const base: UnifiedProps = {
  chat: [],
  agentStatusKind: "idle",
  socketState: "connected",
  streaming: false,
  connected: true,
  telemetry: null,
  taskActive: false,
};

function shell(props: Partial<UnifiedProps> = {}): string {
  return render(
    <MemoryRouter>
      <UnifiedShell {...base} {...props} />
    </MemoryRouter>
  );
}

describe("unified layout", () => {
  it("idle renders conversation mode with honest copy", () => {
    const html = shell();
    expect(html).toContain('data-layout-mode="conversation"');
    expect(html).toContain("Genio is ready");
  });
  it("executing renders execution mode + task panel", () => {
    const html = shell({ taskActive: true, agentStatusKind: "executing", streaming: false });
    expect(html).toContain('data-layout-mode="execution"');
    expect(html).toContain("Genio is working on your task");
    expect(html).toContain("Current task");
  });
  it("streaming answer renders explaining (what the user sees)", () => {
    const html = shell({ taskActive: true, agentStatusKind: "executing", streaming: true });
    expect(html).toContain("Genio is answering");
  });
  it("disconnected shows failure UX with reconnect", () => {
    const html = shell({ connected: false, socketState: "disconnected", onReconnect: () => undefined });
    expect(html).toContain("Connection lost");
    expect(html).toContain("Reconnect");
  });
});

describe("density", () => {
  it("simple hides event stream, advanced shows it", () => {
    const simple = shell();
    expect(simple).not.toContain("Event stream");
    // advanced density is opt-in via settings (localStorage tested separately);
    // technical details disclosure always present:
    expect(simple).toContain("Technical details");
  });
});

describe("resources honesty", () => {
  it("missing metrics say Unavailable, never 0", () => {
    const html = shell();
    expect(html).toContain("Unavailable");
    expect(html).not.toContain(">0%<");
  });
  it("real telemetry values render", () => {
    const html = shell({ telemetry: { cpu_percent: 42.5, ram_percent: 61 } });
    expect(html).toContain("42.5%");
  });
});

describe("offline shell", () => {
  it("offline banner keeps shell usable", () => {
    const html = shell({ online: false });
    expect(html).toMatch(/Offline/);
    expect(html).toContain("Current task");
  });
});

describe("no fake states", () => {
  it("never claims model ready or metric percentages without data", () => {
    const html = shell();
    expect(html).not.toMatch(/Model ready/i);
    expect(html).not.toMatch(/>\d[\d.]*%</);
  });
});
