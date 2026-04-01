"""Health check and metrics router."""

from fastapi import APIRouter

from obsidian_sync import __version__
from obsidian_sync.config import settings

router = APIRouter(tags=["system"])


@router.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {
        "status": "healthy",
        "version": __version__,
        "mode": settings.deployment_mode,
    }
