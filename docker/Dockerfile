# Stage 1: Build portal
FROM node:20-slim AS portal-builder
WORKDIR /app/portal
COPY portal/package.json portal/package-lock.json* ./
RUN npm ci
COPY portal/ ./
RUN npm run build

# Stage 2: Server + portal assets
FROM python:3.11-slim AS server
WORKDIR /app

# Copy server project files first (for dependency install)
COPY server/ ./server/

# Install server package
RUN pip install --no-cache-dir ./server

# Copy portal build artifacts
COPY --from=portal-builder /app/portal/dist/ ./static/

# Copy alembic config
COPY server/alembic.ini ./alembic.ini
COPY server/alembic/ ./alembic/

# Create data directory
RUN mkdir -p /app/data /app/data/vaults

ENV OSS_DEPLOYMENT_MODE=self_hosted
ENV OSS_DATABASE_URL=sqlite+aiosqlite:////app/data/obsidian-sync.db
ENV OSS_STORAGE_LOCAL_PATH=/app/data/vaults

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:8000/api/v1/health'); r.raise_for_status()"

CMD ["uvicorn", "obsidian_sync.main:app", "--host", "0.0.0.0", "--port", "8000"]
