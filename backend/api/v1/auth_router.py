"""
auth_router.py
--------------
Authentication endpoints for the EquiRisk underwriter portal.

Endpoints:
  POST /api/v1/auth/login   — email + password → JWT access token
  GET  /api/v1/auth/me      — return current user info from token

JWT payload (underwriter):
  {
    "sub":          "<underwriter_id>",
    "user_type":    "underwriter",
    "email":        "james@aviva.com",
    "full_name":    "James Mitchell",
    "organisation": "Aviva",
    "ha_ids":       ["ha_demo", "ha_albyn"],
    "exp":          <unix timestamp>
  }

DEV_MODE:
  When DEV_MODE=true, POST /auth/login still validates credentials normally.
  The /me endpoint accepts either a real token or returns dev defaults if
  no token is provided.
"""

from __future__ import annotations

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import bcrypt
import jwt
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr

from backend.core.database.db_pool import DatabasePool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# ── Crypto config ────────────────────────────────────────────────
security = HTTPBearer(auto_error=False)

JWT_SECRET    = os.getenv("JWT_SECRET_KEY", "equirisk-dev-secret-change-in-prod")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_H  = int(os.getenv("JWT_EXPIRE_HOURS", "8"))


# ── Request / Response models ─────────────────────────────────────

class LoginRequest(BaseModel):
    email:    EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user_type:    str
    full_name:    str
    organisation: str
    ha_ids:       List[str]
    expires_in:   int          # seconds


class MeResponse(BaseModel):
    sub:          str
    user_type:    str
    email:        str
    full_name:    str
    organisation: str
    ha_ids:       List[str]


# ── Helpers ───────────────────────────────────────────────────────

def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def _issue_token(payload: Dict[str, Any]) -> str:
    """Issue a signed JWT with expiry."""
    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_H)
    payload["exp"] = expire
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT. Raises HTTPException on failure."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired — please log in again.",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
        )


# ── Endpoints ─────────────────────────────────────────────────────

@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest) -> LoginResponse:
    """
    Underwriter login.

    Verifies email + password against underwriter_users, loads
    accessible ha_ids from ha_underwriter_access, issues JWT.
    """
    pool = DatabasePool.get_pool()
    async with pool.acquire() as conn:

        # 1 — Look up underwriter by email
        user = await conn.fetchrow(
            """
            SELECT
                underwriter_id::text,
                email,
                full_name,
                organisation,
                password_hash,
                is_active
            FROM public.underwriter_users
            WHERE email = $1
            """,
            str(body.email).lower().strip(),
        )

        # Deliberately vague error — don't reveal whether email exists
        if not user or not user["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        # 2 — Verify password
        if not user["password_hash"] or not _verify_password(
            body.password, user["password_hash"]
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        # 3 — Load accessible ha_ids from access grants
        access_rows = await conn.fetch(
            """
            SELECT ha_id
            FROM public.ha_underwriter_access
            WHERE underwriter_id = $1
              AND (expires_at IS NULL OR expires_at > NOW())
            ORDER BY ha_id
            """,
            user["underwriter_id"],
        )
        ha_ids: List[str] = [r["ha_id"] for r in access_rows]

        # 4 — Update last_login_at
        await conn.execute(
            """
            UPDATE public.underwriter_users
            SET last_login_at = NOW()
            WHERE underwriter_id = $1
            """,
            user["underwriter_id"],
        )

    # 5 — Issue JWT
    token = _issue_token({
        "sub":          user["underwriter_id"],
        "user_type":    "underwriter",
        "email":        user["email"],
        "full_name":    user["full_name"],
        "organisation": user["organisation"] or "",
        "ha_ids":       ha_ids,
    })

    logger.info(
        f"[AUTH] Login: {user['email']} ({user['organisation']}) "
        f"ha_ids={ha_ids}"
    )

    return LoginResponse(
        access_token=token,
        user_type="underwriter",
        full_name=user["full_name"],
        organisation=user["organisation"] or "",
        ha_ids=ha_ids,
        expires_in=JWT_EXPIRE_H * 3600,
    )


@router.get("/me", response_model=MeResponse)
async def me(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> MeResponse:
    """
    Return current user info decoded from JWT.
    Useful for frontend to restore session on page reload.
    """
    dev_mode = os.getenv("DEV_MODE", "false").lower() == "true"

    if not credentials:
        if dev_mode:
            return MeResponse(
                sub="dev_user",
                user_type="underwriter",
                email="dev@equirisk.ai",
                full_name="Dev User",
                organisation="EquiRisk",
                ha_ids=[os.getenv("DEV_HA_ID", "ha_demo")],
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
        )

    payload = _decode_token(credentials.credentials)

    return MeResponse(
        sub=payload.get("sub", ""),
        user_type=payload.get("user_type", "underwriter"),
        email=payload.get("email", ""),
        full_name=payload.get("full_name", ""),
        organisation=payload.get("organisation", ""),
        ha_ids=payload.get("ha_ids", []),
    )
