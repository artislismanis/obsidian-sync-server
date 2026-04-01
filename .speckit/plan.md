# Obsidian Sync Server — Implementation Plan

**Status**: Draft v3
**Date**: 2026-04-01

## Technical Context

| Aspect | Decision |
|--------|----------|
| Server language | Python 3.11+ |
| Server framework | FastAPI (async) |
| Database | SQLAlchemy async — SQLite (aiosqlite) or PostgreSQL (asyncpg) |
| Real-time transport | WebSocket (native FastAPI) |
| Auth | JWT (PyJWT) + bcrypt + API keys + OAuth (Authlib: Google, GitHub) |
| Encryption | AES-256-GCM, Argon2id key derivation (client-side) |
| Plugin language | TypeScript (Obsidian Plugin API) |
| Editor integration | CodeMirror 6 + Yjs (y-codemirror.next) |
| Portal | React 18 + Vite + TanStack Query |
| CLI client | Python (Click/Typer), shares sync code with server |
| Payments | Stripe (subscriptions + usage billing) |
| Packaging | Docker multi-arch (amd64, arm64) + pip (CLI) + AWS CDK (SaaS) |
| AWS (SaaS) | Lambda (Mangum) + Fargate (WebSocket) + ALB + Aurora Serverless + S3 + CloudFront |
| Testing (server) | pytest + pytest-asyncio + httpx |
| Testing (portal) | Vitest + React Testing Library |
| Testing (plugin) | Jest |
| Testing (CLI) | pytest |
| E2E | Playwright (portal) |
| CI | GitHub Actions |

## Constitution Check

| Principle | Satisfied | Notes |
|-----------|-----------|-------|
| P1: Dual-Mode | Yes | Feature flags, env-based config |
| P2: Data Sovereignty | Yes | Pluggable storage, client-side encryption, data export |
| P3: Obsidian-Native | Yes | Plugin settings panel, status bar |
| P4: Correctness | Yes | CRDT, conflict preservation, operation log |
| P5: Simple Ops | Yes | Docker Compose, SQLite default, env vars |
| P6: Pluggable Storage | Yes | StorageBackend protocol + implementations |
| P7: Security Default | Yes | Per-vault encryption, signed share links, ACL |
| P8: Privacy by Design | Yes | GDPR export/deletion, consent tracking, audit trail |
| P9: Mobile-First Parity | Yes | Platform-aware sync profiles, battery/bandwidth awareness |

---

## Phase 0: Architecture & Design

### Storage Abstraction Layer

```python
class StorageBackend(Protocol):
    """All methods are async. Paths are vault-relative (e.g., 'notes/daily.md')."""

    async def read(self, path: str) -> bytes: ...
    async def write(self, path: str, data: bytes, content_hash: str) -> None: ...
    async def delete(self, path: str) -> None: ...
    async def exists(self, path: str) -> bool: ...
    async def list(self, prefix: str = "") -> list[StorageEntry]: ...
    async def stat(self, path: str) -> StorageStat: ...  # size, modified, hash

class LocalStorage(StorageBackend):
    """Filesystem backend. root_path = {DATA_DIR}/vaults/{vault_id}/"""

class S3Storage(StorageBackend):
    """S3-compatible backend. Uses aioboto3. Configurable bucket/prefix/region."""
```

Each vault has its own `StorageBackend` instance, configured via `Vault.storage_backend` + `Vault.storage_config`. The server instantiates backends lazily and caches them.

### Per-Vault Encryption Flow

```
Client (plugin/CLI/portal):
  1. User provides vault passphrase
  2. Derive key: Argon2id(passphrase, vault_salt) → 256-bit key
  3. For each file write: AES-256-GCM(key, nonce, plaintext) → ciphertext
  4. Upload ciphertext to server
  5. For each file read: download ciphertext → AES-256-GCM decrypt → plaintext

Server:
  - Stores ciphertext as-is (any storage backend)
  - Stores vault_salt (public, needed for key derivation)
  - Stores key_verification_hash (hash of derived key, for passphrase validation)
  - NEVER sees plaintext content
  - File metadata (paths, sizes, timestamps) remains unencrypted for sync coordination
```

