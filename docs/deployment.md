# Deployment Guide

## Quick Start (Docker)

The fastest way to get running:

```bash
cd docker
cp .env.example .env
# Edit .env with your settings (at minimum, change SECRET_KEY)
docker compose up -d
```

The server will be available at `https://localhost` (Caddy provides auto-TLS).

## First-Run Setup

1. Open `https://your-server/api/docs` (or use curl)
2. Create your admin account:

```bash
curl -X POST https://your-server/api/v1/auth/setup \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-secure-password", "email": "admin@example.com"}'
```

3. Install the Obsidian plugin, enter your server URL, and log in.

## Synology NAS

1. Install Docker via Synology Package Center
2. SSH into your NAS or use Container Manager
3. Clone the repo and run:

```bash
cd docker
docker compose up -d
```

For Synology DSM 7+, you can also import the compose file via Container Manager UI.

**Architecture**: The Docker image supports both amd64 and arm64, covering all modern Synology models.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OSS_SECRET_KEY` | `change-me-in-production` | JWT signing key (min 32 chars) |
| `OSS_DEPLOYMENT_MODE` | `self_hosted` | `self_hosted` or `saas` |
| `OSS_DATABASE_URL` | `sqlite+aiosqlite:///data/obsidian-sync.db` | Database connection string |
| `OSS_STORAGE_BACKEND` | `local` | Default storage backend |
| `OSS_STORAGE_LOCAL_PATH` | `data/vaults` | Local storage directory |
| `OSS_DEBUG` | `false` | Enable debug mode (API docs at /api/docs) |
| `OSS_S3_BUCKET` | | S3 bucket name |
| `OSS_S3_REGION` | | S3 region |
| `OSS_GOOGLE_CLIENT_ID` | | Google OAuth client ID |
| `OSS_GOOGLE_CLIENT_SECRET` | | Google OAuth client secret |
| `OSS_GITHUB_CLIENT_ID` | | GitHub OAuth client ID |
| `OSS_GITHUB_CLIENT_SECRET` | | GitHub OAuth client secret |
| `OSS_STRIPE_SECRET_KEY` | | Stripe API key (SaaS mode) |
| `OSS_STRIPE_WEBHOOK_SECRET` | | Stripe webhook signing secret |

## PostgreSQL (Optional)

For higher concurrency or SaaS deployment:

```bash
# In .env:
OSS_DATABASE_URL=postgresql+asyncpg://user:password@postgres:5432/obsidian_sync
```

Use `docker-compose.full.yml` which includes a PostgreSQL container.

## AWS Deployment (SaaS)

See `aws/README.md` for CDK-based deployment using:
- Lambda (REST APIs via Mangum)
- Fargate (WebSocket sync)
- Aurora Serverless PostgreSQL
- S3 (vault storage)
- CloudFront (portal CDN)

## CLI Client

Install the headless sync client:

```bash
pip install obsidian-sync-cli
oss login https://your-server
oss sync /path/to/vault --vault your-vault-id
oss watch --vault your-vault-id  # daemon mode
```

## Backup

### SQLite
```bash
# Copy the database file
cp data/obsidian-sync.db backup/
```

### Vault Data
```bash
# Copy vault storage
cp -r data/vaults/ backup/vaults/
```

### Full Docker Backup
```bash
docker compose stop
tar czf obsidian-sync-backup.tar.gz data/
docker compose start
```
