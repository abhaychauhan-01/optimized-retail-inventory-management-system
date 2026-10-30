from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from ..models import User


SESSION_COOKIE_NAME = "inventory_session"
SESSION_MAX_AGE_SECONDS = 12 * 60 * 60
APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "").strip()
if APP_ENV == "production" and len(AUTH_SECRET_KEY) < 32:
    raise RuntimeError("AUTH_SECRET_KEY must contain at least 32 characters in production.")
if not AUTH_SECRET_KEY:
    AUTH_SECRET_KEY = secrets.token_urlsafe(48)
COOKIE_HTTPS_ONLY = APP_ENV == "production" or os.getenv("AUTH_COOKIE_SECURE", "false").strip().lower() in {"1", "true", "yes"}
COOKIE_SAME_SITE = os.getenv("AUTH_COOKIE_SAMESITE", "none" if APP_ENV == "production" else "lax").strip().lower()
if COOKIE_SAME_SITE not in {"lax", "strict", "none"}:
    raise RuntimeError("AUTH_COOKIE_SAMESITE must be lax, strict, or none.")
if COOKIE_SAME_SITE == "none" and not COOKIE_HTTPS_ONLY:
    raise RuntimeError("SameSite=None cookies require AUTH_COOKIE_SECURE=true and HTTPS.")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=64, maxmem=64 * 1024 * 1024)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, salt_hex, digest_hex = password_hash.split("$", 2)
        if algorithm != "scrypt":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=len(expected), maxmem=64 * 1024 * 1024)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def require_session_user(request: Request, db: Session) -> User:
    user_id = request.session.get("user_id")
    expires_at = request.session.get("expires_at")
    if not isinstance(user_id, int) or not isinstance(expires_at, int):
        raise HTTPException(status_code=401, detail="Authentication required.")
    if expires_at <= int(time.time()):
        request.session.clear()
        raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Session is no longer valid. Please sign in again.")
    return user