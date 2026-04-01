# Obsidian Sync Server — Feature Specification

**Status**: Draft v2
**Date**: 2026-04-01

## Overview

A synchronization platform for Obsidian vaults supporting self-hosted and SaaS deployment modes. Three client types: Obsidian plugin (primary), web portal (browser access), and CLI (headless sync for servers/CI/NAS). Features multi-user access control, pluggable storage backends (local, S3, cloud), per-vault encryption, file sharing links, a web portal, file version history, external service sync, and payment integration.

---

## User Scenarios

### US1: Initial Vault Setup [P1]
**As a** user with an existing Obsidian vault,
**I want to** connect my vault to the sync server and choose where it's stored,
**So that** my notes are synced across devices with my preferred storage backend.

**Acceptance Criteria:**
- User installs plugin, enters server URL + credentials
- Plugin shows available storage backends (local, S3, etc.) configured by admin
- User picks a storage target (or uses default)
- Plugin uploads full vault to server on first sync with progress indicator
- Vault appears in web portal and server management

### US2: On-Save Sync [P1]
**As a** user editing notes on one device,
**I want to** have changes synced to the server when I save,
**So that** other devices pull the latest version.

**Acceptance Criteria:**
- File save detected → sent to server within 2 seconds
- Server stores new version, notifies connected clients via WebSocket
- Other clients pull and apply the update
- Works for creates, edits, renames, and deletes
- Binary files (images, PDFs) synced as opaque blobs with chunked upload for >5MB

### US3: Live Real-Time Sync [P2]
**As a** user who works across devices simultaneously,
**I want to** see changes appear on other devices in near-real-time,
**So that** I can switch contexts seamlessly.

**Acceptance Criteria:**
- Changes stream to server as user types (debounced)
- Other clients receive and apply within 500ms on LAN
- Uses Yjs CRDT — integrates with CodeMirror 6
- Togglable per vault in plugin settings
- Falls back to on-save sync if WebSocket disconnects

### US4: Offline Support & Conflict Resolution [P1]
**As a** user who sometimes works without internet,
**I want to** continue editing and have changes merged on reconnect,
**So that** I never lose work.

**Acceptance Criteria:**
- Plugin queues changes locally when server unreachable
- On reconnection, queued changes sync automatically
- Same-file offline edits on multiple devices → both versions preserved
- Conflict files clearly marked (e.g., `note.conflict-<timestamp>.md`)
- User can resolve via plugin UI or web portal (diff view, pick/merge)

### US5: Multi-User Vault Sharing & Permissions [P1]
**As a** vault owner,
**I want to** share vaults with other users at different permission levels,
**So that** I can collaborate securely.

**Acceptance Criteria:**
- Owner invites users by username/email with a role
- Four roles: `owner`, `admin`, `write`, `read`
  - **Owner**: full control, delete vault, transfer ownership
  - **Admin**: manage sharing, cannot delete vault or transfer ownership
  - **Write**: push + pull changes
  - **Read**: pull only
- ACL enforced server-side on every API call and WebSocket message
- Changes attributed to author in sync log
- Vault owner can revoke access instantly (active sessions terminated)

### US6: Shareable File Links [P2]
**As a** user,
**I want to** share a link to a specific file or folder in my vault,
**So that** others can view it without needing an account or the full vault.

**Acceptance Criteria:**
- Generate a signed, time-limited share link for a file or folder
- Link opens in web portal with rendered markdown view
- Share link options: expiry (1h, 24h, 7d, 30d, custom), password-protected (optional)
- Links are revocable by owner/admin
- View-only by default; optional "download" permission
- Link recipients cannot navigate outside the shared scope
- Share links work without authentication (public) or require login (restricted)

### US7: Per-Vault Encryption [P1]
**As a** security-conscious user,
**I want to** encrypt each vault with its own key,
**So that** even the server operator cannot read my data.

**Acceptance Criteria:**
- User sets a vault passphrase during creation (or enables encryption later)
- Encryption key derived from passphrase via Argon2id
- All file content encrypted with AES-256-GCM before storage
- Server never sees plaintext content — encryption/decryption happens client-side in plugin
- Web portal can decrypt if user provides passphrase in-browser (key never sent to server)
- Metadata (file paths, sizes, timestamps) visible to server for sync coordination
- Lost passphrase = lost data (no recovery, by design)

