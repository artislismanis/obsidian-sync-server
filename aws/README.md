# AWS Deployment — Obsidian Sync Server

## Architecture (Lambda + Fargate Hybrid)

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
        SQS → Lambda                        ← Background jobs
```

## Why This Architecture?

- **Lambda for REST**: $0 at idle, auto-scales, handles ~90% of API traffic
- **Fargate for WebSocket**: Persistent connections need long-lived processes
- **Aurora over DynamoDB**: Relational data model, same SQLAlchemy code as self-hosted
- **Same codebase**: Env vars control deployment mode — no code changes needed

## Cost Estimates

| Scale | Monthly Cost |
|-------|-------------|
| 1-10 users | ~$25-35 |
| 100 users | ~$60-120 |
| 1000+ users | ~$200-400 |

## Prerequisites

- AWS CLI configured
- Python 3.11+
- AWS CDK CLI: `npm install -g aws-cdk`

## Deployment

CDK stacks will be implemented in Phase 11 (Production Readiness).

```bash
cd aws/cdk
pip install -r requirements.txt
cdk deploy --all
```

## Environment Variables

```
DEPLOYMENT_MODE=saas
DATABASE_URL=postgresql+asyncpg://user:pass@aurora-endpoint:5432/obsidian_sync
STORAGE_BACKEND=s3
S3_BUCKET=obsidian-sync-vaults
AWS_REGION=eu-west-1
STRIPE_SECRET_KEY=sk_live_...
```
