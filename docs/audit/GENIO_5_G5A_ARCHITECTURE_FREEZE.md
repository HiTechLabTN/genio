# GENIO_5_G5A_ARCHITECTURE_FREEZE

## 1. Unchanged

Agent runtime/budgets · policy · sandbox · auth · IPC v1.x · installer
CLI behavior · API 14+WS · CI gates · 4.1.0 tag · mascot/technique modes.

## 2. Extended

Portal routes · presence (image mapping) · UnifiedShell · installer
events/flags (additive) · schemas · docs · budgets · evidence.

## 3. Refactored

Nothing structural in G5-A (only prior additive work).

## 4. New (frozen for implementation)

Contracts: product/canonical/platform (this gate) · states ·
product-data · presence engine · event protocol · visualizer.

## 5. Deprecated (kept working)

Legacy `genio_executive_core` paths · dead 3D components (wired,
not rendered) · `vite preview` serving (works, edge headers pending).

## 6. Cannot be touched (without migration doc + tests)

Security controls · sandbox behavior · API routes · IPC envelope ·
installer transactional semantics · data preservation · version truths.

## 7. Requires migration

4.x→5.0: none (formats unchanged; portal is additive). Future
breaking change MUST land in GENIO_5_MIGRATION.md first.

## 8. Requires native tooling

Tauri builds (no rustc) · APK/IPA (no dir/SDK-use here; SDK present
but unused) · Rust daemon IPC (OS side).

## 9. Externally blocked

Above + D-Bus control + registry `latest` policy + Android signing
secrets + get.genio.ai domain (GitHub release mechanism used).

## 10. Release gates

5.0 tag ONLY after: contracts frozen (this) → implementation gates →
full matrix green → clean-room on public artifacts → explicit
publication decision. No premature tag.

## Dependency graph

```
portal/unified/presence  -->  hooks (socket/task)  -->  backend API/WS
       |                              |
product-data.json              registries/policy/sandbox
       |                              |
   schemas/                     installer CLI <--> prefix
       |                              |
     docs                     IPC v1.x <--> HiTech-OS (pending)
       |
clients (Tauri/Capacitor, BLOCKED builds, contract-validated)
```
