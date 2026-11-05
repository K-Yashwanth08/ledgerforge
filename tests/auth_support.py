"""Test-only identities. These are isolated synthetic records, never source data."""
from app.models import Employee, User


def seed_test_users(db, identities):
    db.flush()
    for user_id, role in identities.items():
        if db.get(User, user_id):
            continue
        employee_id = user_id if role == "Employee" and db.get(Employee, user_id) else None
        db.add(User(user_id=user_id, employee_id=employee_id,
                    username=f"{user_id.casefold()}@example.test",
                    password_hash="test-only-no-login", role=role, is_active=True))
    db.flush()
