# Obsidian Sync Server — Task Breakdown

**Status**: Draft v2
**Date**: 2026-04-01

Tasks are organized by phase. Each phase has a clear entry condition. Tasks marked `[P]` can run in parallel within their phase. Tasks reference user scenarios (US1–US14) and functional requirements (FR-001–FR-013).

---

## Phase 1: Project Setup

**Entry**: Empty repo with spec files.
**Exit**: All four projects scaffold, build, and run (empty shells).

| ID | Par | Story | Task | Files |
|----|-----|-------|------|-------|
| 1.1 | [P] | — | Initialize Python server project (pyproject.toml, FastAPI hello world, pytest config) | `server/` |
| 1.2 | [P] | — | Initialize Obsidian plugin project (package.json, manifest.json, esbuild, empty plugin class) | `plugin/` |
| 1.3 | [P] | — | Initialize React portal project (Vite + React + TypeScript scaffold) | `portal/` |
| 1.4 | [P] | — | Initialize CLI client project (pyproject.toml, Typer hello world) | `cli/` |
| 1.5 | [P] | — | Create Docker setup (Dockerfile, docker-compose.yml, Caddyfile, .env.example) | `docker/` |
| 1.6 | | — | Create GitHub Actions CI (lint + test for all four projects) | `.github/workflows/` |
| 1.7 | | — | Configure monorepo tooling (root .gitignore, .editorconfig, pre-commit hooks) | root files |

---

## Phase 2: Foundation

**Entry**: Phase 1 complete — all projects build.
**Exit**: Users can register, login, create vaults (empty), and the storage abstraction works with local backend.

| ID | Par | Story | Task | Files |
|----|-----|-------|------|-------|
| 2.1 | | FR-001 | Set up SQLAlchemy async engine + session factory with SQLite/PostgreSQL toggle | `server/src/obsidian_sync/database.py`, `config.py` |
| 2.2 | | FR-001 | Create User model + Alembic initial migration | `server/src/obsidian_sync/models/user.py`, `alembic/` |
| 2.3 | | FR-001 | Implement auth service (JWT issue/verify, bcrypt password hash, refresh token rotation) | `server/src/obsidian_sync/services/auth.py` |
| 2.4 | | FR-001 | Create auth router (login, refresh, first-run setup) | `server/src/obsidian_sync/routers/auth.py` |
| 2.5 | | FR-001 | Create auth middleware (JWT verification, request user injection) | `server/src/obsidian_sync/middleware/auth.py` |
| 2.6 | | FR-002 | Create Vault, VaultAccess models + migration | `server/src/obsidian_sync/models/vault.py` |
| 2.7 | | FR-003 | Create vault CRUD router (create, list, get, delete) | `server/src/obsidian_sync/routers/vaults.py` |
| 2.8 | | FR-006 | Implement StorageBackend protocol + LocalStorage backend | `server/src/obsidian_sync/storage/` |
| 2.9 | | FR-006 | Implement StorageBackendConfig model + storage factory | `server/src/obsidian_sync/services/storage.py` |
| 2.10 | | FR-001 | Implement API key auth (create, verify, revoke) | `server/src/obsidian_sync/services/auth.py` |
| 2.11 | [P] | FR-001 | Write auth tests (login, refresh, JWT, rate limiting) | `server/tests/test_auth.py` |
| 2.12 | [P] | FR-003 | Write vault CRUD tests | `server/tests/test_vaults.py` |
| 2.13 | [P] | FR-006 | Write storage backend tests (local) | `server/tests/test_storage.py` |
| 2.14 | | US13 | Implement health check endpoint | `server/src/obsidian_sync/routers/health.py` |

---

## Phase 3: Core Sync — On-Save (US1, US2, US4)

**Entry**: Phase 2 complete — auth, vaults, and local storage work.
**Exit**: Plugin and CLI can sync files to server on save, with conflict detection.

