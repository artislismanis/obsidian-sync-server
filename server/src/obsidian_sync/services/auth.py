"""Authentication service: JWT tokens, password hashing, refresh tokens, API keys."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from obsidian_sync.config import settings
from obsidian_sync.models.user import APIKey, RefreshToken, User


# --- Password hashing ---


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


# --- JWT ---


def create_access_token(user_id: str, is_admin: bool = False) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "type": "access",
        "admin": is_admin,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token_value() -> str:
    return secrets.token_urlsafe(48)


def decode_access_token(token: str) -> dict:
    """Decode and validate an access token. Raises jwt.InvalidTokenError on failure."""
    payload = jwt.decode(
        token, settings.secret_key, algorithms=[settings.jwt_algorithm]
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Not an access token")
    return payload


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# --- Database operations ---


async def authenticate_user(
    db: AsyncSession, username: str, password: str
) -> User | None:
    """Verify credentials and return user, or None."""
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None or user.password_hash is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    user.last_login = datetime.now(timezone.utc)
    return user


async def create_refresh_token(
    db: AsyncSession, user_id: str
) -> str:
    """Create a new refresh token and store its hash."""
    token_value = create_refresh_token_value()
    token = RefreshToken(
        user_id=user_id,
        token_hash=_hash_token(token_value),
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(token)
    await db.flush()
    return token_value


async def rotate_refresh_token(
    db: AsyncSession, old_token_value: str
) -> tuple[User, str] | None:
    """Validate a refresh token, revoke it, and issue a new one. Returns (user, new_token) or None."""
    token_hash = _hash_token(old_token_value)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False,  # noqa: E712
        )
    )
    rt = result.scalar_one_or_none()
    if rt is None:
        return None
    # Compare expiry — handle both naive and aware datetimes (SQLite vs PostgreSQL)
    now = datetime.now(timezone.utc)
    expires_at = rt.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        rt.revoked = True
        return None

    # Revoke old token
    rt.revoked = True

    # Load user
    user_result = await db.execute(select(User).where(User.id == rt.user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        return None

    # Issue new refresh token
    new_token_value = await create_refresh_token(db, user.id)
    return user, new_token_value


async def revoke_all_refresh_tokens(db: AsyncSession, user_id: str) -> int:
    """Revoke all refresh tokens for a user. Returns count revoked."""
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked == False,  # noqa: E712
        )
    )
    tokens = result.scalars().all()
    for token in tokens:
        token.revoked = True
    return len(tokens)


# --- API Keys ---


def generate_api_key() -> tuple[str, str]:
    """Generate an API key. Returns (full_key, prefix)."""
    key = "oss_" + secrets.token_urlsafe(32)
    prefix = key[:12]
    return key, prefix


async def create_api_key(
    db: AsyncSession, user_id: str, name: str
) -> tuple[APIKey, str]:
    """Create an API key. Returns (api_key_model, raw_key)."""
    raw_key, prefix = generate_api_key()
    api_key = APIKey(
        user_id=user_id,
        name=name,
        key_hash=_hash_token(raw_key),
        prefix=prefix,
    )
    db.add(api_key)
    await db.flush()
    return api_key, raw_key


async def verify_api_key(db: AsyncSession, raw_key: str) -> User | None:
    """Verify an API key and return its user, or None."""
    key_hash = _hash_token(raw_key)
    result = await db.execute(
        select(APIKey).where(
            APIKey.key_hash == key_hash,
            APIKey.revoked == False,  # noqa: E712
        )
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        return None

    api_key.last_used_at = datetime.now(timezone.utc)

    user_result = await db.execute(select(User).where(User.id == api_key.user_id))
    return user_result.scalar_one_or_none()


# --- First-run setup ---


async def is_first_run(db: AsyncSession) -> bool:
    """Check if any users exist."""
    result = await db.execute(select(User).limit(1))
    return result.scalar_one_or_none() is None


async def create_admin_user(
    db: AsyncSession, username: str, password: str, email: str | None = None
) -> User:
    """Create the initial admin user."""
    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        is_superadmin=True,
    )
    db.add(user)
    await db.flush()
    return user
