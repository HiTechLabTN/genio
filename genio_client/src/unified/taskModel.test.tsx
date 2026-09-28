import { describe, expect, it } from "vitest";
import { renderToStaticMarkup as render } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";import { buildTaskModel, sanitizeToolText } from "./taskModel";
import Mascot from "./Mascot";

describe("task model", () => {
  it("QUEUED when empty, progress UNKNOWN (never fabricated)", () => {
    const t = buildTaskModel({ active: false, result: "", error: null, cancelRequested: false, events: [] });
    expect(t.status).toBe("QUEUED");
    expect(t.progress).toBe("UNKNOWN");
  });
  it("RUNNING with steps from real events", () => {
    const t = buildTaskModel({
      active: true, result: "", error: null, cancelRequested: false,
      events: [{ type: "thought", text: "plan" }, { type: "tool_call", command: "ls" }],
    });
    expect(t.status).toBe("RUNNING");
    expect(t.steps).toHaveLength(2);
    expect(t.tool).toBe("ls");
    expect(t.currentStep).toBeTruthy();
  });
  it("COMPLETED/FAILED from real outcomes", () => {
    expect(buildTaskModel({ active: false, result: "done", error: null, cancelRequested: false, events: [] }).status).toBe("COMPLETED");
    expect(buildTaskModel({ active: false, result: "", error: "boom", cancelRequested: false, events: [] }).status).toBe("FAILED");
  });
  it("cancellation: requested then confirmed by killed event", () => {
    const req = buildTaskModel({ active: true, result: "", error: null, cancelRequested: true, events: [] });
    expect(req.status).toBe("RUNNING");
    expect(req.cancellation).toBe("requested");
    const done = buildTaskModel({ active: false, result: "", error: null, cancelRequested: true, events: [{ type: "killed" }] });
    expect(done.status).toBe("CANCELLED");
    expect(done.cancellation).toBe("confirmed");
  });
});

describe("sanitization", () => {
  it("strips secrets, tokens, home paths", () => {
    expect(sanitizeToolText("key sk-abcdef1234567890 x")).not.toContain("sk-abcdef");
    expect(sanitizeToolText("Bearer abcdef1234567890")).toContain("Bearer [redacted]");
    expect(sanitizeToolText("open /home/azmi/secret.txt")).toContain("~");
    expect(sanitizeToolText("ls -la")).toBe("ls -la");
  });
});

describe("mascot", () => {
  it("renders canonical image with state label, keyboard operable", () => {
    const html = render(
      <MemoryRouter><Mascot presence={{ semanticState: "thinking", intensity: "low" }} engine="THINKING" size={72} /></MemoryRouter>
    );
    expect(html).toContain('aria-label="Genio, thinking (thinking)"');
    expect(html).toContain("genio-hero");
    expect(html).toContain("tabindex=\"0\"");
  });
  it("interaction never changes system state (no handlers beyond attention)", () => {
    const html = render(
      <MemoryRouter><Mascot presence={{ semanticState: "idle", intensity: "low" }} engine="READY" size={56} /></MemoryRouter>
    );
    expect(html).toContain("visual attention only");
  });
});
