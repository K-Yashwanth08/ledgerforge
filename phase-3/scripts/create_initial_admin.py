"""Interactively provision the first standalone LedgerForge system Admin.

Run locally after configuring the JWT signing secret and applying migrations.
This command intentionally accepts no identity or password command-line values.
"""
import argparse
import getpass
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import User
from app.security import _configured_secret, hash_password

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
CONFIRMATION_PHRASE = "CREATE FIRST ADMIN"


def _normalized_username(username: str) -> str:
    normalized = username.strip().casefold()
    if not EMAIL_RE.fullmatch(normalized):
        raise ValueError("Username must be a valid email address")
    return normalized


def _validate_password(password: str, confirmation: str, username: str) -> str:
    if password != confirmation:
        raise ValueError("Passwords did not match")
    if len(password) < 14 or len(password) > 128:
        raise ValueError("Password must be between 14 and 128 characters")
    categories = (
        any(char.islower() for char in password),
        any(char.isupper() for char in password),
        any(char.isdigit() for char in password),
        any(not char.isalnum() for char in password),
    )
    if sum(categories) < 3:
        raise ValueError("Password must include at least three of: lowercase, uppercase, number, symbol")
    local_part = username.split("@", 1)[0]
    if local_part and local_part.casefold() in password.casefold():
        raise ValueError("Password must not contain the username")
    return password


def _lock_initial_admin_creation(db: Session) -> None:
    """Serialize one-time bootstrap attempts on supported database engines."""
    dialect = db.get_bind().dialect.name
    if dialect == "sqlite":
        # Reserve SQLite's writer lock before checking for an existing Admin.
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
    elif dialect == "postgresql":
        # Transaction-scoped advisory lock; no extra schema object is needed.
        db.execute(text("SELECT pg_advisory_xact_lock(:lock_key)"), {"lock_key": 741982441041})
    else:
        raise ValueError("Initial Admin bootstrap is supported only on SQLite or PostgreSQL")


def provision_initial_admin(
    db: Session,
    username: str,
    password: str,
    confirmation: str,
    confirmation_phrase: str,
) -> User:
    """Add a standalone initial Admin; caller owns the surrounding transaction."""
    _lock_initial_admin_creation(db)
    normalized = _normalized_username(username)
    _validate_password(password, confirmation, normalized)
    if confirmation_phrase != CONFIRMATION_PHRASE:
        raise ValueError("Initial Admin confirmation phrase did not match")
    if db.query(User).filter(User.role == "Admin").first():
        raise ValueError("An Admin already exists; initial bootstrap is one-time")
    if db.query(User).filter(func.lower(User.username) == normalized).first():
        raise ValueError("Username already exists")
    user = User(
        user_id=uuid.uuid4().hex[:24],
        employee_id=None,
        username=normalized,
        password_hash=hash_password(password),
        role="Admin",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.flush()
    return user


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("Run this bootstrap from an interactive local terminal.", file=sys.stderr)
        return 2
    try:
        _configured_secret()
    except Exception:
        print("JWT signing secret is not configured; set it locally before bootstrap.", file=sys.stderr)
        return 2

    try:
        username = _normalized_username(input("Initial Admin email: "))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    password = getpass.getpass("Initial password (14+ characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    phrase = input(f"Type {CONFIRMATION_PHRASE!r} to create the first Admin: ")
    # A single transaction prevents partial user creation. The database check
    # is performed inside it, immediately before inserting the account.
    try:
        with SessionLocal.begin() as db:
            provision_initial_admin(db, username, password, confirmation, phrase)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except IntegrityError:
        print("Initial Admin was not created because a concurrent or duplicate account change occurred.",
              file=sys.stderr)
        return 2
    print("Standalone initial Admin account created. No employee record was linked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