Portal uses Web Crypto API (SubtleCrypto) for in-browser decryption — key never leaves the client.

**Open question**: Should file paths be encrypted? Encrypting paths makes server-side operations (listing, conflict detection) much harder. Current design: paths are cleartext metadata.

### Share Link Design

```
Token structure (before signing):
  {vault_id}:{path}:{permissions}:{expiry_unix}:{link_id}

Signed token:
  base64url(payload) + "." + base64url(HMAC-SHA256(server_secret, payload))

URL: {base_url}/share/{signed_token}

Verification:
  1. Decode token, verify HMAC signature
  2. Check expiry
  3. Check revocation (link_id in database)
  4. Check optional password
  5. Serve content (render markdown or download)
```

### External Sync Connector Design

```python
class SyncConnector(Protocol):
    """Interface for external service sync."""

    async def authenticate(self, oauth_token: str) -> None: ...
    async def push_file(self, remote_path: str, content: bytes) -> None: ...
    async def pull_file(self, remote_path: str) -> bytes: ...
    async def list_files(self, prefix: str = "") -> list[RemoteFile]: ...
    async def delete_file(self, remote_path: str) -> None: ...

class GoogleDriveConnector(SyncConnector):
    """Uses Google Drive API v3. Files stored in a designated folder."""

class OneDriveConnector(SyncConnector):
    """Uses Microsoft Graph API. Files stored in a designated folder."""
```

Mirror mode: A background worker watches the `SyncOperation` table. For each new operation, it calls the appropriate connector method.

Bidirectional mode: Additionally polls external services for changes:
- **Google Drive**: Changes API polling every 5 minutes (configurable)
- **OneDrive**: Microsoft Graph change notifications (webhooks) for real-time detection
- External changes pulled down, version-compared with server state, conflicts preserved

### Payment / Entitlement Architecture

```python
class EntitlementEngine:
    """Determines what features/limits a user has based on subscription tier."""

    def get_limits(self, user: User) -> Entitlements:
        if settings.DEPLOYMENT_MODE == "self_hosted":
            return Entitlements.unlimited()
        # Look up subscription tier and return limits
        ...

@dataclass
class Entitlements:
    max_vaults: int | None          # None = unlimited
    max_storage_bytes: int | None
    live_sync: bool
    file_history: bool
    vault_sharing: bool
    external_sync: bool
    max_share_links: int | None
```

Stripe webhooks update subscription status in DB. Entitlement checks are middleware — fast DB lookup, cached per-request.

---

## Phase 1: Project Structure

