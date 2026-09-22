# Motion Memory

## Storage

SQLite `genio_gestures/gestures.db`, table `motion_memory`:

```sql
CREATE TABLE motion_memory (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  context TEXT NOT NULL, emotion TEXT NOT NULL, gesture_name TEXT NOT NULL,
  score REAL DEFAULT 0.5, use_count INTEGER DEFAULT 1,
  last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
```

Only behavioral metadata is stored — never raw conversations, never
message text (§17). Complements (does not duplicate) the on-device
`mascotMemory.ts` per-user gesture library.

## API

- `POST /api/v1/motion/record` `{context, emotion, gesture_name, signal 0..1}`
  → running-average score, `use_count+1`.
- `GET /api/v1/motion/recommend?context=&emotion=` → best gesture by

```text
score = semantic*W0 + history*W1 + context_match*W2 + freshness*W3 + personality*W4
```

weights default `0.4,0.3,0.15,0.1,0.05`, configurable via
`GENIO_MOTION_WEIGHTS` env. Freshness = `exp(-days/30)` decay.

## Client

`MascotController.recommendMotion()` (1500ms timeout, null = use planned)
and `recordMotionOutcome()` (fire-and-forget). Memory is enhancement-only:
every call path has a safe local fallback, offline never blocks.

## Personalization (§19)

Shorter/longer gestures, analytical vs warm repertoires and voice-heavy
listening emerge from per-context scores + `use_count`; core identity
(clip set, style) never changes. No sensitive attributes are inferred.