| ID | Par | Story | Task | Files |
|----|-----|-------|------|-------|
| 3.1 | | FR-004 | Create FileVersion, SyncOperation models + migration | `server/src/obsidian_sync/models/sync.py` |
| 3.2 | | FR-004 | Implement file upload/download endpoints (PUT/GET /vaults/{id}/files/{path}) | `server/src/obsidian_sync/routers/vaults.py` |
| 3.3 | | FR-004 | Implement sync service (version comparison, conflict detection, operation log) | `server/src/obsidian_sync/services/sync.py` |
| 3.4 | | FR-004 | Implement WebSocket handler (connection manager, auth, message routing) | `server/src/obsidian_sync/websocket/` |
| 3.5 | | FR-004 | Implement WebSocket sync protocol (file_save, file_delete, file_rename, pull) | `server/src/obsidian_sync/websocket/protocol.py` |
| 3.6 | | US1 | Plugin: implement server connection + auth (settings tab, login flow) | `plugin/src/settings.ts`, `plugin/src/sync/client.ts` |
| 3.7 | | US1 | Plugin: implement initial vault upload (full sync on first connect) | `plugin/src/sync/engine.ts` |
| 3.8 | | US2 | Plugin: implement on-save sync (file watcher → WebSocket push) | `plugin/src/sync/engine.ts` |
| 3.9 | | US2 | Plugin: implement change receiver (WebSocket → apply file changes) | `plugin/src/sync/engine.ts` |
| 3.10 | | US4 | Plugin: implement offline queue (IndexedDB, retry on reconnect) | `plugin/src/sync/queue.ts` |
| 3.11 | | US4 | Plugin: implement conflict detection + resolution UI | `plugin/src/sync/conflict.ts`, `plugin/src/ui/conflict-modal.ts` |
| 3.12 | | US2 | Plugin: implement status bar indicator (sync status, connection state) | `plugin/src/ui/status-bar.ts` |
| 3.13 | | US14 | CLI: implement login command (token storage in config dir) | `cli/src/obsidian_sync_cli/commands/auth.py` |
| 3.14 | | US14 | CLI: implement sync/pull/push commands | `cli/src/obsidian_sync_cli/commands/sync.py` |
| 3.15 | | US14 | CLI: implement watch command (file watcher daemon) | `cli/src/obsidian_sync_cli/commands/watch.py` |
| 3.16 | | US14 | CLI: implement status command | `cli/src/obsidian_sync_cli/commands/status.py` |
| 3.17 | [P] | FR-004 | Write sync protocol tests (version conflicts, operations) | `server/tests/test_sync.py` |
| 3.18 | [P] | FR-004 | Write WebSocket handler tests | `server/tests/test_websocket.py` |
| 3.19 | [P] | US14 | Write CLI command tests | `cli/tests/` |

**Checkpoint**: Test full on-save sync cycle: plugin saves file → server stores → another plugin receives update. CLI can pull/push. Conflicts detected and preserved.

---

## Phase 4: ACL & Sharing (US5, US6)

**Entry**: Phase 3 complete — on-save sync works.
**Exit**: Vault sharing with roles works, share links functional.

| ID | Par | Story | Task | Files |
|----|-----|-------|------|-------|
| 4.1 | | FR-002 | Implement vault sharing service (grant, revoke, list, update role) | `server/src/obsidian_sync/services/sharing.py` |
| 4.2 | | FR-002 | Create sharing router (CRUD vault access) | `server/src/obsidian_sync/routers/sharing.py` |
| 4.3 | | FR-002 | Enforce ACL on all sync operations (WebSocket + REST) | `server/src/obsidian_sync/middleware/auth.py` |
| 4.4 | | FR-008 | Create ShareLink model + migration | `server/src/obsidian_sync/models/sharing.py` |
| 4.5 | | FR-008 | Implement share link service (create, verify, revoke, signed tokens) | `server/src/obsidian_sync/services/sharing.py` |
| 4.6 | | FR-008 | Create share link endpoints (create, list, revoke, public access) | `server/src/obsidian_sync/routers/sharing.py` |
| 4.7 | | US5 | Plugin: add sharing UI (invite users, manage roles) | `plugin/src/ui/` |
| 4.8 | | US13 | Create AuditLog model + logging service | `server/src/obsidian_sync/models/audit.py`, `services/audit.py` |
| 4.9 | [P] | FR-002 | Write ACL tests (all role permutations) | `server/tests/test_acl.py` |
| 4.10 | [P] | FR-008 | Write share link tests (signing, expiry, revocation, password) | `server/tests/test_sharing.py` |

