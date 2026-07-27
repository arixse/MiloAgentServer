"""Auth API router —— register / login / me."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo import MongoClient
from pymongo.collection import Collection

from auth.dependencies import get_current_user
from auth.models import UserResponse

logger = logging.getLogger("milo.auth")

router = APIRouter(prefix="/api/auth", tags=["Auth"])

# ---------------------------------------------------------------------------
# MongoDB users collection —— set by main.py via `init_auth_mongo()`
# ---------------------------------------------------------------------------
_users_collection: Collection | None = None


def init_auth_mongo(client: MongoClient, db_name: str = "MiloAgent") -> Collection:
    """Initialize the auth users collection from a pymongo client.

    Called once at app startup from main.py.
    """
    global _users_collection
    db = client[db_name]
    _users_collection = db["users"]
    # Ensure unique index on username
    _users_collection.create_index("username", unique=True)
    logger.info("MongoDB users collection ready: %s.users", db_name)
    return _users_collection


def _get_users_collection() -> Collection:
    if _users_collection is None:
        raise RuntimeError("Auth MongoDB collection not initialized. Call init_auth_mongo() first.")
    return _users_collection


def get_users_collection() -> Collection:
    """Public accessor for the users collection (used by oauth.py)."""
    return _get_users_collection()


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/me", response_model=UserResponse, summary="获取当前用户信息")
async def get_me(current_user: dict = Depends(get_current_user)):
    """返回当前认证用户的详细信息（需要 Bearer token）。"""
    users = _get_users_collection()
    user_doc = users.find_one({"user_id": current_user["user_id"]})
    if not user_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    return UserResponse(
        user_id=user_doc["user_id"],
        username=user_doc["username"],
        created_at=user_doc.get("created_at", ""),
        avatar_url=user_doc.get("avatar_url"),
    )
