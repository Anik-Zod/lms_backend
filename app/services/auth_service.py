import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.email import send_password_reset_email
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.identity import AuthIdentity, PasswordResetToken, User, UserSession
from app.schemas.auth import TokenResponse


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def register_user(db: AsyncSession, email: str, password: str, display_name: str) -> User:
    existing = await db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(email=email, display_name=display_name)
    db.add(user)
    await db.flush()

    identity = AuthIdentity(
        user_id=user.id,
        provider="password",
        provider_subject=email.lower(),
        password_hash=hash_password(password),
    )
    db.add(identity)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
    )

    identity = await db.scalar(
        select(AuthIdentity).where(
            AuthIdentity.provider == "password",
            AuthIdentity.provider_subject == email.lower(),
        )
    )
    if identity is None or identity.password_hash is None:
        raise invalid_credentials
    if not verify_password(password, identity.password_hash):
        raise invalid_credentials

    user = await db.get(User, identity.user_id)
    if user is None or user.deleted_at is not None:
        raise invalid_credentials
    if user.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active")

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    return user


async def issue_token_pair(db: AsyncSession, user: User) -> TokenResponse:
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    session = UserSession(
        user_id=user.id,
        refresh_token_hash=_hash_token(refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(session)
    await db.commit()

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


async def rotate_refresh_token(db: AsyncSession, refresh_token: str) -> TokenResponse:
    invalid = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    try:
        payload = decode_token(refresh_token)
    except ValueError:
        raise invalid
    if payload.get("type") != "refresh":
        raise invalid

    user_id = uuid.UUID(payload["sub"])
    token_hash = _hash_token(refresh_token)

    now = datetime.now(timezone.utc)
    session = await db.scalar(
        select(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.refresh_token_hash == token_hash,
            UserSession.revoked_at.is_(None),
        )
    )
    if session is None or session.expires_at < now:
        raise invalid

    user = await db.get(User, user_id)
    if user is None or user.deleted_at is not None or user.status != "ACTIVE":
        raise invalid

    session.revoked_at = now
    await db.flush()

    return await issue_token_pair(db, user)


async def revoke_refresh_token(db: AsyncSession, user: User, refresh_token: str) -> None:
    token_hash = _hash_token(refresh_token)
    session = await db.scalar(
        select(UserSession).where(
            UserSession.user_id == user.id,
            UserSession.refresh_token_hash == token_hash,
            UserSession.revoked_at.is_(None),
        )
    )
    if session is None:
        return

    session.revoked_at = datetime.now(timezone.utc)
    await db.commit()


async def request_password_reset(db: AsyncSession, email: str) -> None:
    """Always succeeds silently -- never reveals whether the email is registered."""
    identity = await db.scalar(
        select(AuthIdentity).where(
            AuthIdentity.provider == "password",
            AuthIdentity.provider_subject == email.lower(),
        )
    )
    if identity is None:
        return

    user = await db.get(User, identity.user_id)
    if user is None or user.deleted_at is not None or user.status != "ACTIVE":
        return

    raw_token = secrets.token_urlsafe(32)
    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_token(raw_token),
        expires_at=datetime.now(timezone.utc)
        + timedelta(minutes=settings.password_reset_token_expire_minutes),
    )
    db.add(reset_token)
    await db.commit()

    send_password_reset_email(user.email, raw_token)


async def reset_password(db: AsyncSession, token: str, new_password: str) -> None:
    invalid = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token"
    )

    now = datetime.now(timezone.utc)
    reset_token = await db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == _hash_token(token),
            PasswordResetToken.used_at.is_(None),
        )
    )
    if reset_token is None or reset_token.expires_at < now:
        raise invalid

    user = await db.get(User, reset_token.user_id)
    if user is None or user.deleted_at is not None:
        raise invalid

    identity = await db.scalar(
        select(AuthIdentity).where(
            AuthIdentity.user_id == user.id,
            AuthIdentity.provider == "password",
        )
    )
    if identity is None:
        raise invalid

    identity.password_hash = hash_password(new_password)
    reset_token.used_at = now

    # Force re-login on every device after a password reset.
    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )

    await db.commit()


async def change_password(
    db: AsyncSession, user: User, current_password: str, new_password: str
) -> None:
    identity = await db.scalar(
        select(AuthIdentity).where(
            AuthIdentity.user_id == user.id,
            AuthIdentity.provider == "password",
        )
    )
    if (
        identity is None
        or identity.password_hash is None
        or not verify_password(current_password, identity.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect"
        )

    identity.password_hash = hash_password(new_password)
    await db.commit()
