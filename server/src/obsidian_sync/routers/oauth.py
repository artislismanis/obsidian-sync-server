"""OAuth login router: Google and GitHub authentication via Authlib."""

from datetime import datetime, timezone

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from obsidian_sync.config import settings
from obsidian_sync.database import get_db
from obsidian_sync.models.user import User
from obsidian_sync.services.auth import (
    create_access_token,
    create_refresh_token,
    hash_password,
)

router = APIRouter(prefix="/api/v1/auth/oauth", tags=["oauth"])

oauth = OAuth()

if settings.google_client_id:
    oauth.register(
        name="google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

if settings.github_client_id:
    oauth.register(
        name="github",
        client_id=settings.github_client_id,
        client_secret=settings.github_client_secret,
        access_token_url="https://github.com/login/oauth/access_token",
        authorize_url="https://github.com/login/oauth/authorize",
        api_base_url="https://api.github.com/",
        client_kwargs={"scope": "user:email"},
    )


@router.get("/{provider}")
async def oauth_login(provider: str, request: Request) -> RedirectResponse:
    """Initiate OAuth flow — redirects to provider."""
    client = oauth.create_client(provider)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OAuth provider '{provider}' not configured")

    redirect_uri = str(request.url_for("oauth_callback", provider=provider))
    return await client.authorize_redirect(request, redirect_uri)


@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str, request: Request, db: AsyncSession = Depends(get_db)
) -> dict:
    """OAuth callback — exchanges code for tokens, creates/links user account."""
    client = oauth.create_client(provider)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OAuth provider '{provider}' not configured")

    try:
        token = await client.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"OAuth error: {e}")

    # Get user info from provider
    if provider == "google":
        userinfo = token.get("userinfo", {})
        oauth_id = userinfo.get("sub", "")
        email = userinfo.get("email", "")
        name = userinfo.get("name", email.split("@")[0])
    elif provider == "github":
        resp = await client.get("user", token=token)
        github_user = resp.json()
        oauth_id = str(github_user.get("id", ""))
        email = github_user.get("email", "")
        name = github_user.get("login", "")
        if not email:
            emails_resp = await client.get("user/emails", token=token)
            emails = emails_resp.json()
            primary = next((e for e in emails if e.get("primary")), None)
            email = primary["email"] if primary else ""
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported provider")

    if not oauth_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not get user ID from provider")

    # Find or create user
    result = await db.execute(
        select(User).where(User.oauth_provider == provider, User.oauth_id == oauth_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        # Check if email matches an existing account (link accounts)
        if email:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()

        if user is None:
            # Create new user
            username = name
            # Ensure unique username
            counter = 0
            while True:
                check_name = username if counter == 0 else f"{username}{counter}"
                exists = await db.execute(select(User).where(User.username == check_name))
                if exists.scalar_one_or_none() is None:
                    username = check_name
                    break
                counter += 1

            user = User(
                username=username,
                email=email or None,
                oauth_provider=provider,
                oauth_id=oauth_id,
            )
            db.add(user)
            await db.flush()
        else:
            # Link OAuth to existing email-matched account
            user.oauth_provider = provider
            user.oauth_id = oauth_id

    user.last_login = datetime.now(timezone.utc)
    await db.flush()

    access_token = create_access_token(user.id, user.is_superadmin)
    refresh_token_value = await create_refresh_token(db, user.id)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token_value,
        "token_type": "bearer",
        "user": {"id": user.id, "username": user.username, "email": user.email},
    }
