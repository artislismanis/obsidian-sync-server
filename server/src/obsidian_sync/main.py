"""FastAPI application factory."""

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from obsidian_sync import __version__
from obsidian_sync.config import settings
from obsidian_sync.database import engine
from obsidian_sync.models import Base

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create database tables on startup (dev convenience). Use Alembic in production."""
    if settings.secret_key == "change-me-in-production":
        logger.warning(
            "SECURITY WARNING: Using default secret_key. "
            "Set OSS_SECRET_KEY to a random string (min 32 chars) in production."
        )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        docs_url="/api/docs" if settings.debug else None,
        redoc_url="/api/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    # Register routers
    from obsidian_sync.routers.health import router as health_router
    from obsidian_sync.routers.auth import router as auth_router
    from obsidian_sync.routers.oauth import router as oauth_router
    from obsidian_sync.routers.users import router as users_router
    from obsidian_sync.routers.vaults import router as vaults_router
    from obsidian_sync.routers.sharing import router as sharing_router
    from obsidian_sync.routers.history import router as history_router
    from obsidian_sync.routers.admin import router as admin_router
    from obsidian_sync.routers.billing import router as billing_router
    from obsidian_sync.routers.gdpr import router as gdpr_router
    from obsidian_sync.routers.sync_ws import router as sync_ws_router
    from obsidian_sync.routers.external_sync import router as external_sync_router

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(oauth_router)
    app.include_router(users_router)
    app.include_router(vaults_router)
    app.include_router(sharing_router)
    app.include_router(history_router)
    app.include_router(admin_router)
    app.include_router(billing_router)
    app.include_router(gdpr_router)
    app.include_router(sync_ws_router)
    app.include_router(external_sync_router)

    # Rate limiting middleware (sliding window, in-memory for self-hosted mode)
    from obsidian_sync.middleware.rate_limit import RateLimitMiddleware

    app.add_middleware(RateLimitMiddleware)

    # Serve portal static files (built React SPA)
    import os
    from pathlib import Path
    static_dir = Path(os.environ.get("OSS_STATIC_DIR", "/app/static"))
    if static_dir.is_dir():
        from starlette.staticfiles import StaticFiles
        from starlette.responses import FileResponse

        @app.get("/")
        async def serve_index():
            return FileResponse(static_dir / "index.html")

        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="portal-assets")

        @app.get("/{path:path}")
        async def serve_spa(path: str):
            file = static_dir / path
            if file.is_file():
                return FileResponse(file)
            return FileResponse(static_dir / "index.html")

    return app


app = create_app()