### Server
```
server/
├── pyproject.toml                   # Dependencies, build config
├── alembic.ini
├── alembic/versions/
├── src/obsidian_sync/
│   ├── __init__.py
│   ├── main.py                      # FastAPI app factory + lifespan
│   ├── config.py                    # pydantic-settings (env vars)
│   ├── database.py                  # SQLAlchemy async engine + session
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py                  # User, Subscription
│   │   ├── vault.py                 # Vault, VaultAccess, StorageBackendConfig
│   │   ├── sync.py                  # FileVersion, SyncOperation
│   │   ├── sharing.py               # ShareLink
│   │   ├── external.py              # ExternalSyncConfig
│   │   └── audit.py                 # AuditLog
│   ├── schemas/                     # Pydantic request/response models
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── vault.py
│   │   ├── sync.py
│   │   ├── sharing.py
│   │   └── billing.py
│   ├── routers/
│   │   ├── auth.py                  # login, refresh, setup
│   │   ├── users.py                 # user CRUD (admin)
│   │   ├── vaults.py                # vault CRUD + files
│   │   ├── sharing.py               # vault sharing + share links
│   │   ├── history.py               # file version history
│   │   ├── billing.py               # Stripe webhooks + subscription
│   │   ├── admin.py                 # admin panel API
│   │   ├── portal.py                # portal-specific endpoints
│   │   └── health.py                # health + metrics
│   ├── services/
│   │   ├── auth.py                  # JWT, password, API keys
│   │   ├── sync.py                  # Sync coordination + conflict resolution
│   │   ├── vault.py                 # Vault CRUD + file operations
│   │   ├── yjs.py                   # Yjs CRDT integration (pycrdt)
│   │   ├── storage.py               # Storage backend factory + registry
│   │   ├── sharing.py               # Share link signing + verification
│   │   ├── history.py               # Version history + pruning
│   │   ├── entitlement.py           # Subscription → feature flags
│   │   ├── billing.py               # Stripe API integration
│   │   ├── external_sync.py         # External sync orchestration
│   │   └── audit.py                 # Audit logging
│   ├── storage/
│   │   ├── __init__.py              # StorageBackend protocol
│   │   ├── local.py                 # LocalStorage
│   │   └── s3.py                    # S3Storage (aioboto3)
│   ├── connectors/
│   │   ├── __init__.py              # SyncConnector protocol
│   │   ├── google_drive.py
│   │   └── onedrive.py
│   ├── websocket/
│   │   ├── handler.py               # Connection manager
│   │   └── protocol.py              # Message types + routing
│   ├── middleware/
│   │   ├── auth.py                  # JWT + API key middleware
│   │   └── entitlement.py           # Feature flag checks
│   └── workers/
│       ├── external_sync.py         # Background sync worker
│       └── history_pruner.py        # Version retention cleanup
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_sync.py
│   ├── test_vaults.py
│   ├── test_websocket.py
│   ├── test_storage.py
│   ├── test_sharing.py
│   ├── test_encryption.py
│   └── test_entitlement.py
└── Dockerfile
```

### CLI Client
```
cli/
├── pyproject.toml                   # pip install obsidian-sync-cli
├── src/obsidian_sync_cli/
│   ├── __init__.py
│   ├── main.py                      # Typer CLI app
│   ├── commands/
│   │   ├── auth.py                  # login, logout
│   │   ├── vaults.py                # list vaults
│   │   ├── sync.py                  # sync, pull, push
│   │   ├── watch.py                 # daemon file watcher
│   │   └── status.py                # sync status
│   ├── client/
│   │   ├── http.py                  # REST API client (httpx)
│   │   ├── websocket.py             # WebSocket client
│   │   └── auth.py                  # Token storage + refresh
│   ├── sync/
│   │   ├── engine.py                # Sync orchestration (shared logic)
│   │   ├── conflict.py              # Conflict resolution
│   │   ├── watcher.py               # Filesystem watcher (watchfiles)
│   │   └── crypto.py                # Encryption/decryption
│   └── config.py                    # Config file (~/.config/obsidian-sync/)
└── tests/
    ├── test_sync.py
    └── test_commands.py
```

### Portal
```
portal/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── index.html
├── src/
│   ├── main.tsx                     # React entry
│   ├── App.tsx                      # Router + providers
│   ├── api/                         # API client (fetch + TanStack Query)
│   │   ├── client.ts
│   │   ├── auth.ts
│   │   └── queries.ts
│   ├── pages/
│   │   ├── Login.tsx
│   │   ├── Dashboard.tsx            # Vault list
│   │   ├── VaultBrowser.tsx         # File tree + content viewer
│   │   ├── FileHistory.tsx          # Version list + diff
│   │   ├── ShareView.tsx            # Public share link viewer
│   │   ├── Settings.tsx             # User settings
│   │   ├── Admin.tsx                # Admin panel
│   │   └── Billing.tsx              # Subscription management (SaaS)
│   ├── components/
│   │   ├── FileTree.tsx
│   │   ├── MarkdownRenderer.tsx
│   │   ├── DiffViewer.tsx
│   │   ├── SharingModal.tsx
│   │   └── EncryptionPrompt.tsx     # Passphrase input for encrypted vaults
│   ├── hooks/
│   │   └── useCrypto.ts             # SubtleCrypto for client-side decrypt
│   └── utils/
│       └── crypto.ts                # AES-256-GCM + Argon2 (via argon2-browser)
├── tests/
└── public/
```

