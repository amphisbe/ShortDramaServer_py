from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import re
from typing import Any

import jwt
from google.auth import exceptions as google_exceptions
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.config import get_settings
from app.db.database import initialize_database
from app.models import User, UserDramaFavorite, UserEpisodeProgress
from app.services import watch_service


settings = get_settings()

# 允许服务器与 Google 之间的时钟偏差（秒），用于 iat/exp 校验
GOOGLE_CLOCK_SKEW_SECONDS = 30


class AuthConfigurationError(Exception):
    """Raised when required auth settings are missing."""


class InvalidGoogleTokenError(Exception):
    """Raised when Google ID token verification fails."""


class InvalidDeviceAuthError(Exception):
    """Raised when device auth request is invalid."""


def verify_google_id_token(id_token: str) -> dict[str, Any]:
    if not settings.google_web_client_id:
        raise AuthConfigurationError("GOOGLE_WEB_CLIENT_ID is not configured")

    try:
        claims = google_id_token.verify_oauth2_token(
            id_token,
            google_requests.Request(),
            settings.google_web_client_id,
            clock_skew_in_seconds=GOOGLE_CLOCK_SKEW_SECONDS,
        )
    except google_exceptions.TransportError as exc:
        # 拉取 Google 公钥失败（网络问题），不是令牌本身无效
        raise AuthConfigurationError("cannot fetch google certs") from exc
    except (ValueError, google_exceptions.GoogleAuthError) as exc:
        # ValueError：签名/aud/exp 等校验失败；GoogleAuthError：issuer 错误
        raise InvalidGoogleTokenError("invalid google token") from exc

    issuer = claims.get("iss")
    if issuer not in ("accounts.google.com", "https://accounts.google.com"):
        raise InvalidGoogleTokenError("invalid google token issuer")

    if not claims.get("sub"):
        raise InvalidGoogleTokenError("missing google subject")

    if claims.get("email") and claims.get("email_verified") is False:
        raise InvalidGoogleTokenError("google email is not verified")

    return claims


def login_with_google(id_token: str, android_id: str | None = None) -> dict[str, Any]:
    claims = verify_google_id_token(id_token)
    # Never log id_token or full claims (PII / token material).
    db = initialize_database()
    with db.atomic():
        user = _upsert_google_user(claims)
        if android_id:
            _bind_android_id(user, android_id)
        token = _create_backend_token(user)
        return {
            "token": token,
            "user": _format_auth_user(user),
        }


def login_with_device(android_id: str) -> dict[str, Any]:
    """Lookup user by android_id.

    android_id is only bound after a successful Google login, so a hit implies
    the device already completed Google bind. No pre-bind device-only rows.
    """
    cleaned = (android_id or "").strip()
    if not cleaned:
        raise InvalidDeviceAuthError("android_id is required")

    initialize_database()
    user = User.get_or_none(User.android_id == cleaned)
    if user is None:
        return {
            "registered": False,
            "google_bound": False,
            "token": None,
            "user": None,
        }

    google_bound = bool(user.google_sub)
    if not google_bound:
        # Rare under bind-on-Google policy; treat as incomplete registration.
        return {
            "registered": True,
            "google_bound": False,
            "token": None,
            "user": {
                "userId": user.external_user_id,
                "nickname": user.nickname,
                "avatarUrl": user.avatar_url,
                "email": user.email,
                "emailVerified": bool(user.email_verified),
            },
        }

    user.last_login_at = _utcnow()
    user.save()
    token = _create_backend_token(user)
    return {
        "registered": True,
        "google_bound": True,
        "token": token,
        "user": _format_auth_user(user),
    }


def _bind_android_id(user: User, android_id: str) -> None:
    """Bind android_id to the Google-authenticated user.

    Conflict policy (anti-brush: google_sub is primary, android_id is auxiliary):
    if another user already owns this android_id, move the bind to the current
    Google user and clear it from the previous user so the device follows the
    Google account being logged in.
    """
    cleaned = (android_id or "").strip()
    if not cleaned:
        return

    previous = (
        User.select()
        .where((User.android_id == cleaned) & (User.id != user.id))
        .first()
    )
    if previous is not None:
        previous.android_id = None
        previous.save()

    if user.android_id != cleaned:
        user.android_id = cleaned
        user.save()


def _upsert_google_user(claims: dict[str, Any]) -> User:
    google_sub = str(claims["sub"])
    email = str(claims.get("email") or "")
    nickname = str(claims.get("name") or email or "Google User")
    avatar_url = str(claims.get("picture") or "")
    email_verified = bool(claims.get("email_verified") or False)

    user, _ = User.get_or_create(
        google_sub=google_sub,
        defaults={
            "external_user_id": _build_external_user_id(google_sub),
            "email": email,
            "email_verified": email_verified,
            "nickname": nickname,
            "avatar_url": avatar_url,
            "last_login_at": _utcnow(),
        },
    )
    # 以已校验的 idToken claims 为准；claim 缺失时保留已有值，避免把昵称/头像覆盖成空
    if email:
        user.email = email
        user.email_verified = email_verified
    if claims.get("name") or not user.nickname:
        user.nickname = nickname
    if avatar_url:
        user.avatar_url = avatar_url
    user.last_login_at = _utcnow()
    user.save()
    return user


def _build_external_user_id(google_sub: str) -> str:
    safe_sub = re.sub(r"[^a-zA-Z0-9]+", "_", google_sub).strip("_").lower()
    candidate = f"user_{safe_sub}"
    if 5 < len(candidate) <= 24:
        return candidate
    digest = hashlib.sha1(google_sub.encode("utf-8")).hexdigest()[:18]
    return f"user_{digest}"


def _create_backend_token(user: User) -> str:
    now = _utcnow()
    payload = {
        "sub": user.external_user_id,
        "uid": user.id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.jwt_expire_seconds)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def _format_auth_user(user: User) -> dict[str, Any]:
    watched_count = (
        UserEpisodeProgress.select()
        .where((UserEpisodeProgress.user == user) & (UserEpisodeProgress.is_finished == True))
        .count()
    )
    favorite_count = UserDramaFavorite.select().where(UserDramaFavorite.user == user).count()
    return {
        "userId": user.external_user_id,
        "nickname": user.nickname,
        "avatarUrl": user.avatar_url,
        "email": user.email,
        "emailVerified": bool(user.email_verified),
        "isVip": False,
        "watchedCount": watched_count,
        "favoriteCount": favorite_count,
        "downloadCount": 0,
        # 真实观看时长（秒，1 位小数），与 user_service.get_user_profile 同一口径
        **watch_service.get_user_watch_totals(user),
    }


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
