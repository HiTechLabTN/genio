import { describe, expect, it } from "vitest";
import { INSTALL_STATES, canTransition } from "./installStates";

describe("installStates mirror", () => {
  it("has all 18 charter states", () => {
    expect(Object.keys(INSTALL_STATES)).toHaveLength(18);
  });
  it("terminal states are closed", () => {
    for (const s of ["complete", "rolled_back", "cancelled"] as const) {
      expect(INSTALL_STATES[s].transitions).toEqual([]);
    }
  });
  it("guards transitions", () => {
    expect(canTransition("idle", "detecting")).toBe(true);
    expect(canTransition("idle", "installing")).toBe(false);
    expect(canTransition("failed", "rolling_back")).toBe(true);
  });
});