### Plugin
```
plugin/
├── package.json
├── tsconfig.json
├── esbuild.config.mjs
├── manifest.json
├── src/
│   ├── main.ts
│   ├── settings.ts                  # Settings tab (server URL, credentials, per-vault config)
│   ├── sync/
│   │   ├── client.ts                # HTTP + WS client
│   │   ├── engine.ts                # Sync orchestration
│   │   ├── conflict.ts              # Conflict detection + resolution
│   │   ├── yjs-provider.ts          # Yjs WebSocket provider
│   │   ├── queue.ts                 # Offline change queue
│   │   └── crypto.ts                # AES-256-GCM + Argon2
│   ├── ui/
│   │   ├── status-bar.ts
│   │   ├── conflict-modal.ts
│   │   ├── setup-modal.ts
│   │   └── history-view.ts          # File version history sidebar
│   └── utils/
│       ├── debounce.ts
│       └── hash.ts
├── tests/
└── styles.css
```

### Docker
```
docker/
├── Dockerfile                       # Multi-stage: Python server + React portal build
├── Dockerfile.cli                   # CLI client image (for containerized sync)
├── docker-compose.yml               # Server + Caddy
├── docker-compose.dev.yml           # Dev overrides (hot reload)
├── docker-compose.full.yml          # Server + Caddy + PostgreSQL (SaaS-like)
├── Caddyfile
└── .env.example
```

---

## API Design (REST)

```
# Auth
POST   /api/v1/auth/login                         # Get tokens
POST   /api/v1/auth/refresh                        # Refresh access token
POST   /api/v1/auth/setup                          # First-run admin creation
POST   /api/v1/auth/api-keys                       # Create API key
DELETE /api/v1/auth/api-keys/{id}                  # Revoke API key
GET    /api/v1/auth/oauth/{provider}               # Start OAuth flow (Google/GitHub)
GET    /api/v1/auth/oauth/{provider}/callback      # OAuth callback

# Users (admin)
GET    /api/v1/users
POST   /api/v1/users
GET    /api/v1/users/{id}
PATCH  /api/v1/users/{id}
DELETE /api/v1/users/{id}
PATCH  /api/v1/users/{id}/password
POST   /api/v1/users/me/export                     # GDPR data export
GET    /api/v1/users/me/export/{id}                # Check export status / download
DELETE /api/v1/users/me                            # GDPR account deletion (30-day grace)
PATCH  /api/v1/users/me/cancel-deletion            # Cancel deletion request

# Vaults
GET    /api/v1/vaults                              # List user's vaults
POST   /api/v1/vaults                              # Create vault (with storage + encryption config)
GET    /api/v1/vaults/{id}
PATCH  /api/v1/vaults/{id}                         # Update vault settings
DELETE /api/v1/vaults/{id}
GET    /api/v1/vaults/{id}/files                   # List files (tree or flat)
GET    /api/v1/vaults/{id}/files/{path}            # Get file content
PUT    /api/v1/vaults/{id}/files/{path}            # Upload/update file
DELETE /api/v1/vaults/{id}/files/{path}            # Delete file
GET    /api/v1/vaults/{id}/status                  # Sync status
POST   /api/v1/vaults/{id}/export                  # Export vault as ZIP

# Vault Sharing
GET    /api/v1/vaults/{id}/sharing                 # List access
POST   /api/v1/vaults/{id}/sharing                 # Grant access
PATCH  /api/v1/vaults/{id}/sharing/{user_id}       # Update role
DELETE /api/v1/vaults/{id}/sharing/{user_id}       # Revoke access

# Share Links
POST   /api/v1/vaults/{id}/share-links             # Create share link
GET    /api/v1/vaults/{id}/share-links             # List share links
DELETE /api/v1/vaults/{id}/share-links/{link_id}   # Revoke link
GET    /api/v1/share/{token}                        # Access shared content (public)

# File History
GET    /api/v1/vaults/{id}/files/{path}/history    # List versions
GET    /api/v1/vaults/{id}/files/{path}/history/{version}  # Get version content
POST   /api/v1/vaults/{id}/files/{path}/restore/{version}  # Restore version
GET    /api/v1/vaults/{id}/files/{path}/diff       # Diff two versions (?v1=X&v2=Y)

# Storage Backends (admin)
GET    /api/v1/storage-backends                    # List configured backends
POST   /api/v1/storage-backends                    # Add backend
DELETE /api/v1/storage-backends/{id}               # Remove backend
POST   /api/v1/storage-backends/{id}/test          # Test connectivity

# External Sync
GET    /api/v1/vaults/{id}/external-sync           # Get config
POST   /api/v1/vaults/{id}/external-sync           # Configure connector
DELETE /api/v1/vaults/{id}/external-sync            # Remove connector
POST   /api/v1/vaults/{id}/external-sync/trigger   # Manual sync trigger
GET    /api/v1/external-sync/oauth/{provider}      # Start OAuth flow
GET    /api/v1/external-sync/oauth/{provider}/callback  # OAuth callback

# Billing (SaaS mode)
GET    /api/v1/billing/subscription                # Current subscription
POST   /api/v1/billing/checkout                    # Create Stripe checkout session
POST   /api/v1/billing/portal                      # Create Stripe customer portal session
POST   /api/v1/billing/webhooks                    # Stripe webhook endpoint
GET    /api/v1/billing/usage                       # Current usage stats

# Admin
GET    /api/v1/admin/stats                         # Server-wide statistics
GET    /api/v1/admin/audit-log                     # Audit log (paginated)
GET    /api/v1/admin/config                        # Server configuration (read-only)

# System
GET    /api/v1/health                              # Health check
GET    /api/v1/metrics                             # Prometheus-format metrics (admin)
```