### US8: Web Portal [P2]
**As a** user,
**I want to** browse my vaults and files in a web browser,
**So that** I can access my notes without Obsidian installed.

**Acceptance Criteria:**
- Login with existing credentials
- Browse vault list, navigate folder tree
- View markdown files with rendered preview
- View file version history (see US10)
- Manage sharing (see US5) and share links (see US6)
- Download individual files or full vault as ZIP
- Admin panel: user management, server stats, storage usage
- Responsive design (works on mobile browsers)
- In SaaS mode: subscription management and billing (see US12)

### US9: Pluggable Storage Backends [P1]
**As a** self-hosted admin or SaaS user,
**I want to** choose where each vault's data is physically stored,
**So that** I control my data location and costs.

**Acceptance Criteria:**
- Storage backends configured at server level (admin) and selectable per vault
- Built-in backends:
  - **Local filesystem** (default for self-hosted)
  - **S3-compatible** (AWS S3, MinIO, Backblaze B2, DigitalOcean Spaces)
- Future backends (post-MVP): Azure Blob, GCS
- Each vault stores: `storage_backend` type + config (bucket, region, prefix, credentials)
- Credentials for cloud backends stored encrypted in database
- Storage backend can be migrated (server copies data between backends)
- Health check per backend (connectivity, permissions)

### US10: File Version History [P2]
**As a** user,
**I want to** see the history of changes to any file and restore previous versions,
**So that** I can recover from mistakes or review past content.

