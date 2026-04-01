"""FastAPI application factory."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from obsidian_sync import __version__
from obsidian_sync.config import settings
from obsidian_sync.database import engine
from obsidian_sync.models import Base


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create database tables on startup (dev convenience). Use Alembic in production."""
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

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(vaults_router)

    return app


app = create_app()