## API Design (WebSocket)

```
WS /api/v1/sync/{vault_id}    # Auth via JWT in query param or first message
```

Message types (JSON-framed, binary for Yjs updates):

```jsonc
// Client → Server
{"type": "file_save", "path": "note.md", "content": "<base64>", "version": 5, "content_hash": "sha256:..."}
{"type": "file_delete", "path": "old.md", "version": 3}
{"type": "file_rename", "old_path": "a.md", "new_path": "b.md", "version": 4}
{"type": "yjs_update", "path": "note.md", "update": "<base64 Yjs binary>"}
{"type": "pull", "since_version": 42}
{"type": "ping"}

// Server → Client
{"type": "file_changed", "path": "note.md", "version": 6, "content": "<base64>", "author": "username"}
{"type": "file_deleted", "path": "old.md", "version": 4, "author": "username"}
{"type": "file_renamed", "old_path": "a.md", "new_path": "b.md", "version": 5}
{"type": "yjs_update", "path": "note.md", "update": "<base64>"}
{"type": "conflict", "path": "note.md", "server_version": 6, "your_version": 5}
{"type": "sync_complete", "vault_version": 50}
{"type": "error", "code": "FORBIDDEN", "message": "..."}
{"type": "pong"}
```

Note: For encrypted vaults, `content` fields contain ciphertext. Server never decrypts.

---

## Key Technical Decisions

### SQLite vs PostgreSQL
Both supported from day one via SQLAlchemy async. Config toggle:
- `DATABASE_URL=sqlite+aiosqlite:///data/obsidian-sync.db` (self-hosted default)
- `DATABASE_URL=postgresql+asyncpg://user:pass@host/db` (SaaS)

Alembic migrations use dialect-aware SQL where needed.

### Yjs for Live Sync
- pycrdt (Python) + y-codemirror.next (TypeScript plugin)
- Server persists Yjs document state for reconnection catch-up
- CLI client does NOT support live sync (on-save only)

### React + Vite for Portal
- Built as static assets, served by FastAPI via `StaticFiles` mount
- In production Docker image: `npm run build` → copy to `/app/static/`
- SaaS mode could optionally CDN-host the assets

### Typer for CLI
- Modern Python CLI framework (built on Click)
- Rich terminal output for progress bars, tables
- Shares `httpx` client code pattern with server test suite

