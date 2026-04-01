"""Tests for rate limiting middleware."""

import pytest
from httpx import AsyncClient

from obsidian_sync.middleware.rate_limit import (
    TIER_IP_AUTH,
    get_store,
)


# ------------------------------------------------------------------
# Requests under limit succeed
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_requests_under_limit_succeed(client: AsyncClient) -> None:
    """Normal requests should succeed when under the rate limit."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200


# ------------------------------------------------------------------
# Rate limit headers are present
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limit_headers_present(client: AsyncClient) -> None:
    """Every response should include X-RateLimit-* headers."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers
    assert "X-RateLimit-Reset" in response.headers


# ------------------------------------------------------------------
# IP-based limiting on auth endpoints
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auth_ip_rate_limit_blocks_after_threshold(client: AsyncClient) -> None:
    """Auth endpoints should return 429 after exceeding per-IP limit."""
    ip_limit, _ = TIER_IP_AUTH

    # Exhaust the per-IP limit on the login endpoint
    for _ in range(ip_limit):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "nobody", "password": "wrong"},
        )
        # Should be 401 (bad creds) – not 429 yet
        assert resp.status_code == 401

    # Next request should be rate-limited
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "nobody", "password": "wrong"},
    )
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    assert resp.json()["detail"] == "Too many requests"


@pytest.mark.asyncio
async def test_auth_rate_limit_has_correct_headers(client: AsyncClient) -> None:
    """429 responses on auth endpoints should include all rate-limit headers."""
    ip_limit, _ = TIER_IP_AUTH

    for _ in range(ip_limit):
        await client.post(
            "/api/v1/auth/login",
            json={"username": "nobody", "password": "wrong"},
        )

    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "nobody", "password": "wrong"},
    )
    assert resp.status_code == 429
    assert "X-RateLimit-Limit" in resp.headers
    assert "X-RateLimit-Remaining" in resp.headers
    assert "X-RateLimit-Reset" in resp.headers
    assert resp.headers["X-RateLimit-Remaining"] == "0"


@pytest.mark.asyncio
async def test_auth_rate_limit_per_endpoint(client: AsyncClient) -> None:
    """Rate limits on /login should not affect /setup (separate keys)."""
    ip_limit, _ = TIER_IP_AUTH

    # Exhaust login limit
    for _ in range(ip_limit):
        await client.post(
            "/api/v1/auth/login",
            json={"username": "nobody", "password": "wrong"},
        )

    # /setup should still work (different key)
    resp = await client.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": "securepass123"},
    )
    assert resp.status_code == 201


# ------------------------------------------------------------------
# Requests over limit get 429
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_over_limit_returns_429(client: AsyncClient) -> None:
    """Exceeding the per-IP auth limit should yield a 429 with Retry-After."""
    ip_limit, _ = TIER_IP_AUTH

    for _ in range(ip_limit):
        await client.post(
            "/api/v1/auth/login",
            json={"username": "x", "password": "y"},
        )

    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "x", "password": "y"},
    )
    assert resp.status_code == 429
    retry_after = int(resp.headers["Retry-After"])
    assert retry_after > 0
