"""FastAPI dependencies for extracting the current user from a JWT Bearer token."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth.security import decode_access_token

# ---------------------------------------------------------------------------
# Security scheme
# ---------------------------------------------------------------------------
_bearer_scheme = HTTPBearer(auto_error=False)


async def _validate_token(token: str) -> dict:
    """验证 JWT token，返回 user info dict。token 无效时抛出 401。"""
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录已过期，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    username = payload.get("username", "")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌",
        )
    return {"user_id": user_id, "username": username}


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict:
    """FastAPI dependency: extract and validate the current user from a JWT Bearer token.

    Raises 401 if the token is missing, expired, or invalid.

    Returns:
        A dict with at least {"user_id": str, "username": str}.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要登录才能访问此接口",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = await _validate_token(credentials.credentials)
    user["access_token"] = credentials.credentials
    return user


async def get_current_user_from_query_or_header(
    token: str = Query("", description="JWT token（用于文件下载等无法带 Header 的场景）"),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict:
    """支持从 query 参数或 Authorization header 获取 JWT token 的认证依赖。

    优先使用 Authorization header，其次使用 `token` query 参数。
    用于文件下载等浏览器直接打开链接的场景（<a> 标签跳转不带 Header）。
    """
    if credentials is not None:
        return await _validate_token(credentials.credentials)
    if token:
        return await _validate_token(token)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="需要登录才能访问此接口",
        headers={"WWW-Authenticate": "Bearer"},
    )