### Background Workers
- `arq` (lightweight async task queue, Redis-backed) for SaaS mode
- Simple `asyncio.create_task` for self-hosted mode (no Redis dependency)
- Used for: external sync mirror, version history pruning, storage migration

### Stripe Integration
- Only active when `STRIPE_SECRET_KEY` env var is set
- All billing routes return 404 in self-hosted mode
- Entitlement engine returns unlimited for all features in self-hosted mode

---

## OAuth Flow Design

```
Google/GitHub OAuth2 via Authlib:

1. User clicks "Login with Google/GitHub" in plugin or portal
2. Client redirects to: GET /api/v1/auth/oauth/{provider}
3. Server redirects to provider's OAuth consent page
4. Provider redirects back: GET /api/v1/auth/oauth/{provider}/callback?code=...
5. Server exchanges code for access token, fetches user profile
6. Server creates/links User record (sets oauth_provider, oauth_id, email)
7. Server issues JWT (same format as local auth)
8. Client stores JWT and proceeds normally

Account linking:
- If email matches existing local account → link OAuth to existing user
- If new email → create new user with OAuth credentials
- Users can have both local password AND OAuth linked
```

## Rate Limiting Architecture

```
Algorithm: Sliding window counter

Tiers:
- Per-IP (auth endpoints): 5 requests/minute
- Per-user: 100 requests/minute (configurable by subscription tier)
- Per-vault: 60 sync operations/minute
- Global: 10,000 requests/minute (protects server)

Implementation:
- SaaS: Redis (INCR + EXPIRE, sliding window via sorted sets)
- Self-hosted: In-memory dict with TTL (no Redis dependency)

Response headers on every response:
  X-RateLimit-Limit: 100
  X-RateLimit-Remaining: 87
  X-RateLimit-Reset: 1711929600

429 Too Many Requests when exceeded, with Retry-After header
```

## GDPR Compliance Design

```
Data Export (POST /api/v1/users/me/export):
  1. Creates GDPRExportRequest record (status: pending)
  2. Background job collects: user profile, all owned vaults, all files, metadata, audit log
  3. Generates ZIP archive, uploads to temporary storage
  4. Sets download_url + expires_at (48h)
  5. Notifies user (or returns status via polling)

Account Deletion (DELETE /api/v1/users/me):
  1. Sets deletion_requested_at on User record
  2. 30-day grace period (user can cancel via PATCH /api/v1/users/me/cancel-deletion)
  3. After 30 days, background job cascades:
     - Delete all owned vaults + files + versions
     - Remove VaultAccess records
     - Remove ShareLinks
     - Remove ExternalSyncConfigs
     - Anonymize AuditLog entries (set actor_id to null)
     - Delete User record

Consent:
  - Recorded at registration (gdpr_consent_at timestamp)
  - Consent text versioned (consent_version field)
  - Revocable (triggers account deletion flow)
```

## Mobile Plugin Architecture

```typescript
// plugin/src/sync/platform.ts

interface SyncProfile {
  debounceMs: number;            // 2000 (desktop) / 5000 (mobile)
  maxConcurrentUploads: number;  // 10 (desktop) / 3 (mobile)
  liveSyncDefault: boolean;      // true (desktop) / false (mobile)
  maxAutoSyncFileSize: number;   // Infinity (desktop) / 20_971_520 (mobile, 20MB)
  wsReconnectMaxDelay: number;   // 10_000 (desktop) / 30_000 (mobile)
  wsReconnectBaseDelay: number;  // 1_000 (both)
  wifiOnlyLargeFiles: boolean;   // false (desktop) / true (mobile)
  batteryAwareSync: boolean;     // false (desktop) / true (mobile)
  batteryThreshold: number;      // N/A (desktop) / 0.2 (mobile, 20%)
}

const DESKTOP_PROFILE: SyncProfile = {
  debounceMs: 2000,
  maxConcurrentUploads: 10,
  liveSyncDefault: true,
  maxAutoSyncFileSize: Infinity,
  wsReconnectMaxDelay: 10_000,
  wsReconnectBaseDelay: 1_000,
  wifiOnlyLargeFiles: false,
  batteryAwareSync: false,
  batteryThreshold: 0,
};

const MOBILE_PROFILE: SyncProfile = {
  debounceMs: 5000,
  maxConcurrentUploads: 3,
  liveSyncDefault: false,
  maxAutoSyncFileSize: 20_971_520,
  wsReconnectMaxDelay: 30_000,
  wsReconnectBaseDelay: 1_000,
  wifiOnlyLargeFiles: true,
  batteryAwareSync: true,
  batteryThreshold: 0.2,
};

function getSyncProfile(): SyncProfile {
  if (Platform.isMobileApp) return { ...MOBILE_PROFILE };
  return { ...DESKTOP_PROFILE };
}

// All profile values overridable in plugin settings
```

