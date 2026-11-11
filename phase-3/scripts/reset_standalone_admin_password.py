"""Interactively reset the password for the existing standalone LedgerForge Admin.

Run locally from an interactive terminal. Credentials are read only by getpass;
the command accepts no usernames or passwords as command-line arguments.
"""
import argparse
import getpass
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import func

from app.database import SessionLocal
from app.models import User
from app.security import _configured_secret, hash_password
from scripts.create_initial_admin import _lock_initial_admin_creation, _normalized_username, _validate_password

CONFIRMATION_PHRASE = "RESET EXISTING ADMIN PASSWORD"


def reset_standalone_admin_password(db, username: str, password: str, confirmation: str,
                                    confirmation_phrase: str) -> None:
    """Reset only the matching active, unlinked Admin inside caller transaction."""
    _lock_initial_admin_creation(db)
    normalized = _normalized_username(username)
    if confirmation_phrase != CONFIRMATION_PHRASE:
        raise ValueError("Password reset confirmation phrase did not match")
    _validate_password(password, confirmation, normalized)
    user = db.query(User).filter(func.lower(User.username) == normalized).one_or_none()
    if not user or user.role != "Admin" or not user.is_active or user.employee_id is not None:
        raise ValueError("No matching active standalone Admin account was found")
    user.password_hash = hash_password(password)
    db.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("Run this password reset from an interactive local terminal.", file=sys.stderr)
        return 2
    try:
        _configured_secret()
        username = _normalized_username(input("Existing standalone Admin email: "))
        password = getpass.getpass("New password (14+ characters): ")
        confirmation = getpass.getpass("Confirm new password: ")
        phrase = input(f"Type {CONFIRMATION_PHRASE!r} to reset this account: ")
        with SessionLocal.begin() as db:
            reset_standalone_admin_password(db, username, password, confirmation, phrase)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        # Avoid exception details here: database/driver errors can include connection
        # configuration and other local environment details.
        print(f"Password reset failed ({type(exc).__name__}).", file=sys.stderr)
        return 2
    print("Standalone Admin password reset. Sign in with the new password.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
