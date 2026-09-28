# GENIO_PRESENCE_FOUNDATION_CONTRACT (G6-A)

## State → visual meaning (all real, via resolvePresence)

| State | Visual | Motion | Attention |
|---|---|---|---|
| idle/greeting | base/wave image, soft glow | breathe 4s | user |
| listening | wave image, cyan ring | still (calm) | user |
| thinking/planning | base + focus tint | slow pulse | task |
| executing | base + task glow | progress bar (TelemetryBar) | task |
| complete/success | wink image briefly | single nod-equivalent fade | success-result |
| error | base + rose ring, calm | none (still = serious) | question |
| offline/disconnected | base, grey ring + banner | none | system-state |
| reconnecting | base + amber pulse | pulse until ready | system-state |

## Rules

- Never claim `thinking` while idle (resolver-tested).
- Reduced motion: CSS kill-switch + MotionConfig + explicit pref.
- Decorative animation without state meaning: forbidden.
- Future dynamic animation: new validated primitives + tests first.
