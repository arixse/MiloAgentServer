"""Pydantic schemas for auth endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str


class UserResponse(BaseModel):
    """Public user info."""

    user_id: str
    username: str
    created_at: str
    avatar_url: str | None = None
