"""Local JWT authentication and database-backed role authorization."""
import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timezone
from typing import Callable

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User

bearer = HTTPBearer(auto_error=False)
ACCESS_TOKEN_SECONDS = 30 * 60
ROLES = {"Admin", "HR", "Employee"}


def _configured_secret() -> bytes:
    secret = settings.secret_key
    lowered = secret.casefold()
    if len(secret.encode("utf-8")) < 32 or any(marker in lowered for marker in ("dev-only", "replace-this", "change-me", "placeholder")):
        raise HTTPException(503, "JWT secret is not configured")
    return secret.encode("utf-8")


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_access_token(user: User, now: int | None = None) -> tuple[str, int]:
    """Create a short-lived token whose subject is an opaque user ID."""
    issued_at = int(time.time()) if now is None else int(now)
    expires_at = issued_at + ACCESS_TOKEN_SECONDS
    header = _b64encode(b'{"alg":"HS256","typ":"JWT"}')
    claims = {
        "sub": user.user_id,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": issued_at,
        "exp": expires_at,
    }
    payload = _b64encode(json.dumps(claims, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header}.{payload}"
    signature = _b64encode(hmac.new(_configured_secret(), signing_input.encode("ascii"), hashlib.sha256).digest())
    return f"{signing_input}.{signature}", expires_at


def current_actor(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> dict:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Bearer token required", headers={"WWW-Authenticate": "Bearer"})
    try:
        head, payload, signature = credentials.credentials.split(".")
        header = json.loads(_b64decode(head))
        claims = json.loads(_b64decode(payload))
        if header != {"alg": "HS256", "typ": "JWT"}:
            raise ValueError("Unsupported token header")
        expected = hmac.new(_configured_secret(), f"{head}.{payload}".encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64decode(signature)):
            raise ValueError("Invalid signature")
        if claims.get("iss") != settings.jwt_issuer or claims.get("aud") != settings.jwt_audience:
            raise ValueError("Invalid issuer or audience")
        now = time.time()
        issued_at, expires_at = float(claims["iat"]), float(claims["exp"])
        if not claims.get("sub") or expires_at <= now or issued_at > now + 30:
            raise ValueError("Expired or invalid token")
        if expires_at <= issued_at or expires_at - issued_at > ACCESS_TOKEN_SECONDS:
            raise ValueError("Invalid token lifetime")
    except HTTPException:
        raise
    except (ValueError, TypeError, KeyError, OverflowError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(401, "Invalid or expired bearer token", headers={"WWW-Authenticate": "Bearer"}) from exc

    subject = str(claims["sub"])
    user = db.get(User, subject)
    # Keep accepting already configured identity-provider tokens that use the
    # employee ID as `sub`, while still resolving role and active state locally.
    if not user:
        user = db.query(User).filter(User.employee_id == subject).first()
    if not user or not user.is_active:
        raise HTTPException(401, "Invalid or inactive account", headers={"WWW-Authenticate": "Bearer"})
    return {
        "sub": user.employee_id or user.user_id,
        "user_id": user.user_id,
        "employee_id": user.employee_id,
        "username": user.username,
        "role": user.role,
    }


def require_roles(*roles: str) -> Callable:
    allowed = set(roles)

    def dependency(actor: dict = Depends(current_actor)) -> dict:
        if actor["role"] not in allowed:
            raise HTTPException(403, "Insufficient permissions")
        return actor

    return dependency


admin_actor = require_roles("Admin")
hr_actor = require_roles("HR", "Admin")


def require_employee_access(employee_id: str, actor: dict) -> None:
    if actor["role"] == "Employee" and actor.get("employee_id") != employee_id:
        raise HTTPException(403, "You may access only your own employee records")


def require_linked_admin_for_employee_payroll(actor: dict) -> None:
    if actor.get("role") == "Admin" and not actor.get("employee_id"):
        raise HTTPException(403, "Standalone Admin accounts are not linked to employee payroll records")


def hash_password(password: str) -> str:
    if len(password) < 12 or len(password) > 128:
        raise ValueError("Password must be between 12 and 128 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=64, maxmem=32 * 1024 * 1024)
    return f"scrypt$16384$8$1${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = encoded.split("$")
        if algorithm != "scrypt" or (int(n), int(r), int(p)) != (16384, 8, 1):
            return False
        actual = hashlib.scrypt(password.encode("utf-8"), salt=_b64decode(salt), n=16384, r=8, p=1,
                                dklen=len(_b64decode(expected)), maxmem=32 * 1024 * 1024)
        return hmac.compare_digest(actual, _b64decode(expected))
    except (ValueError, TypeError, OverflowError):
        return False


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