Key mobile constraints:
- Never use Node.js or Electron APIs (crash on mobile)
- Use `requestUrl` instead of `fetch` (Obsidian's network abstraction)
- Files >20MB: queue for manual sync or WiFi-only
- No background sync — only syncs when Obsidian app is active
- WebSocket reconnect: exponential backoff 1s → 30s (vs 1s → 10s desktop)

## AWS Deployment Architecture

```
Internet
  ├── CloudFront → S3 (portal static assets)
  └── API Gateway → Lambda (Mangum)       ← REST API ($0 at idle)
      ALB → Fargate (0.25 vCPU, 512MB)    ← WebSocket sync only (~$9/month)
              ↓
        Aurora Serverless PostgreSQL        ← Same SQLAlchemy code (~$15/month)
              ↓
        S3 (vault storage)                  ← Pay per GB
              ↓
        SQS → Lambda                        ← Background jobs (external sync, pruning)

aws/
├── cdk/
│   ├── app.py                    # CDK app entry point
│   ├── stacks/
│   │   ├── network.py            # VPC, subnets, security groups
│   │   ├── api.py                # API Gateway + Lambda (REST via Mangum)
│   │   ├── websocket.py          # ECS Fargate + ALB (WebSocket sync)
│   │   ├── database.py           # Aurora Serverless PostgreSQL
│   │   ├── storage.py            # S3 buckets for vault data
│   │   ├── cdn.py                # CloudFront for portal
│   │   └── background.py         # SQS queues + Lambda workers
│   └── requirements.txt          # aws-cdk-lib
├── lambda/
│   └── handler.py                # Mangum adapter: from mangum import Mangum; handler = Mangum(app)
└── README.md

Key env vars for AWS mode:
  DEPLOYMENT_MODE=saas
  DATABASE_URL=postgresql+asyncpg://user:pass@aurora-endpoint:5432/obsidian_sync
  STORAGE_BACKEND=s3
  S3_BUCKET=obsidian-sync-vaults
  AWS_REGION=eu-west-1
  STRIPE_SECRET_KEY=sk_live_...

Cost estimates:
  1-10 users:   ~$25-35/month
  100 users:    ~$60-120/month
  1000+ users:  Aurora + Fargate auto-scale, ~$200-400/month
```

### Why Lambda + Fargate Hybrid?
- Lambda for REST: $0 at idle, auto-scales, no container management. ~90% of API requests are stateless REST.
- Fargate for WebSocket: persistent connections need long-lived processes. Lambda's 15-min timeout can't hold WebSocket connections.
- ALB routes `/api/v1/sync/*` (WebSocket upgrade) to Fargate target group, everything else to API Gateway.
- Cost-effective: only the WebSocket service runs continuously (~$9/month for 0.25 vCPU).

### Why Aurora over DynamoDB?
- Data model is highly relational (User → Vault → VaultAccess → FileVersion → SyncOperation)
- SQLAlchemy code works identically on SQLite (self-hosted) and Aurora (SaaS) — one data layer
- DynamoDB would require rewriting all data access code and a completely different query model
- Aurora Serverless v2 auto-scales and starts at ~$15/month — acceptable for the simplicity gain
