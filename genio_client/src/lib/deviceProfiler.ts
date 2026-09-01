import { useEffect, useState } from "react";

/**
 * Device Hardware Capability Profiler — Phase 1.
 *
 * Inspects RAM, CPU concurrency, WebGL render limits and categorises into:
 *  - Tier A (High Performance - On-Device): RAM >=6GB, cores >=4, WebGL OK
 *  - Tier B (Resource Constrained - Cloud Fallback): otherwise
 *
 * Exposes reactive hook `useDeviceProfile`.
 */

export type DeviceTier = "A" | "B";

export interface DeviceProfile {
  tier: DeviceTier;
  ramGB: number;
  cores: number;
  webglMaxTextureSize: number;
  webglVendor: string | null;
  webglRenderer: string | null;
  isMobile: boolean;
  isLowEnd: boolean;
  reason: string;
  timestamp: number;
}

export interface ProfilerOverrides {
  ramGB?: number;
  cores?: number;
  maxTextureSize?: number;
}

function getRamGB(overrides?: ProfilerOverrides): number {
  if (typeof overrides?.ramGB === "number") return overrides.ramGB;
  // @ts-ignore - deviceMemory is non-standard but present on Android/Chrome
  const dm = (navigator as unknown as { deviceMemory?: number }).deviceMemory;
  if (typeof dm === "number" && !Number.isNaN(dm)) return dm;
  // Heuristic fallback: if we can allocate? assume 4GB on desktop, 2GB on mobile-ish
  return 4;
}

function getCores(overrides?: ProfilerOverrides): number {
  if (typeof overrides?.cores === "number") return overrides.cores;
  const c = navigator.hardwareConcurrency ?? 4;
  return c;
}

function getWebGLInfo(overrides?: ProfilerOverrides): { maxTextureSize: number; vendor: string | null; renderer: string | null } {
  if (typeof overrides?.maxTextureSize === "number") {
    return { maxTextureSize: overrides.maxTextureSize, vendor: null, renderer: null };
  }
  try {
    const canvas = document.createElement("canvas");
    const gl = (canvas.getContext("webgl") || canvas.getContext("experimental-webgl")) as WebGLRenderingContext | null;
    if (!gl) return { maxTextureSize: 0, vendor: null, renderer: null };
    const maxTex = gl.getParameter(gl.MAX_TEXTURE_SIZE) as number;
    const dbg = gl.getExtension("WEBGL_debug_renderer_info");
    let vendor: string | null = null;
    let renderer: string | null = null;
    if (dbg) {
      vendor = gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL) as string;
      renderer = gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) as string;
    }
    return { maxTextureSize: maxTex, vendor, renderer };
  } catch {
    return { maxTextureSize: 0, vendor: null, renderer: null };
  }
}

function isMobileUA(): boolean {
  if (typeof navigator === "undefined") return false;
  return /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent);
}

export function categorizeDevice(profile: Omit<DeviceProfile, "tier" | "reason" | "timestamp"> & { tier?: DeviceTier; timestamp?: number }): DeviceProfile {
  const reasons: string[] = [];
  let tier: DeviceTier = "A";

  // Spec: Tier B if RAM <6GB
  if (profile.ramGB < 6) {
    tier = "B";
    reasons.push(`RAM ${profile.ramGB}GB <6GB`);
  }
  if (profile.cores < 4) {
    tier = "B";
    reasons.push(`cores ${profile.cores} <4`);
  }
  if (profile.webglMaxTextureSize > 0 && profile.webglMaxTextureSize < 4096) {
    tier = "B";
    reasons.push(`WebGL maxTexture ${profile.webglMaxTextureSize} <4096`);
  }
  if (profile.isLowEnd) {
    tier = "B";
    reasons.push("low-end signals");
  }
  // WebGL unavailable is not fatal on desktop but tier B on mobile
  if (profile.webglMaxTextureSize === 0 && profile.isMobile) {
    tier = "B";
    reasons.push("no WebGL on mobile");
  }

  const reason = reasons.length ? reasons.join("; ") : "high-performance: RAM≥6GB, cores≥4, WebGL OK";
  return { ...profile, tier, reason, timestamp: Date.now() } as DeviceProfile;
}

export function getDeviceProfile(overrides?: ProfilerOverrides): DeviceProfile {
  const ramGB = getRamGB(overrides);
  const cores = getCores(overrides);
  const { maxTextureSize, vendor, renderer } = getWebGLInfo(overrides);
  const mobile = isMobileUA();
  // Very coarse low-end detection via hardwareConcurrency=2 and ram=2 edge
  const isLowEnd = ramGB <= 2 && cores <= 4;
  return categorizeDevice({
    ramGB,
    cores,
    webglMaxTextureSize: maxTextureSize,
    webglVendor: vendor,
    webglRenderer: renderer,
    isMobile: mobile,
    isLowEnd,
  });
}

// Reactive hook + singleton exposure

let cached: DeviceProfile | null = null;
const listeners = new Set<(p: DeviceProfile) => void>();

export function refreshProfile(overrides?: ProfilerOverrides): DeviceProfile {
  const p = getDeviceProfile(overrides);
  cached = p;
  listeners.forEach((cb) => cb(p));
  return p;
}

export function useDeviceProfile(overrides?: ProfilerOverrides): DeviceProfile {
  const [profile, setProfile] = useState<DeviceProfile>(() => cached ?? getDeviceProfile(overrides));

  useEffect(() => {
    const init = getDeviceProfile(overrides);
    cached = init;
    setProfile(init);
    const cb = (p: DeviceProfile) => setProfile(p);
    listeners.add(cb);
    // Re-evaluate on visibility change (thermal throttling could be inferred later)
    const onVis = () => {
      if (document.visibilityState === "visible") refreshProfile(overrides);
    };
    document.addEventListener("visibilitychange", onVis);
    return () => {
      listeners.delete(cb);
      document.removeEventListener("visibilitychange", onVis);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return profile;
}

export const DEVICE_TIER_THRESHOLDS = {
  ramGB: 6,
  cores: 4,
  webglTexture: 4096,
};
