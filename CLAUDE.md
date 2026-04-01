# Obsidian Sync Server — Agent Instructions

## Project Overview

Self-hosted + SaaS synchronization platform for Obsidian vaults. Four deliverables:

1. **Server** (`server/`) — Python FastAPI backend
2. **Plugin** (`plugin/`) — Obsidian TypeScript plugin
3. **Portal** (`portal/`) — React SPA (vault browser, admin, billing)
4. **CLI** (`cli/`) — Python command-line sync client

## Spec-Driven Development

Read these files before starting any implementation work:

- `.speckit/constitution.md` — Project principles and constraints
- `.speckit/spec.md` — Feature specification (user scenarios, requirements, data entities)
- `.speckit/plan.md` — Technical architecture, API design, project structure
- `.speckit/tasks.md` — Phased task breakdown with dependencies

Follow the task phases in order. Check task dependencies before starting work.

## Tech Stack

| Component | Stack |
|-----------|-------|
| Server | Python 3.11+, FastAPI, SQLAlchemy async, Alembic |
| Database | SQLite (aiosqlite) or PostgreSQL (asyncpg) — configurable |
| Real-time | WebSocket + Yjs (pycrdt) |
| Auth | JWT (PyJWT), bcrypt, Argon2id (encryption), OAuth (Authlib) |
| Plugin | TypeScript, Obsidian Plugin API, esbuild |
| Portal | React 18, Vite, TanStack Router/Query |
| CLI | Python, Typer, httpx, watchfiles |
| Docker | Multi-stage build, Caddy reverse proxy |
| AWS | Lambda (Mangum) + Fargate + ALB + Aurora + S3 + CloudFront |
| IaC | AWS CDK (Python) |
| Payments | Stripe (SaaS mode only) |

## Development Commands

### Server
```bash
cd server
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn obsidian_sync.main:app --reload --port 8000
pytest
ruff check src/
black --check src/
```

### Plugin
```bash
cd plugin
npm install
npm run dev      # watch mode build
npm run build    # production build
npm run test
npm run lint
```

### Portal
```bash
cd portal
npm install
npm run dev      # Vite dev server (port 5173)
npm run build    # Production build → dist/
npm run test
npm run lint
```

### CLI
```bash
cd cli
pip install -e ".[dev]"
oss --help
pytest
```

### Docker
```bash
cd docker
docker compose up -d              # Production (server + Caddy)
docker compose -f docker-compose.dev.yml up  # Dev (hot reload)
```

## Code Conventions

### Python (server + CLI)
- Formatter: `black`
- Linter: `ruff`
- Type hints on all functions
- Async everywhere (no sync DB calls)
- Pydantic models for all API schemas
- SQLAlchemy models in `models/`, business logic in `services/`

### TypeScript (plugin + portal)
- ESLint + Prettier
- Strict mode (`strict: true` in tsconfig)
- No `any` types
- Plugin: follow Obsidian plugin conventions (Plugin class, PluginSettingTab)

### Git
- Conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `chore:`
- Branch per feature/task phase
- PR required for merging to main

## Architecture Notes

### Storage Abstraction
All file I/O goes through `StorageBackend` protocol. Never access filesystem directly for vault data. See `server/src/obsidian_sync/storage/`.

### Encryption
Client-side only. Server never sees plaintext. Plugin, CLI, and portal all implement the same algorithm (Argon2id → AES-256-GCM). Crypto code must produce identical output across all three clients.

### Dual-Mode (Self-Hosted vs SaaS)
Controlled by environment variables. Key toggle: `DEPLOYMENT_MODE=self_hosted|saas`. When `self_hosted`:
- Billing routes return 404
- Entitlement engine returns unlimited
- No Stripe dependency needed

### AWS Deployment
SaaS mode uses Lambda + Fargate hybrid. See `aws/README.md`. Lambda (via Mangum) handles REST APIs; Fargate handles WebSocket sync. Same codebase — env vars control everything.

### Mobile Plugin
Plugin must work on Obsidian mobile (iOS/Android). Use `Platform.isMobileApp` for detection. Adaptive sync profiles: larger debounce, fewer concurrent uploads, WiFi-only for large files, battery-aware throttling. Never use Node.js or Electron APIs.

### Database
SQLAlchemy async with dialect abstraction. Use `DATABASE_URL` env var. Test with both SQLite and PostgreSQL before merging.

## Testing

- Server: `pytest` with `pytest-asyncio`, use `httpx.AsyncClient` for API tests
- Always test both SQLite and PostgreSQL paths for DB-dependent code
- Mock external services (S3, Stripe, Google Drive, OneDrive) in tests
- Encryption: cross-client compatibility tests (same plaintext + key → same ciphertext format)
