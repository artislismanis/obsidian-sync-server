from fastapi import FastAPI

from obsidian_sync import __version__
from obsidian_sync.config import settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        docs_url="/api/docs" if settings.debug else None,
        redoc_url="/api/redoc" if settings.debug else None,
    )

    @app.get("/api/v1/health")
    async def health() -> dict[str, str]:
        return {
            "status": "healthy",
            "version": __version__,
            "mode": settings.deployment_mode,
        }

    return app


app = create_app()
