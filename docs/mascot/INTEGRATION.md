# Integration

`MascotStage` (default `/app` view) hosts the master:

```tsx
<motion.div animate={physicsDriven}>   {/* Rapier rigid body, invisible canvas */}
  <ErrorBoundary fallback={legacyAvatar}>   {/* v3 → CyberAvatar */}
    <Suspense fallback={legacyAvatar}>
      <MascotScene directive={...} audioLevel voiceEnabled overlay
                   onDebug onReady />
    </Suspense>
  </ErrorBoundary>
  {debugEnabled && <MascotDebugPanel ... />}  {/* ?mascot-debug=1 or localStorage */}
</motion.div>
```

- `directive` comes from `planDirective(intent)` where intent derives from
  `pose.contextKey` + `agentStatus` + mic state; emotion persists in a ref.
- Assistant answers trigger TTS (`ar-TN`) + `recordMotionOutcome()` (positive
  signal = user continued).
- Debug triggers (`wave/listen/think/speak/hero/smile/nod/idle`) override the
  body clip; `reset` clears.
- Technical mode (`← Mode mascotte` / `Mode technique`) is untouched.

## Events (§16)

`deriveEvents(status, prevStatus, chatLen, prevChatLen, listening, speaking)`
produces canonical events; `clipForEvent()` gives the default clip (memory
recommendation may override). TTS timing can be plugged via
`LipSyncDriver.setTimingProvider()`; otherwise audio-level estimation drives
visemes.
