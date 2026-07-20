"""Pydantic schemas for auth endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    """Registration request body."""

    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    password: str = Field(..., min_length=4, max_length=128, description="密码")


class UserLogin(BaseModel):
    """Login request body."""

    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


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
