"""Auth API router —— register / login / me."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo import MongoClient
from pymongo.collection import Collection

from auth.dependencies import get_current_user
from auth.models import TokenResponse, UserCreate, UserLogin, UserResponse
from auth.security import create_access_token, hash_password, verify_password

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
    print(f"[Auth] MongoDB users collection ready — {db_name}.users")
    return _users_collection


def _get_users_collection() -> Collection:
    if _users_collection is None:
        raise RuntimeError("Auth MongoDB collection not initialized. Call init_auth_mongo() first.")
    return _users_collection


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/register", response_model=TokenResponse, summary="注册新用户")
async def register(body: UserCreate):
    """注册新用户，返回 JWT token。

    用户名必须唯一。密码使用 bcrypt 哈希存储。
    """
    users = _get_users_collection()

    # Check username uniqueness
    if users.find_one({"username": body.username}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"用户名 '{body.username}' 已被注册",
        )

    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    user_doc = {
        "user_id": user_id,
        "username": body.username,
        "hashed_password": hash_password(body.password),
        "created_at": now,
    }
    users.insert_one(user_doc)

    token = create_access_token({"sub": user_id, "username": body.username})
    return TokenResponse(access_token=token, user_id=user_id, username=body.username)


@router.post("/login", response_model=TokenResponse, summary="用户登录")
async def login(body: UserLogin):
    """使用用户名和密码登录，返回 JWT token。"""
    users = _get_users_collection()

    user_doc = users.find_one({"username": body.username})
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    if not verify_password(body.password, user_doc["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    token = create_access_token({"sub": user_doc["user_id"], "username": user_doc["username"]})
    return TokenResponse(
        access_token=token,
        user_id=user_doc["user_id"],
        username=user_doc["username"],
    )


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
    )
