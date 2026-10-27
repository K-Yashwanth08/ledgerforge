"""JWT validation for deployments that integrate an existing identity provider.

LedgerForge does not issue credentials. An upstream identity provider must sign
tokens for the configured issuer/audience with the configured key.
"""
import base64
import hashlib
import hmac
import json
import time
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from .config import settings

bearer = HTTPBearer(auto_error=False)

def current_actor(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if settings.secret_key == "dev-only-change-me" or len(settings.secret_key) < 32:
        raise HTTPException(503, "Identity provider JWT validation is not configured")
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Bearer token required", headers={"WWW-Authenticate": "Bearer"})
    try:
        head, payload, signature = credentials.credentials.split(".")
        header = json.loads(_b64decode(head))
        claims = json.loads(_b64decode(payload))
        if header.get("alg") != "HS256" or header.get("typ", "JWT") != "JWT":
            raise ValueError("Unsupported token algorithm")
        expected = hmac.new(settings.secret_key.encode(), f"{head}.{payload}".encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64decode(signature)):
            raise ValueError("Invalid token signature")
        if claims.get("iss") != settings.jwt_issuer:
            raise ValueError("Invalid issuer")
        audience = claims.get("aud")
        if settings.jwt_audience not in (audience if isinstance(audience, list) else [audience]):
            raise ValueError("Invalid audience")
        if not claims.get("sub") or not all(k in claims for k in ("exp", "iat")):
            raise ValueError("Missing required claims")
        now = time.time()
        if float(claims["exp"]) <= now or float(claims["iat"]) > now + 60:
            raise ValueError("Expired or future-issued token")
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(401, "Invalid or expired bearer token", headers={"WWW-Authenticate": "Bearer"}) from exc
    return {"sub": str(claims["sub"]), "role": str(claims.get("role", "employee")).lower()}

def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

def hr_actor(actor: dict = Depends(current_actor)) -> dict:
    if actor["role"] not in {"hr", "admin"}:
        raise HTTPException(403, "HR authorization required")
    return actor