---

## Phase 5: Per-Vault Encryption (US7)

**Entry**: Phase 3 complete — sync works.
**Exit**: Encrypted vaults work end-to-end across plugin, CLI, and (later) portal.

| ID | Par | Story | Task | Files |
|----|-----|-------|------|-------|
| 5.1 | | FR-007 | Add encryption fields to Vault model (encrypted, salt, key_hash) + migration | `server/src/obsidian_sync/models/vault.py` |
| 5.2 | | FR-007 | Server: pass-through encrypted content (no decrypt, just store/retrieve) | `server/src/obsidian_sync/services/sync.py` |
| 5.3 | | FR-007 | Plugin: implement crypto module (Argon2id key derivation, AES-256-GCM encrypt/decrypt) | `plugin/src/sync/crypto.ts` |
| 5.4 | | FR-007 | Plugin: integrate encryption into sync engine (encrypt before upload, decrypt after download) | `plugin/src/sync/engine.ts` |
| 5.5 | | FR-007 | Plugin: vault passphrase UI (setup, unlock, change passphrase) | `plugin/src/ui/` |
| 5.6 | | FR-007 | CLI: implement crypto module (same algorithm, Python cryptography lib) | `cli/src/obsidian_sync_cli/sync/crypto.py` |
| 5.7 | | FR-007 | CLI: integrate encryption into sync commands (passphrase prompt or env var) | `cli/src/obsidian_sync_cli/commands/sync.py` |
| 5.8 | [P] | FR-007 | Write encryption tests (key derivation, encrypt/decrypt round-trip, cross-client compat) | `server/tests/test_encryption.py`, `cli/tests/` |

---

## Phase 6: Web Portal (US8, US10)

**Entry**: Phase 4 complete — sharing and ACL work.
**Exit**: Web portal for browsing vaults, viewing files, managing sharing, and viewing history.

| ID | Par | Story | Task | Files |
|----|-----|-------|------|-------|
| 6.1 | | FR-012 | Portal: set up React project with routing (TanStack Router), API client, auth flow | `portal/src/` |
| 6.2 | | FR-012 | Portal: login page + JWT token management (httpOnly cookie) | `portal/src/pages/Login.tsx` |
| 6.3 | | FR-012 | Portal: dashboard page (vault list, storage usage) | `portal/src/pages/Dashboard.tsx` |
| 6.4 | | FR-012 | Portal: vault browser (file tree, folder navigation, breadcrumbs) | `portal/src/pages/VaultBrowser.tsx` |
| 6.5 | | FR-012 | Portal: markdown renderer (GitHub-flavored, syntax highlighting) | `portal/src/components/MarkdownRenderer.tsx` |
| 6.6 | | FR-012 | Portal: sharing management UI (invite users, manage roles, create share links) | `portal/src/components/SharingModal.tsx` |
| 6.7 | | FR-012 | Portal: share link viewer (public page, rendered markdown, download) | `portal/src/pages/ShareView.tsx` |
| 6.8 | | FR-009 | Portal: file history page (version list, diff viewer, restore button) | `portal/src/pages/FileHistory.tsx` |
| 6.9 | | FR-009 | Server: implement history endpoints (list versions, get version, diff, restore) | `server/src/obsidian_sync/routers/history.py` |
| 6.10 | | FR-009 | Server: implement history service (version retention, pruning worker) | `server/src/obsidian_sync/services/history.py` |
| 6.11 | | FR-007 | Portal: encryption prompt + SubtleCrypto decryption for encrypted vaults | `portal/src/components/EncryptionPrompt.tsx`, `hooks/useCrypto.ts` |
| 6.12 | | FR-012 | Portal: admin panel (user management, server stats, audit log) | `portal/src/pages/Admin.tsx` |
| 6.13 | | US13 | Server: admin stats + audit log endpoints | `server/src/obsidian_sync/routers/admin.py` |
| 6.14 | | FR-013 | Server: configure FastAPI to serve portal static assets | `server/src/obsidian_sync/main.py` |
| 6.15 | | FR-013 | Docker: multi-stage build (Python server + React portal assets) | `docker/Dockerfile` |
| 6.16 | [P] | FR-012 | Write portal tests (critical flows: login, browse, share) | `portal/tests/` |
| 6.17 | [P] | FR-009 | Write history service tests | `server/tests/test_history.py` |

