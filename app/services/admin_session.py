"""Password-based administrator sessions for deployments using GeFeiSites."""

import hashlib
import hmac

from fastapi import Request

from ..config import settings
from .jwt_service import jwt_service

ADMIN_USERNAME = "admin"
SESSION_PATH = "/api/v1/admin/session"
SESSION_COOKIE = "__Secure-formrefine-admin"
COOKIE_OPTIONS = {"path": "/api/v1/admin", "secure": True, "httponly": True, "samesite": "strict"}


def _signing_key() -> str:
    # Keep this session separate from legacy JWTs. Rotating the password revokes all sessions.
    return hmac.new(settings.engine_admin_password.get_secret_value().encode(), SESSION_COOKIE.encode(), hashlib.sha256).hexdigest()


def start_session(username: str, password: str) -> str | None:
    username_ok = hmac.compare_digest(username.encode(), ADMIN_USERNAME.encode())
    password_ok = hmac.compare_digest(password.encode(), settings.engine_admin_password.get_secret_value().encode())
    if not (username_ok and password_ok):
        return None
    return jwt_service.create_token({"id": username, "role": "admin", "is_local": True}, signing_key=_signing_key())


def read_session(request: Request) -> dict | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    user = jwt_service.verify_token(token, signing_key=_signing_key())
    if user and user["id"] == ADMIN_USERNAME and user["role"] == "admin":
        return {**user, "provider": "admin_password"}
    return None