**Acceptance Criteria:**
- Every file save creates a version entry (author, timestamp, size, content hash)
- View version list in plugin sidebar or web portal
- Diff view between any two versions
- Restore a previous version (creates a new version, doesn't delete history)
- Configurable retention: keep N versions or versions from last N days
- Storage-efficient: content-addressed deduplication (identical content stored once)

### US11: External Service Sync [P3]
**As a** user,
**I want to** mirror my vault to Google Drive, OneDrive, or other services,
**So that** I have an additional backup or can access files via those platforms.

**Acceptance Criteria:**
- **Mirror mode**: Changes on server pushed to external service. One-directional.
- **Bidirectional mode** (day one): Changes on external service sync back. Conflict resolution applies.
- **BYO storage mode**: User provides credentials for their own cloud storage; vault uses it as primary backend (overlaps with US9).
- Supported services (MVP): Google Drive, OneDrive
- OAuth flow for connecting external accounts
- Sync runs as background task, not blocking primary sync
- Sync status visible in portal (last sync time, errors)
- Each vault independently configurable

### US12: Payment & Subscription Integration [P3]
**As a** SaaS operator,
**I want to** charge users for the service via subscriptions,
**So that** the platform is financially sustainable.

**Acceptance Criteria:**
- Stripe integration for payment processing
- Subscription tiers (configurable by admin):
  - **Free**: 1 vault, 100MB storage, on-save sync only
  - **Pro**: unlimited vaults, 10GB storage, live sync, file history
  - **Team**: Pro features + vault sharing + admin panel
- Usage-based billing option for storage overages
- Stripe Customer Portal for self-service billing management
- Webhook handling for payment events (subscription created/cancelled/failed)
- Grace period on failed payments before restricting access
- Self-hosted mode: billing system disabled entirely, all features unlocked

### US13: Server Administration [P1]
**As a** server administrator,
**I want to** manage users, monitor the system, and configure the platform,
**So that** I can keep things running smoothly.

**Acceptance Criteria:**
- First-run setup wizard creates admin account
- Admin panel in web portal: users, vaults, storage backends, system health
- CLI tool for headless administration (Docker exec friendly)
- Metrics: connected clients, active syncs, storage usage per vault/user, API latency
- Health check endpoint for Docker/load balancer monitoring
- Configurable via environment variables (12-factor app style)
- Audit log for admin actions (user created, vault deleted, permissions changed)

### US14: Headless CLI Sync [P2]
**As a** power user or sysadmin,
**I want to** sync vault directories from the command line without Obsidian,
**So that** I can integrate vault sync into scripts, cron jobs, CI pipelines, or use it on headless servers.

**Acceptance Criteria:**
- Installable via pip: `pip install obsidian-sync-cli`
- Commands:
  - `oss login <server-url>` — authenticate and store credentials
  - `oss vaults` — list available vaults
  - `oss sync <local-dir> --vault <name>` — initial sync (bidirectional)
  - `oss pull [--vault <name>]` — pull latest from server
  - `oss push [--vault <name>]` — push local changes to server
  - `oss status [--vault <name>]` — show sync status (pending changes, last sync)
  - `oss watch [--vault <name>]` — daemon mode, file watcher triggers on-save sync
- Supports encrypted vaults (passphrase via prompt, env var, or keyring)
- Conflict resolution: preserve both versions (same as plugin behavior)
- Config stored in `~/.config/obsidian-sync/` or `$OSS_CONFIG_DIR`
- Shares sync protocol code with server (common Python package)
- Works on Linux, macOS, Windows
- Supports API key auth for unattended/service use

---

## Functional Requirements

### FR-001: Authentication & Sessions
- JWT access tokens (15min expiry) + refresh tokens (30d, rotated on use)
- Password hashing: bcrypt (cost 12)
- Rate limiting on login endpoint (5 attempts/minute per IP)
- Session revocation (invalidate all refresh tokens for a user)
- API key support for programmatic access (service accounts)
- OAuth2 login (Google, GitHub) via Authlib — day one
- OAuth account linking: creates/links User record, sets `oauth_provider` + `oauth_id`
- JWT issued after OAuth callback (same token format as local auth)

### FR-002: Authorization & ACL
- Role-based: `owner > admin > write > read` per vault
- Server-wide roles: `superadmin`, `user`
- Every API endpoint and WebSocket message checks permissions
- Share links: separate permission model (view, download) with signed tokens
- ACL changes take effect immediately (active WebSocket connections re-evaluated)

### FR-003: Vault Management
- CRUD vaults via REST API
- Each vault: UUID, name, owner, storage backend config, encryption flag
- Vault-level settings: sync mode (on-save/live/both), retention policy, sharing
- Vault transfer (change owner)
- Vault archival (soft delete, data retained for configurable period)

### FR-004: File Sync Protocol (On-Save)
- Client sends `{path, content, last_known_version, content_hash}`
- Server validates version, stores new version, increments counter
- Server broadcasts change to connected clients via WebSocket
- Chunked upload for files >5MB
- Binary files synced as opaque blobs

### FR-005: File Sync Protocol (Live)
- WebSocket connection per vault, authenticated via JWT
- Yjs CRDT updates exchanged as binary messages (efficient encoding)
- Server persists Yjs document state for catch-up on reconnect
- Falls back to on-save on disconnection

### FR-006: Storage Abstraction
- `StorageBackend` protocol: `read`, `write`, `delete`, `list`, `exists`, `stat`
- Implementations: `LocalStorage`, `S3Storage`
- Per-vault storage config stored in database (encrypted credentials)
- Backend health checks
- Migration tool: copy vault between backends

### FR-007: Per-Vault Encryption
- Client-side encryption: content encrypted before upload, decrypted after download
- Key derivation: Argon2id(passphrase, vault-specific salt) → AES-256-GCM key
- Encrypted content stored as-is on any storage backend
- File metadata (path, size, timestamps) NOT encrypted (needed for sync coordination)
- Key verification: server stores hash of derived key for passphrase validation without seeing the key
- Web portal decryption: passphrase entered in browser, SubtleCrypto API, key never leaves client

### FR-008: Share Links
- Signed URL: `{base_url}/share/{token}` where token encodes vault_id + path + permissions + expiry
- Token signed with server secret (HMAC-SHA256)
- Optional password protection (bcrypt hash stored with link metadata)
- Link metadata in database: creator, target, permissions, expiry, access count
- Rendered markdown view in portal for `.md` files
- Raw download for other file types

### FR-009: File Version History
- Every file mutation creates a `FileVersion` record
- Content stored content-addressed: `{content_hash}` → file content
- Deduplication: identical content shares storage
- Retention policies: by count (last N versions) or by time (last N days)
- Pruning runs as background task, respects retention policy
- API: list versions, get version content, restore version, diff two versions

### FR-010: External Sync Connectors
- Connector interface: `connect(oauth_token)`, `push(path, content)`, `pull(path)`, `list(prefix)`
- Google Drive: OAuth2, files stored in a designated folder
- OneDrive: OAuth2 via Microsoft Graph API
- Mirror mode: background worker watches operation log, pushes changes out
- Bidirectional mode: polling for GDrive changes (5min interval), Microsoft Graph webhooks for OneDrive
- Conflict resolution: server version wins by default, conflicts preserved as `.conflict` files
- Connector status: last sync, pending changes, errors

### FR-011: Payment Integration (SaaS mode)
- Stripe: Products, Prices, Subscriptions, Customer Portal
- Webhook endpoint for Stripe events
- Entitlement engine: maps subscription tier → feature flags + limits
- Usage tracking: storage bytes, vault count, sync operations
- Grace period: 7 days after failed payment, then read-only, then suspend after 30 days
- Self-hosted: entitlement engine returns "unlimited" for all features

### FR-012: Web Portal
- React SPA built with Vite, served as static assets by FastAPI
- Auth: JWT (same as API), stored in httpOnly cookie for portal
- File browser: tree view, breadcrumb navigation, folder expand/collapse
- Markdown renderer: GitHub-flavored markdown with syntax highlighting
- Admin panel: user CRUD, vault overview, storage stats, audit log
- Responsive: mobile-friendly layout

### FR-013: Deployment
**Docker (self-hosted)**:
- Multi-stage Dockerfile: Python server + built React portal assets
- Docker Compose: server + Caddy (reverse proxy + auto-TLS)
- Docker Compose (dev): hot reload for server + portal
- Environment variables for all config (PORT, DATABASE_URL, SECRET_KEY, STORAGE_DEFAULT, STRIPE_*, etc.)
- Health check endpoint for container orchestration
- Multi-arch: amd64 + arm64

**AWS (SaaS)**:
- Lambda + Fargate hybrid: Lambda (via Mangum) for REST APIs, Fargate for WebSocket sync
- API Gateway routes REST traffic to Lambda; ALB routes WebSocket to Fargate
- ALB idle timeout: 4000s for persistent WebSocket connections, sticky sessions enabled
- Aurora Serverless PostgreSQL (same SQLAlchemy code, env var toggle)
- S3 for vault storage, CloudFront for portal static assets, ACM for TLS
- SQS + Lambda for background jobs (external sync, history pruning)
- AWS CDK (Python) for infrastructure-as-code
- Same codebase — deployment mode controlled entirely by environment variables

### FR-014: Rate Limiting
- Sliding window algorithm
- Three tiers: per-user, per-vault, global
- SaaS: Redis-backed counters
- Self-hosted: in-memory (no Redis dependency)
- Response headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- Configurable limits per subscription tier
- Auth endpoints: stricter limits (5 attempts/minute per IP)

### FR-015: GDPR & Privacy
- Data export: `POST /api/v1/users/me/export` triggers async job → ZIP of all user data
- Account deletion: `DELETE /api/v1/users/me` with 30-day grace period, then cascade delete
- Consent tracking: recorded at registration, timestamped, revocable
- Audit trail for all data access and admin actions
- Data minimization: collect only what's needed for sync functionality
- Right to rectification: users can update all personal data

### FR-016: Mobile Optimization
- Platform detection: `Platform.isMobileApp` / `Platform.isIosApp` / `Platform.isAndroidApp`
- Adaptive sync profiles (mobile vs desktop):
  - Debounce: 5000ms mobile / 2000ms desktop
  - Max concurrent uploads: 3 mobile / 10 desktop
  - Live sync: off by default on mobile / on by default on desktop
  - Max auto-sync file size: 20MB mobile / unlimited desktop
  - WebSocket reconnect max delay: 30s mobile / 10s desktop
- Binary files >20MB: queue for WiFi-only sync on mobile
- Battery-aware: reduce sync frequency when battery <20%
- All mobile defaults overridable in plugin settings
- No Node.js or Electron API usage (breaks on mobile)

---

## Data Entities

### User
- `id` (UUID), `username` (unique), `email` (unique, nullable)
- `password_hash`, `is_superadmin` (bool)
- `oauth_provider` (nullable — google/github), `oauth_id` (nullable)
- `stripe_customer_id` (nullable — SaaS mode)
- `gdpr_consent_at` (nullable), `deletion_requested_at` (nullable)
- `created_at`, `updated_at`, `last_login`

### Subscription (SaaS mode)
- `id` (UUID), `user_id` (FK→User)
- `stripe_subscription_id`, `tier` (enum: free/pro/team)
- `max_storage_bytes` (1GB free, 5GB pro, 10GB team, unlimited BYO)
- `status` (enum: active/past_due/cancelled/suspended)
- `current_period_end`, `created_at`

### Vault
- `id` (UUID), `name`, `owner_id` (FK→User)
- `storage_backend` (enum: local/s3), `storage_config` (JSON, encrypted)
- `encrypted` (bool), `encryption_salt` (bytes, nullable)
- `encryption_key_hash` (for passphrase verification, nullable)
- `sync_mode` (enum: on_save/live/both)
- `obsidian_config_sync` (enum: all/settings_only/none — controls .obsidian/ folder sync)
- `retention_policy` (JSON: {type: "count"|"days", value: int})
- `archived_at` (nullable — soft delete)
- `created_at`, `updated_at`

### VaultAccess
- `vault_id` (FK→Vault), `user_id` (FK→User)
- `role` (enum: owner/admin/write/read)
- `granted_at`, `granted_by` (FK→User)

### FileVersion
- `id` (UUID), `vault_id` (FK→Vault), `file_path`
- `version` (int), `content_hash` (SHA-256), `size_bytes`
- `author_id` (FK→User), `created_at`
- Content stored via storage backend: `versions/{content_hash}`

### SyncOperation
- `id` (UUID), `vault_id` (FK→Vault), `file_path`
- `operation_type` (enum: create/update/delete/rename)
- `version` (int), `author_id` (FK→User)
- `payload` (JSON), `created_at`

### ShareLink
- `id` (UUID), `vault_id` (FK→Vault), `file_path` (nullable — whole vault)
- `token` (unique, indexed), `created_by` (FK→User)
- `permissions` (enum: view/download)
- `password_hash` (nullable), `expires_at`
- `access_count` (int), `max_access_count` (nullable)
- `revoked` (bool), `created_at`

### ExternalSyncConfig
- `id` (UUID), `vault_id` (FK→Vault)
- `provider` (enum: google_drive/onedrive)
- `mode` (enum: mirror/bidirectional)
- `oauth_token_encrypted` (bytes), `remote_folder_id`
- `last_sync_at`, `last_error`, `enabled` (bool)
- `created_at`, `updated_at`

### StorageBackendConfig
- `id` (UUID), `name` (unique), `backend_type` (enum: local/s3)
- `config_encrypted` (JSON — bucket, region, access_key, etc.)
- `is_default` (bool), `created_by` (FK→User)
- `created_at`

### AuditLog
- `id` (UUID), `actor_id` (FK→User)
- `action` (string), `resource_type` (string), `resource_id` (UUID)
- `details` (JSON), `ip_address`, `created_at`

### GDPRExportRequest
- `id` (UUID), `user_id` (FK→User)
- `status` (enum: pending/processing/ready/expired)
- `download_url` (nullable), `expires_at` (nullable)
- `created_at`

---

## Success Criteria

- On-save sync latency < 2 seconds E2E on LAN
- Live sync latency < 500ms E2E on LAN
- Server handles 50 concurrent clients without degradation (SaaS target)
- Server handles 10 concurrent clients on NAS hardware (self-hosted target)
- No data loss in any sync scenario
- Docker image < 300MB (includes portal assets)
- Self-hosted idle memory < 256MB
- First-time setup < 5 minutes
- Client-side encryption adds < 50ms overhead per file operation
- Share link loads in < 2 seconds for files up to 1MB

---

## Resolved Decisions

| Question | Resolution |
|----------|------------|
| Max vault size | Tiered: 1GB (free), 5GB (pro), 10GB (team) for platform storage. Unlimited for BYO storage backends. |
| `.obsidian/` config sync | Configurable per vault via `obsidian_config_sync`: `all`, `settings_only`, `none` |
| Server-side search | No. Client-side only. Portal is a management utility, not an Obsidian replacement. |
| Encrypted vault search | N/A — no server-side search. |
| OAuth/SSO | Day one. Google + GitHub OAuth via Authlib (FR-001). |
| Rate limiting | 3-tier: per-user + per-vault + global. Redis for SaaS, in-memory for self-hosted (FR-014). |
| GDPR | Yes — data export, account deletion, consent tracking from day one (FR-015). |
| Bidirectional external sync | Day one. Polling for GDrive, webhooks for OneDrive (FR-010). |
| Mobile optimization | Plugin optimized for Obsidian mobile with adaptive sync profiles (FR-016). |
| AWS deployment | Lambda + Fargate hybrid alongside Docker self-hosted (FR-013). |
