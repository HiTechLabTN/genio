/**
 * Experience preferences — local only, no account (§7, §23).
 * Safe values only (validated on load, invalid → defaults).
 */
export type AnimationMode = "on" | "reduced" | "off";
export type MascotSize = "compact" | "standard" | "large";
export type Density = "simple" | "detailed" | "advanced";

export interface ExperiencePrefs {
  animation: AnimationMode;
  mascotSize: MascotSize;
  density: Density;
  ambient: boolean;
}

export const DEFAULT_PREFS: ExperiencePrefs = {
  animation: "on",
  mascotSize: "standard",
  density: "simple",
  ambient: true,
};

const KEY = "genio-experience-prefs-v1";

function valid(p: unknown): p is ExperiencePrefs {
  if (!p || typeof p !== "object") return false;
  const o = p as Record<string, unknown>;
  return (
    ["on", "reduced", "off"].includes(o.animation as string) &&
    ["compact", "standard", "large"].includes(o.mascotSize as string) &&
    ["simple", "detailed", "advanced"].includes(o.density as string) &&
    typeof o.ambient === "boolean"
  );
}

export function loadPrefs(): ExperiencePrefs {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return { ...DEFAULT_PREFS };
    const parsed: unknown = JSON.parse(raw);
    return valid(parsed) ? parsed : { ...DEFAULT_PREFS };
  } catch {
    return { ...DEFAULT_PREFS };
  }
}

export function savePrefs(prefs: ExperiencePrefs): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(prefs));
  } catch {
    /* storage unavailable: preferences simply don't persist */
  }
}

/** Effective motion: explicit off/reduced wins; otherwise honor OS setting. */
export function effectiveMotion(prefs: ExperiencePrefs, osReduced: boolean): AnimationMode {
  if (prefs.animation !== "on") return prefs.animation;
  return osReduced ? "reduced" : "on";
}
