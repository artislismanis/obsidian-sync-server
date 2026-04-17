# Obsidian Sync Server

Self-hosted vault synchronization for [Obsidian](https://obsidian.md). Sync your notes across devices through your own server — on a Synology NAS, a VPS, or anywhere Docker runs.

## What It Does

- **On-save sync** — changes propagate to all connected devices within seconds
- **Live sync** — real-time CRDT-based sync as you type (Yjs)
- **Multi-user** — share vaults with teammates at different permission levels (owner/admin/write/read)
- **Per-vault encryption** — client-side AES-256-GCM; the server never sees plaintext
- **Share links** — signed, expiring, optionally password-protected links to files
- **File history** — version tracking with diff and restore
- **Web portal** — browse vaults, manage sharing, view files in a browser
- **CLI client** — headless sync for servers, cron jobs, CI pipelines
- **Pluggable storage** — local filesystem or S3-compatible (MinIO, Backblaze B2, AWS S3)
- **SaaS mode** — optional Stripe billing, entitlements, and multi-tenant support

## Quick Start (5 minutes)

### 1. Start the server

```bash
git clone https://github.com/your-org/obsidian-sync-server.git
cd obsidian-sync-server/docker
cp .env.example .env
```

Edit `.env` — at minimum change the secret key:

```env
OSS_SECRET_KEY=your-random-secret-key-at-least-32-chars-long
OSS_DEBUG=true   # enables API docs at /api/docs — disable in production
```

Start the server:

```bash
docker compose up -d
```

The server is now running behind Caddy at `https://localhost` with auto-TLS.

### 2. Create your admin account

```bash
curl -k -X POST https://localhost/api/v1/auth/setup \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "your-secure-password",
    "email": "you@example.com"
  }'
```

Save the `access_token` and `refresh_token` from the response.

### 3. Install the Obsidian plugin

```bash
cd plugin
npm install && npm run build
```

Copy `main.js` and `manifest.json` into your Obsidian vault:

```bash
mkdir -p /path/to/your-vault/.obsidian/plugins/obsidian-sync
cp main.js manifest.json /path/to/your-vault/.obsidian/plugins/obsidian-sync/
```

In Obsidian:
1. Settings → Community Plugins → enable "Obsidian Sync"
2. Settings → Obsidian Sync → enter your server URL (`https://your-server`)
3. Enter your username and password, click Login
4. Set a Vault ID (create one via the API first — see below)

### 4. Create a vault and start syncing

```bash
# Create a vault
curl -k -X POST https://localhost/api/v1/vaults \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "My Notes"}'
```

Copy the vault `id` from the response and paste it into the plugin settings. Sync starts automatically.

---

## Synology NAS Setup

### Using SSH

```bash
ssh admin@your-nas-ip
git clone https://github.com/your-org/obsidian-sync-server.git
cd obsidian-sync-server/docker
cp .env.example .env
# Edit .env with your settings
docker compose up -d
```

### Using Container Manager (DSM 7+)

1. Install **Container Manager** from Package Center
2. Upload the Docker Compose file via **Project** → **Create** → **Import**
3. Upload `docker-compose.yml`, `Caddyfile`, and `.env`
4. Start the project

### Exposing to the Internet

To access from outside your LAN:

1. Set `DOMAIN=sync.yourdomain.com` in `.env`
2. Port-forward 443 on your router to the NAS
3. Point your DNS to your home IP (or use a dynamic DNS service)
4. Caddy handles TLS certificates automatically via Let's Encrypt

For LAN-only use, `https://your-nas-ip` works with Caddy's self-signed certificate.

---

## Cloud/VPS Deployment

### Any VPS with Docker

```bash
ssh root@your-vps
git clone https://github.com/your-org/obsidian-sync-server.git
cd obsidian-sync-server/docker
cp .env.example .env
# Edit .env — set DOMAIN to your domain, set a real SECRET_KEY
docker compose up -d
```

### AWS (SaaS Mode)

For multi-tenant SaaS deployment using AWS managed services:

```bash
cd aws/cdk
pip install -r requirements.txt
cdk deploy --all
```

This deploys:
- **ECS Fargate** — FastAPI server with WebSocket support
- **ALB** — load balancer with 4000s idle timeout for WebSocket
- **Aurora Serverless** — PostgreSQL database
- **S3** — vault file storage
- **CloudFront** — CDN for the web portal

See `aws/README.md` for architecture details and cost estimates.

---

## CLI Client

For headless sync on servers, NAS cron jobs, or CI pipelines:

```bash
cd cli
pip install -e .

# Login
oss login https://your-server

# Sync a local directory to a vault
oss sync /path/to/notes --vault YOUR_VAULT_ID

# Pull latest from server
oss pull --vault YOUR_VAULT_ID

# Push local changes
oss push --vault YOUR_VAULT_ID

# Watch mode — continuous sync via file watcher
oss watch --vault YOUR_VAULT_ID

# Show status
oss status
```

### Encrypted vaults

```bash
# Pull with decryption
oss pull --vault YOUR_VAULT_ID --encrypted

# Push with encryption
oss push --vault YOUR_VAULT_ID --encrypted

# Or set the passphrase via environment variable
export OSS_VAULT_PASSPHRASE="your-vault-passphrase"
oss sync /path/to/notes --vault YOUR_VAULT_ID --encrypted
```

---

## Web Portal

The web portal is bundled into the Docker image and served at the root URL.

- **Dashboard** — view all your vaults
- **Vault browser** — navigate file tree, view markdown files
- **File history** — see version history, diffs, restore previous versions
- **Sharing** — manage vault access, create share links
- **Admin** — user management, server stats, audit log
- **Billing** — subscription management (SaaS mode only)

For development:

```bash
cd portal
npm install
npm run dev   # Vite dev server at http://localhost:5173
```

---

## Configuration

All settings are via environment variables (prefixed `OSS_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `OSS_SECRET_KEY` | `change-me-in-production` | JWT signing key (min 32 chars) |
| `OSS_DEPLOYMENT_MODE` | `self_hosted` | `self_hosted` or `saas` |
| `OSS_DATABASE_URL` | `sqlite+aiosqlite:///data/obsidian-sync.db` | Database URL |
| `OSS_STORAGE_BACKEND` | `local` | `local` or `s3` |
| `OSS_STORAGE_LOCAL_PATH` | `data/vaults` | Local storage path |
| `OSS_DEBUG` | `false` | Enable API docs at `/api/docs` |
| `OSS_S3_BUCKET` | | S3 bucket name |
| `OSS_S3_REGION` | | S3 region |
| `OSS_GOOGLE_CLIENT_ID` | | Google OAuth client ID |
| `OSS_GOOGLE_CLIENT_SECRET` | | Google OAuth secret |
| `OSS_GITHUB_CLIENT_ID` | | GitHub OAuth client ID |
| `OSS_GITHUB_CLIENT_SECRET` | | GitHub OAuth secret |
| `OSS_STRIPE_SECRET_KEY` | | Stripe API key (SaaS only) |
| `OSS_STRIPE_WEBHOOK_SECRET` | | Stripe webhook secret |

### Self-hosted vs SaaS

When `OSS_DEPLOYMENT_MODE=self_hosted` (default):
- All features are unlocked (no billing limits)
- Billing endpoints return 404
- No Stripe dependency needed
- SQLite works fine

When `OSS_DEPLOYMENT_MODE=saas`:
- Subscription tiers control feature access (free/pro/team)
- Stripe handles payments
- Use PostgreSQL for concurrency

---

## API Overview

The server exposes a REST API at `/api/v1/` and a WebSocket endpoint for real-time sync.

When `OSS_DEBUG=true`, interactive API docs are at `/api/docs`.

### Key endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/auth/setup` | First-run admin account creation |
| `POST /api/v1/auth/login` | Login, returns JWT tokens |
| `GET /api/v1/vaults` | List your vaults |
| `POST /api/v1/vaults` | Create a vault |
| `PUT /api/v1/vaults/{id}/files/{path}` | Upload a file |
| `GET /api/v1/vaults/{id}/files/{path}` | Download a file |
| `GET /api/v1/vaults/{id}/files/{path}/history` | File version history |
| `WS /api/v1/sync/{vault_id}?token=JWT` | WebSocket sync |
| `POST /api/v1/vaults/{id}/sharing` | Share vault with a user |
| `POST /api/v1/vaults/{id}/share-links` | Create a share link |
| `GET /api/v1/admin/stats` | Server statistics (admin) |
| `GET /api/v1/account/export` | GDPR data export |

---

## Development

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (for deployment testing)

### Server

```bash
cd server
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
OSS_DEBUG=true uvicorn obsidian_sync.main:app --reload --port 8000
pytest -v   # 89 tests
```

### Plugin

```bash
cd plugin
npm install
npm run dev    # watch mode
npm run build  # production build → main.js
```

### Portal

```bash
cd portal
npm install
npm run dev    # Vite dev server at :5173
npm run build  # production → dist/
```

### CLI

```bash
cd cli
pip install -e ".[dev]"
oss --help
pytest
```

---

## Backup & Restore

### SQLite (default)

```bash
# Backup
docker compose exec server cp /app/data/obsidian-sync.db /app/data/backup.db

# Or from host
docker cp obsidian-sync-server-server-1:/app/data/obsidian-sync.db ./backup.db
```

### Full backup

```bash
docker compose stop
docker run --rm -v obsidian-sync-server_sync-data:/data -v $(pwd):/backup \
  alpine tar czf /backup/obsidian-sync-backup.tar.gz -C /data .
docker compose start
```

---

## Architecture

```
Obsidian Plugin ←┐
CLI Client      ←┼→ WebSocket/REST ←→ FastAPI Server ←→ Storage Backend
Web Portal      ←┘                          ↕                    ↕
                                       SQLite/PG           Local | S3
                                          ↕
                                   External Sync
                                   (GDrive | OneDrive)
```

| Component | Tech |
|-----------|------|
| Server | Python 3.11, FastAPI, SQLAlchemy async |
| Plugin | TypeScript, Obsidian Plugin API |
| Portal | React 18, Vite |
| CLI | Python, Typer, httpx |
| Real-time | WebSocket + Yjs CRDT |
| Auth | JWT + bcrypt + OAuth (Google/GitHub) |
| Encryption | AES-256-GCM, PBKDF2 key derivation |
| Deployment | Docker + Caddy, or AWS CDK |

---

## License

MIT
