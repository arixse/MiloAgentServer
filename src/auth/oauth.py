"""GitHub OAuth router — login and callback endpoints."""

from __future__ import annotations

import logging
import os
import secrets
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse

from auth.router import get_users_collection
from auth.security import create_access_token

load_dotenv()

logger = logging.getLogger("milo.auth.oauth")

# ---------------------------------------------------------------------------
# OAuth config
# ---------------------------------------------------------------------------
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI", "http://localhost:8000/api/auth/github/callback")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

router = APIRouter(prefix="/api/auth", tags=["Auth"])

# ---------------------------------------------------------------------------
# State store (in-memory, 10-minute TTL)
# ---------------------------------------------------------------------------
_state_store: dict[str, float] = {}  # state -> expiry epoch


def _generate_state() -> str:
    """Generate a random CSRF state token with a 10-minute expiry."""
    token = secrets.token_urlsafe(32)
    _state_store[token] = time.time() + 600
    # Lazy cleanup of expired entries
    expired = [k for k, v in _state_store.items() if v < time.time()]
    for k in expired:
        del _state_store[k]
    return token


def _consume_state(token: str) -> bool:
    """Validate and consume a state token. Returns True if valid."""
    expiry = _state_store.pop(token, None)
    return expiry is not None and expiry > time.time()


# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------
async def _exchange_code(code: str) -> dict | None:
    """Exchange an OAuth authorization code for a GitHub access token."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                "https://github.com/login/oauth/access_token",
                json={
                    "client_id": GITHUB_CLIENT_ID,
                    "client_secret": GITHUB_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": GITHUB_REDIRECT_URI,
                },
                headers={"Accept": "application/json"},
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()
            if "access_token" not in data:
                logger.error("GitHub token exchange failed: %s", data)
                return None
            return data
        except httpx.HTTPError as exc:
            logger.error("GitHub token exchange HTTP error: %s", exc)
            return None


async def _fetch_github_user(access_token: str) -> dict | None:
    """Fetch the authenticated user's profile from GitHub."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.error("GitHub user fetch HTTP error: %s", exc)
            return None


# ---------------------------------------------------------------------------
# User upsert
# ---------------------------------------------------------------------------
async def _upsert_github_user(github_user: dict) -> tuple[str, str]:
    """Insert or find a user from GitHub profile data.

    Returns:
        (user_id, username) tuple.
    """
    users = get_users_collection()
    github_id = github_user["id"]  # GitHub numeric ID
    github_username = github_user["login"]

    # Check if this GitHub user already exists
    existing = users.find_one({"github_id": github_id})
    if existing:
        logger.info("GitHub user %s already exists as %s", github_id, existing["username"])
        return existing["user_id"], existing["username"]

    # Determine username — resolve collisions
    username = github_username
    if users.find_one({"username": username}):
        username = f"gh_{github_username}"
        if users.find_one({"username": username}):
            # Extremely unlikely, but add random suffix as final fallback
            username = f"gh_{github_username}_{secrets.token_hex(3)}"

    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    user_doc = {
        "user_id": user_id,
        "username": username,
        "github_id": github_id,
        "github_username": github_username,
        "avatar_url": github_user.get("avatar_url"),
        "provider": "github",
        "created_at": now,
    }
    users.insert_one(user_doc)
    logger.info("Created new GitHub user: %s (github_id=%s)", username, github_id)

    return user_id, username


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("/github", summary="GitHub OAuth 登录入口")
async def github_login():
    """Redirect to GitHub's OAuth authorization page."""
    if not GITHUB_CLIENT_ID:
        return RedirectResponse(url=f"{FRONTEND_URL}/auth/callback?error=github_oauth_not_configured")

    state = _generate_state()
    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": GITHUB_REDIRECT_URI,
        "scope": "read:user",
        "state": state,
    }
    url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"
    return RedirectResponse(url=url)


@router.get("/github/callback", summary="GitHub OAuth 回调")
async def github_callback(
    code: str = Query(..., description="GitHub OAuth authorization code"),
    state: str = Query(..., description="CSRF state token"),
):
    """Handle the GitHub OAuth callback — exchange code, upsert user, redirect with JWT."""
    # Handle user denying authorization
    if not code:
        return RedirectResponse(url=f"{FRONTEND_URL}/auth/callback?error=access_denied")

    # 1. Validate state
    if not _consume_state(state):
        logger.warning("Invalid or expired OAuth state token")
        return RedirectResponse(url=f"{FRONTEND_URL}/auth/callback?error=invalid_state")

    # 2. Exchange code for access token
    token_resp = await _exchange_code(code)
    if not token_resp:
        return RedirectResponse(url=f"{FRONTEND_URL}/auth/callback?error=token_exchange_failed")

    # 3. Fetch GitHub user profile
    github_user = await _fetch_github_user(token_resp["access_token"])
    if not github_user:
        return RedirectResponse(url=f"{FRONTEND_URL}/auth/callback?error=user_fetch_failed")

    # 4. Upsert user in MongoDB
    try:
        user_id, username = await _upsert_github_user(github_user)
    except Exception as exc:
        logger.exception("Failed to upsert GitHub user")
        return RedirectResponse(url=f"{FRONTEND_URL}/auth/callback?error=server_error")

    # 5. Create JWT
    jwt_token = create_access_token({"sub": user_id, "username": username})

    # 6. Redirect to frontend with token
    params = urlencode({
        "token": jwt_token,
        "user_id": user_id,
        "username": username,
    })
    return RedirectResponse(url=f"{FRONTEND_URL}/auth/callback?{params}")
