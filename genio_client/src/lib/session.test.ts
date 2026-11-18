import { describe, expect, it, vi, beforeEach } from "vitest";
import { fetchSession } from "./session";

describe("session (backend-verified, no local token)", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns the verified user from /me", async () => {
    const user = { id: 7, provider: "google", email: "u@x.io" };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        status: 200,
        json: async () => ({ ok: true, user }),
      })),
    );
    await expect(fetchSession()).resolves.toEqual(user);
  });

  it("returns null on 401 (anonymous stays anonymous)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: false, status: 401, json: async () => ({}) })),
    );
    await expect(fetchSession()).resolves.toBeNull();
  });

  it("returns null when the backend is unreachable (offline-safe)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("down");
      }),
    );
    await expect(fetchSession()).resolves.toBeNull();
  });

  it("legacy mock tokens are gone (no mock-google-token factory)", async () => {
    const fs = await import("fs");
    const src = fs.readFileSync(
      new URL("./googleAuth.ts", import.meta.url),
      "utf8",
    );
    expect(src).not.toContain("mock-google-token");
    expect(src).not.toContain("mock-bypass");
  });
});