---

## Phase 7: Live Sync (US3)

**Entry**: Phase 3 complete — on-save sync works.
**Exit**: Real-time CRDT-based sync works in plugin.

| ID | Par | Story | Task | Files |
|----|-----|-------|------|-------|
| 7.1 | | FR-005 | Server: integrate pycrdt for Yjs document management | `server/src/obsidian_sync/services/yjs.py` |
| 7.2 | | FR-005 | Server: WebSocket binary message handling for Yjs updates | `server/src/obsidian_sync/websocket/protocol.py` |
| 7.3 | | FR-005 | Server: persist Yjs document state (storage backend) | `server/src/obsidian_sync/services/yjs.py` |
| 7.4 | | FR-005 | Plugin: integrate y-codemirror.next with Obsidian's CodeMirror 6 editor | `plugin/src/sync/yjs-provider.ts` |
| 7.5 | | FR-005 | Plugin: live sync toggle (per-vault setting, fallback to on-save) | `plugin/src/settings.ts` |
| 7.6 | [P] | FR-005 | Write live sync tests (concurrent edits, reconnection, catch-up) | `server/tests/test_yjs.py` |

---

## Phase 8: Storage Backends (US9)

**Entry**: Phase 2 complete — storage abstraction exists.
**Exit**: S3 backend works, vaults can be configured with different backends.

| ID | Par | Story | Task | Files |
|----|-----|-------|------|-------|
| 8.1 | | FR-006 | Implement S3Storage backend (aioboto3, configurable bucket/prefix/region) | `server/src/obsidian_sync/storage/s3.py` |
| 8.2 | | FR-006 | Storage backend admin endpoints (CRUD, test connectivity) | `server/src/obsidian_sync/routers/admin.py` |
| 8.3 | | FR-006 | Vault storage migration tool (copy data between backends) | `server/src/obsidian_sync/services/storage.py` |
| 8.4 | | FR-006 | Portal: storage backend configuration UI (admin panel) | `portal/src/pages/Admin.tsx` |
| 8.5 | | FR-006 | Plugin: storage backend selection during vault creation | `plugin/src/ui/setup-modal.ts` |
| 8.6 | [P] | FR-006 | Write S3 storage tests (mocked + integration with MinIO) | `server/tests/test_storage_s3.py` |

---

## Phase 9: External Sync (US11)

**Entry**: Phase 3 complete — sync engine and operation log work.
**Exit**: Mirror-mode sync to Google Drive and OneDrive works.

| ID | Par | Story | Task | Files |
|----|-----|-------|------|-------|
| 9.1 | | FR-010 | Define SyncConnector protocol | `server/src/obsidian_sync/connectors/__init__.py` |
| 9.2 | | FR-010 | Implement Google Drive connector (OAuth2, file CRUD) | `server/src/obsidian_sync/connectors/google_drive.py` |
| 9.3 | | FR-010 | Implement OneDrive connector (Microsoft Graph, file CRUD) | `server/src/obsidian_sync/connectors/onedrive.py` |
| 9.4 | | FR-010 | Create ExternalSyncConfig model + migration | `server/src/obsidian_sync/models/external.py` |
| 9.5 | | FR-010 | Implement external sync worker (mirror mode — watch operation log, push changes) | `server/src/obsidian_sync/workers/external_sync.py` |
| 9.6 | | FR-010 | External sync API endpoints (configure, trigger, status) | `server/src/obsidian_sync/routers/` |
| 9.7 | | FR-010 | OAuth flow endpoints (initiate + callback for GDrive/OneDrive) | `server/src/obsidian_sync/routers/` |
| 9.8 | | FR-010 | Portal: external sync configuration UI | `portal/src/` |
| 9.9 | [P] | FR-010 | Write connector tests (mocked API responses) | `server/tests/test_connectors.py` |

