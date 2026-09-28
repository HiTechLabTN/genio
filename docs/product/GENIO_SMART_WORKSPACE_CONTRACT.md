# GENIO_SMART_WORKSPACE_CONTRACT (foundation, G6-A)

## Zones (UnifiedShell, implemented)

Presence (header: avatar + L1/L2 status) · Conversation (chat list,
existing) · Current Task (steps/tool/duration/cancel) · Tool Activity
(last tool line) · Result (last answer) · System Status (resources,
honest Unavailable).

## Responsive model

Desktop: status row + 2-col panels + opt-in details + settings.
Mobile (≤640px): single column, compact presence (56px), panels
stack, code blocks scroll internally, no overflow (tested 360–412).
Tablet: same single column until lg breakpoint.

## Density

simple (default) / detailed / advanced radio, persisted
(`genio-experience-prefs-v1`), no reload. EventStream visible when
detailed or advanced.

## Future gaps (declared, not implemented)

Full drag/resize panels · saved layouts · multi-task tabs · command
palette. None promised in UI.
