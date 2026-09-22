/**
 * mascotMemory — persists, per user, which gesture/expression variations the
 * mascot has produced and how they landed, so future sessions can favor the
 * variations that already "worked" instead of re-rolling from scratch every
 * time. Local-first (localStorage) so it works fully offline; the shape is
 * deliberately server-sync-ready (see `exportForSync`/`importFromSync`) for
 * a future genio_server endpoint that would sync this across a user's
 * devices — not implemented server-side yet, see the handoff prompt.
 */

export interface GestureRecord {
  /** Which trigger context this gesture belongs to, e.g. "greeting", "thinking", "success", "idle-fidget" */
  context: string;
  /** A stable id for this specific variation within the context (procedural params, not a file) */
  variantId: string;
  /** Procedural parameters that reproduce this exact variation (joint targets, timing, amplitude…) */
  params: Record<string, number>;
  /** How many times it has actually played */
  useCount: number;
  /** Lightweight signal of whether it "landed" — currently: did the user keep interacting right after (not dismiss/interrupt) */
  positiveCount: number;
  lastUsedAt: number;
  createdAt: number;
}

interface MascotMemoryStore {
  userId: string;
  version: 1;
  gestures: GestureRecord[];
}

const STORAGE_KEY = "genio.mascotMemory.v1";
const USER_ID_KEY = "genio.userId";
const MAX_RECORDS_PER_CONTEXT = 24; // keep the library from growing unbounded

function getOrCreateUserId(): string {
  try {
    let id = localStorage.getItem(USER_ID_KEY);
    if (!id) {
      id = `local-${crypto.randomUUID?.() ?? Date.now().toString(36) + Math.random().toString(36).slice(2)}`;
      localStorage.setItem(USER_ID_KEY, id);
    }
    return id;
  } catch {
    return "anonymous";
  }
}

function loadStore(): MascotMemoryStore {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as MascotMemoryStore;
      if (parsed && parsed.version === 1 && Array.isArray(parsed.gestures)) return parsed;
    }
  } catch {
    /* corrupt or unavailable — start fresh */
  }
  return { userId: getOrCreateUserId(), version: 1, gestures: [] };
}

function saveStore(store: MascotMemoryStore) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
  } catch {
    /* storage full or unavailable — degrade silently, memory just won't persist this session */
  }
}

let cache: MascotMemoryStore | null = null;
function store(): MascotMemoryStore {
  if (!cache) cache = loadStore();
  return cache;
}

/** Record that a newly-generated gesture variation was played. */
export function recordGesture(context: string, variantId: string, params: Record<string, number>) {
  const s = store();
  const existing = s.gestures.find(g => g.context === context && g.variantId === variantId);
  const now = Date.now();
  if (existing) {
    existing.useCount += 1;
    existing.lastUsedAt = now;
  } else {
    s.gestures.push({ context, variantId, params, useCount: 1, positiveCount: 0, lastUsedAt: now, createdAt: now });
    // prune oldest-least-used entries for this context if over the cap
    const forContext = s.gestures.filter(g => g.context === context);
    if (forContext.length > MAX_RECORDS_PER_CONTEXT) {
      const sorted = [...forContext].sort((a, b) => (a.useCount + a.positiveCount) - (b.useCount + b.positiveCount));
      const toDrop = new Set(sorted.slice(0, forContext.length - MAX_RECORDS_PER_CONTEXT).map(g => g.variantId));
      s.gestures = s.gestures.filter(g => !(g.context === context && toDrop.has(g.variantId)));
    }
  }
  saveStore(s);
}

/** Mark the most recently used gesture in a context as having "landed" (user kept engaging). */
export function markPositive(context: string, variantId: string) {
  const s = store();
  const g = s.gestures.find(x => x.context === context && x.variantId === variantId);
  if (g) {
    g.positiveCount += 1;
    saveStore(s);
  }
}

/**
 * Pick a variation for this context: mostly favor what has worked before
 * (weighted by useCount+positiveCount), but keep exploring — small chance of
 * trying something the animator hasn't tried yet, so the library keeps growing
 * instead of collapsing onto one fixed animation.
 */
export function pickWeighted(context: string, exploreRate = 0.25): GestureRecord | null {
  const s = store();
  const pool = s.gestures.filter(g => g.context === context);
  if (pool.length === 0) return null;
  if (Math.random() < exploreRate) return null; // signal "generate something new"
  const weights = pool.map(g => 1 + g.useCount + g.positiveCount * 2);
  const total = weights.reduce((a, b) => a + b, 0);
  let r = Math.random() * total;
  for (let i = 0; i < pool.length; i++) {
    r -= weights[i];
    if (r <= 0) return pool[i];
  }
  return pool[pool.length - 1];
}

export function getUserId(): string {
  return store().userId;
}

export function getStats() {
  const s = store();
  const byContext: Record<string, number> = {};
  for (const g of s.gestures) byContext[g.context] = (byContext[g.context] ?? 0) + 1;
  return { userId: s.userId, totalGestures: s.gestures.length, byContext };
}

/** For a future genio_server sync endpoint — not called anywhere yet. */
export function exportForSync(): MascotMemoryStore {
  return store();
}
export function importFromSync(remote: MascotMemoryStore) {
  if (remote?.version === 1 && Array.isArray(remote.gestures)) {
    cache = remote;
    saveStore(remote);
  }
}