---

## Phase 10: Payments (US12)

**Entry**: Phase 6 complete — portal works.
**Exit**: SaaS billing with Stripe works end-to-end.

| ID | Par | Story | Task | Files |
|----|-----|-------|------|-------|
| 10.1 | | FR-011 | Create Subscription model + migration | `server/src/obsidian_sync/models/user.py` |
| 10.2 | | FR-011 | Implement entitlement engine (tier → limits + feature flags) | `server/src/obsidian_sync/services/entitlement.py` |
| 10.3 | | FR-011 | Implement entitlement middleware (check limits on vault create, sync, etc.) | `server/src/obsidian_sync/middleware/entitlement.py` |
| 10.4 | | FR-011 | Implement Stripe billing service (checkout, portal, webhooks) | `server/src/obsidian_sync/services/billing.py` |
| 10.5 | | FR-011 | Create billing router (checkout, portal session, webhook, usage) | `server/src/obsidian_sync/routers/billing.py` |
| 10.6 | | FR-011 | Portal: billing page (subscription status, upgrade, usage, Stripe portal link) | `portal/src/pages/Billing.tsx` |
| 10.7 | | FR-011 | Portal: upgrade prompts when hitting limits | `portal/src/components/` |
| 10.8 | [P] | FR-011 | Write entitlement + billing tests | `server/tests/test_billing.py` |

---

## Phase 11: Production Readiness

**Entry**: All feature phases complete.
**Exit**: Production-deployable with CI/CD, documentation, and monitoring.

| ID | Par | Story | Task | Files |
|----|-----|-------|------|-------|
| 11.1 | [P] | — | Multi-arch Docker build (GitHub Actions, amd64 + arm64) | `.github/workflows/` |
| 11.2 | [P] | — | Docker Hub / GHCR image publishing | `.github/workflows/` |
| 11.3 | [P] | — | CLI: publish to PyPI | `cli/`, `.github/workflows/` |
| 11.4 | | — | Write deployment guide (Synology NAS, generic Docker, VPS) | `docs/deployment.md` |
| 11.5 | | — | Write user guide (plugin setup, CLI usage, portal walkthrough) | `docs/user-guide.md` |
| 11.6 | | — | Write API documentation (auto-generated from OpenAPI + manual guides) | `docs/api.md` |
| 11.7 | | — | E2E tests with Playwright (portal critical paths) | `portal/tests/e2e/` |
| 11.8 | | — | Performance testing (sync latency, concurrent connections) | `server/tests/benchmarks/` |
| 11.9 | | — | Security review (dependency audit, OWASP checklist, penetration test plan) | `docs/security.md` |
| 11.10 | | — | Prometheus metrics endpoint + Grafana dashboard template | `docker/grafana/` |

---

## Dependency Graph (Phase Order)

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundation)
    ↓
Phase 3 (Core Sync) ←── required by all below
    ├── Phase 4 (ACL & Sharing)
    │       ↓
    │   Phase 6 (Portal) ←── requires Phase 4
    │       ↓
    │   Phase 10 (Payments) ←── requires Phase 6
    ├── Phase 5 (Encryption) ←── independent of Phase 4
    ├── Phase 7 (Live Sync) ←── independent
    ├── Phase 8 (Storage Backends) ←── can start after Phase 2
    └── Phase 9 (External Sync) ←── independent
            ↓
        Phase 11 (Production) ←── after all features
```

**Recommended MVP path**: Phases 1 → 2 → 3 → 4 → 5 → 6 (gives you a functional product with sync, sharing, encryption, and a portal).

Phases 7–10 can be added incrementally after MVP.
