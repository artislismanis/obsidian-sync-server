# Obsidian Sync Server — Project Constitution

**Version**: 2.0
**Date**: 2026-04-01

## 1. Project Identity

**Obsidian Sync Server** (OSS) is a synchronization platform for Obsidian vaults that operates in two modes:

- **Self-hosted**: Docker deployment on personal hardware (Synology NAS, VPS, etc.)
- **Hosted SaaS**: Multi-tenant deployment with subscription billing

It consists of four deliverables:

- **Server**: A Python (FastAPI) backend providing sync APIs, storage abstraction, user management, and platform services
- **Plugin**: An Obsidian plugin (TypeScript) that connects vaults to the server
- **Portal**: A React SPA for vault browsing, sharing, administration, and billing
- **CLI**: A Python command-line client for headless vault sync (servers, CI, NAS cron jobs, non-Obsidian users)

## 2. Core Principles

### P1: Dual-Mode Architecture
Every feature must work in both self-hosted and SaaS modes. Feature flags control what's available. The self-hosted experience must not degrade to push users toward SaaS — it's a first-class deployment target.

### P2: Data Sovereignty
Users choose where their data lives — local filesystem, their own S3 bucket, or platform-managed storage. Vault data is encrypted at rest with per-vault keys. Users can export all their data at any time in a standard format.

### P3: Obsidian-Native Experience
The plugin must feel like a natural part of Obsidian. No separate apps for core sync functionality. The web portal is supplementary — for sharing, admin, and file browsing when Obsidian isn't available.

### P4: Correctness Over Speed
Sync conflicts must never silently lose data. When in doubt, preserve both versions. This applies to all sync targets: primary server, external services (GDrive, OneDrive), and BYO storage backends.

### P5: Simple Self-Hosted Operations
`docker compose up` and it works. SQLite by default, PostgreSQL as an option. Minimal configuration for basic operation. Complex features (external sync, custom storage) are opt-in.

### P6: Pluggable Storage
The storage layer is an abstraction. Vaults can independently target different backends (local, S3, GCS, Azure Blob). Adding a new storage backend should require implementing one interface.

### P7: Security by Default
Per-vault encryption with user-held keys. JWT auth with token rotation. ACL enforced server-side on every operation. Share links are signed, time-limited, and revocable. No security feature should be opt-in — the safe path is the default path.

## 3. Technical Constraints

### Language & Frameworks
- **Server**: Python 3.11+, FastAPI, SQLAlchemy (async), SQLite (aiosqlite) or PostgreSQL (asyncpg)
- **Plugin**: TypeScript, Obsidian Plugin API
- **Portal**: React 18+, Vite, TanStack Router/Query, served as static assets
- **Transport**: WebSocket for real-time sync, REST for management APIs
- **Auth**: JWT tokens with refresh rotation
- **Encryption**: AES-256-GCM for vault at-rest encryption, keys derived from user passphrase via Argon2
- **Payments**: Stripe (subscriptions + usage-based)
- **Packaging**: Docker (multi-arch: amd64, arm64)

### Database Strategy
- SQLAlchemy async with dialect abstraction from day one
- SQLite for self-hosted (default) — WAL mode, single-file simplicity
- PostgreSQL for SaaS and high-concurrency self-hosted — configurable via env var
- Alembic for migrations, dialect-aware

### Testing Requirements
- Server: pytest with async support, 80%+ coverage on core sync and ACL logic
- Portal: Vitest + React Testing Library
- Plugin: Jest for unit tests
- Integration: Docker Compose test matrix (SQLite + PostgreSQL)
- E2E: Playwright for portal critical paths

### Code Style
- Server: Black formatter, ruff linter, type hints everywhere
- Portal: ESLint + Prettier, strict TypeScript
- Plugin: ESLint + Prettier, strict TypeScript (no `any`)
- Commits: Conventional commits format

## 4. Architecture Overview

### Monorepo Structure
```
/
├── server/              # Python FastAPI server
│   └── src/obsidian_sync/
│       ├── core/        # Sync engine, CRDT, conflict resolution
│       ├── storage/     # Pluggable storage backends
│       ├── auth/        # JWT, ACL, share links
│       ├── platform/    # Billing, external sync, portal API
│       ├── models/      # SQLAlchemy models
│       ├── routers/     # API endpoints
│       └── services/    # Business logic
├── portal/              # React SPA (vault browser, admin, billing)
├── plugin/              # Obsidian TypeScript plugin
├── cli/                 # Python CLI client (headless sync)
├── docker/              # Dockerfiles and compose configs
├── docs/                # User and developer documentation
├── .speckit/            # Spec-driven development artifacts
└── CLAUDE.md            # AI agent instructions
```

### Data Flow
```
Obsidian Plugin ←┐
CLI Client      ←┼→ WebSocket/REST ←→ FastAPI Server ←→ Storage Backend
Web Portal      ←┘                          ↕                    ↕
                                       SQLite/PG           Local|S3|GCS|...
                                          ↕
                                   External Sync
                                   (GDrive|OneDrive)
                                          ↕
                                   Web Portal (React)
```

### Deployment Modes

| Aspect | Self-Hosted | SaaS |
|--------|-------------|------|
| Database | SQLite (default) | PostgreSQL |
| Storage | Local filesystem | S3 (managed) or BYO |
| Auth | Local accounts | Local + OAuth (future) |
| Billing | Disabled | Stripe |
| External sync | Available | Available |
| Portal | Bundled in Docker | CDN-hosted |
| TLS | Caddy auto-cert | Cloud LB |
| Updates | Manual / Watchtower | Rolling deploy |

## 5. Development Workflow

1. **Specify** → Define requirements in `.speckit/spec.md`
2. **Plan** → Technical design in `.speckit/plan.md`
3. **Tasks** → Breakdown in `.speckit/tasks.md`
4. **Implement** → Code against tasks, test, iterate
5. **Review** → PR-based review with spec compliance check

## 6. Non-Goals (MVP)

- OAuth / SSO login (post-MVP, local accounts only)
- Mobile app (web portal works on mobile browsers)
- Multi-server federation
- Plugin marketplace distribution
- Bidirectional external sync (mirror-out first, bidirectional later)
- Real-time collaborative cursors / presence indicators
