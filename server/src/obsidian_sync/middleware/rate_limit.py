"""Rate limiting middleware: sliding window algorithm with per-IP, per-user, and global tiers."""

import time
from collections import defaultdict
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from obsidian_sync.middleware.auth import get_current_user

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Auth endpoints get strict per-IP limiting (brute-force protection)
AUTH_PATHS = {"/api/v1/auth/login", "/api/v1/auth/setup", "/api/v1/auth/refresh"}

# Tier definitions: (max_requests, window_seconds)
TIER_IP_AUTH = (5, 60)       # 5 requests per minute on auth endpoints per IP
TIER_USER = (100, 60)        # 100 requests per minute per user
TIER_GLOBAL = (10000, 60)    # 10 000 requests per minute globally

# ---------------------------------------------------------------------------
# Sliding-window store (in-memory, suitable for self-hosted single-process)
# ---------------------------------------------------------------------------


class _SlidingWindowStore:
    """Thread-safe-ish sliding window counter backed by a plain dict.

    Each key maps to a list of timestamps (floats).  On every check we
    prune entries older than the window.
    """

    def __init__(self) -> None:
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def hit(self, key: str, limit: int, window: int) -> tuple[bool, int, float]:
        """Record a hit and return (allowed, remaining, reset_timestamp).

        *allowed* is ``True`` when the request should proceed.
        """
        now = time.time()
        cutoff = now - window

        # Prune expired entries
        entries = self._buckets[key]
        self._buckets[key] = entries = [t for t in entries if t > cutoff]

        remaining = max(0, limit - len(entries) - 1)
        reset_at = now + window

        if len(entries) >= limit:
            # Already at the limit – reject
            return False, 0, reset_at

        entries.append(now)
        return True, remaining, reset_at

    def clear(self) -> None:
        self._buckets.clear()


_store = _SlidingWindowStore()


def get_store() -> _SlidingWindowStore:
    """Return the module-level store (useful for resetting in tests)."""
    return _store


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


async def check_rate_limit(request: Request) -> None:
    """FastAPI dependency that enforces per-user and global rate limits.

    Per-IP auth limiting is handled in the middleware layer so that it
    fires *before* route dependencies (which may touch the DB).
    """
    # --- global tier ---
    g_limit, g_window = TIER_GLOBAL
    allowed, remaining, reset_at = _store.hit("global", g_limit, g_window)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Global rate limit exceeded",
            headers={
                "Retry-After": str(g_window),
                "X-RateLimit-Limit": str(g_limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(reset_at)),
            },
        )

    # --- per-user tier (only when user is authenticated) ---
    # We peek at state set by the middleware; the auth dependency runs later.
    user_id: str | None = getattr(request.state, "rate_limit_user_id", None)
    if user_id:
        u_limit, u_window = TIER_USER
        allowed, remaining, reset_at = _store.hit(f"user:{user_id}", u_limit, u_window)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Per-user rate limit exceeded",
                headers={
                    "Retry-After": str(u_window),
                    "X-RateLimit-Limit": str(u_limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(reset_at)),
                },
            )


# ---------------------------------------------------------------------------
# Starlette middleware (applied globally)
# ---------------------------------------------------------------------------


class RateLimitMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that enforces per-IP rate limits on auth endpoints
    and injects rate-limit response headers on every response.
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path

        # --- Per-IP auth tier ---
        if path in AUTH_PATHS:
            ip_limit, ip_window = TIER_IP_AUTH
            allowed, remaining, reset_at = _store.hit(
                f"ip:{client_ip}:{path}", ip_limit, ip_window
            )
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests"},
                    headers={
                        "Retry-After": str(ip_window),
                        "X-RateLimit-Limit": str(ip_limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(reset_at)),
                    },
                )

        # --- Global tier (checked early to short-circuit) ---
        g_limit, g_window = TIER_GLOBAL
        allowed, g_remaining, g_reset_at = _store.hit("global", g_limit, g_window)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Global rate limit exceeded"},
                headers={
                    "Retry-After": str(g_window),
                    "X-RateLimit-Limit": str(g_limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(g_reset_at)),
                },
            )

        response: Response = await call_next(request)

        # Attach informational headers to every response
        response.headers["X-RateLimit-Limit"] = str(g_limit)
        response.headers["X-RateLimit-Remaining"] = str(g_remaining)
        response.headers["X-RateLimit-Reset"] = str(int(g_reset_at))

        return response
