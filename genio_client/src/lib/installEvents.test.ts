import { describe, expect, it } from "vitest";
import { INSTALL_EVENTS, EVENT_STATES, INSTALL_ERRORS, parseEventLog, severityForState } from "./installEvents";
import { INSTALL_STATES } from "./installStates";

describe("installEvents mirror", () => {
  it("covers all 18 protocol events", () => {
    expect(INSTALL_EVENTS).toHaveLength(18);
  });
  it("every event maps to a real G1 state", () => {
    for (const e of INSTALL_EVENTS) {
      expect(EVENT_STATES[e]).toBeTruthy();
      expect(INSTALL_STATES[EVENT_STATES[e]]).toBeTruthy();
    }
  });
  it("error catalog is complete", () => {
    expect(Object.keys(INSTALL_ERRORS)).toContain("INSTALL_CHECKSUM");
    expect(Object.keys(INSTALL_ERRORS)).toContain("INSTALL_CANCELLED");
    for (const v of Object.values(INSTALL_ERRORS)) expect(v.message).toBeTruthy();
  });
  it("parses real event lines, flags invalid ones", () => {
    const good = JSON.stringify({ protocol: "genio-installer-events/1", event: "INSTALL_STARTED", state: "detecting", data: {} });
    const bad = "{not json";
    const unknown = JSON.stringify({ event: "NOPE", data: {} });
    const out = parseEventLog(`${good}\n${bad}\n${unknown}`);
    expect(out).toHaveLength(3);
    expect(out[0].invalid).toBeUndefined();
    expect(out[0].state).toBe("detecting");
    expect(out[1].invalid).toBe("not JSON");
    expect(out[2].invalid).toMatch(/unknown event/);
  });
  it("renders failure with recovery", () => {
    const line = JSON.stringify({ event: "INSTALL_FAILED", state: "failed", data: {}, error: { code: "INSTALL_CHECKSUM", message: "m", recovery: "Re-download", docs: "/docs" } });
    const [p] = parseEventLog(line);
    expect(p.error?.recovery).toBe("Re-download");
    expect(severityForState(p.state)).toBe("error");
  });
});
