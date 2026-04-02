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
    from obsidian_sync.routers.vaults import router as vaults_router
    from obsidian_sync.routers.sharing import router as sharing_router

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(vaults_router)
    app.include_router(sharing_router)

    # Rate limiting middleware (sliding window, in-memory for self-hosted mode)
    from obsidian_sync.middleware.rate_limit import RateLimitMiddleware

    app.add_middleware(RateLimitMiddleware)

    return app


app = create_app()
