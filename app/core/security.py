"""JWT 鉴权与管理接口鉴权依赖。

鉴权失败不返回 HTTP 401/403，而是抛出 ApiAuthError，由 main.py 注册的异常处理器
统一转换为项目约定的 HTTP 200 + {"code": 401/403, "message": ..., "data": None} 信封，
与其他接口的错误风格以及客户端 http() 的 code != 0 判定保持一致。
"""

from __future__ import annotations

import hmac

import jwt
from fastapi import Depends, Header

from app.core.config import get_settings

# 与 auth_service._create_backend_token 签发算法保持一致
JWT_ALGORITHM = "HS256"


class ApiAuthError(Exception):
    """鉴权失败，code 为信封中的业务码（401 未登录/令牌无效，403 无权限）。"""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        return ""
    scheme, _, token = authorization.strip().partition(" ")
    if scheme.lower() != "bearer":
        return ""
    return token.strip()


def decode_user_id(token: str) -> str | None:
    """校验 JWT（签名 + exp）并返回 sub（即 external_user_id），无效时返回 None。"""
    if not token:
        return None
    try:
        payload = jwt.decode(
            token,
            get_settings().jwt_secret,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError:
        return None
    sub = payload.get("sub")
    return str(sub) if sub else None


def get_optional_user(
    authorization: str | None = Header(default=None),
) -> str | None:
    """可选登录：无令牌或令牌无效时返回 None。"""
    return decode_user_id(_extract_bearer_token(authorization))


def get_current_user(
    authorization: str | None = Header(default=None),
) -> str:
    """必须登录：返回当前用户 external_user_id，否则 code 401。"""
    token = _extract_bearer_token(authorization)
    if not token:
        raise ApiAuthError(401, "未登录")
    user_id = decode_user_id(token)
    if user_id is None:
        raise ApiAuthError(401, "登录已失效")
    return user_id


def require_path_user(
    user_id: str,
    current_user_id: str = Depends(get_current_user),
) -> str:
    """路径中的 {user_id} 必须与令牌用户一致，否则 code 403。"""
    if user_id != current_user_id:
        raise ApiAuthError(403, "无权访问该用户数据")
    return current_user_id


def require_admin(
    x_admin_token: str | None = Header(default=None),
) -> None:
    """管理接口：请求头 X-Admin-Token 必须等于 ADMIN_TOKEN；ADMIN_TOKEN 为空时管理接口禁用。"""
    admin_token = get_settings().admin_token
    if not admin_token:
        raise ApiAuthError(403, "管理接口未启用")
    if not x_admin_token or not hmac.compare_digest(x_admin_token, admin_token):
        raise ApiAuthError(403, "管理员令牌无效")
