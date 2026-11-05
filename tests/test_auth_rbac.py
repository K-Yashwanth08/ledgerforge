import base64
import hashlib
import hmac
import json
import time
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import Department, Employee, Role, User
from app.security import create_access_token, hash_password, verify_password
from scripts.create_initial_admin import CONFIRMATION_PHRASE, provision_initial_admin
from scripts.reset_standalone_admin_password import (
    CONFIRMATION_PHRASE as RESET_CONFIRMATION_PHRASE,
    reset_standalone_admin_password,
)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _token(sub, role="Employee", exp=None, iat=None):
    now = int(time.time())
    header = _b64(b'{"alg":"HS256","typ":"JWT"}')
    payload = _b64(json.dumps({"sub": sub, "role": role, "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience, "iat": iat or now, "exp": exp or now + 1800},
        separators=(",", ":")).encode())
    body = f"{header}.{payload}"
    signature = _b64(hmac.new(settings.secret_key.encode(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{signature}"


@pytest.fixture
def auth_client(monkeypatch):
    monkeypatch.setattr(settings, "secret_key", "task13-test-signing-secret-at-least-32-bytes")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory.begin() as db:
        db.add(Department(department_id="D1", department_name="Test", cost_center="CC1"))
        db.add(Role(role_id="R1", department_id="D1", role_title="Test role", level=1, grade="L1",
                    band_min_annual=1, band_mid_annual=2, band_max_annual=3, overtime_eligible="N", band_year=2026))
        for eid in ("E1", "E2"):
            db.add(Employee(employee_id=eid, first_name="Synthetic", last_name=eid, full_name=f"Synthetic {eid}",
                work_email=f"{eid.lower()}@example.test", hire_date=date(2020, 1, 1), employment_status="Active",
                employment_type="Permanent", department_id="D1", role_id="R1"))
        db.flush()
        db.add_all([
            User(user_id="EMP1", employee_id="E1", username="employee1@example.test",
                 password_hash=hash_password("Employee-Test-Password-1"), role="Employee", is_active=True),
            User(user_id="EMP2", employee_id="E2", username="employee2@example.test",
                 password_hash=hash_password("Employee-Test-Password-2"), role="Employee", is_active=True),
            User(user_id="HR1", employee_id=None, username="hr1@example.test",
                 password_hash=hash_password("HumanResources-Test-1"), role="HR", is_active=True),
            User(user_id="ADMIN1", employee_id=None, username="admin1@example.test",
                 password_hash=hash_password("Administrator-Test-1"), role="Admin", is_active=True),
            User(user_id="INACTIVE", employee_id=None, username="inactive@example.test",
                 password_hash=hash_password("Inactive-Test-Password-1"), role="HR", is_active=False),
        ])
    db = factory()

    def override():
        yield db

    app.dependency_overrides[get_db] = override
    with TestClient(app) as client:
        yield client, db
    app.dependency_overrides.clear()
    db.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def auth(sub="EMP1", role="Employee"):
    return {"Authorization": f"Bearer {_token(sub, role)}"}


def test_login_password_hash_and_database_role_are_authoritative(auth_client):
    client, db = auth_client
    page = client.get("/")
    assert page.status_code == 200 and 'id="loginForm"' in page.text and 'id="loginPassword"' in page.text
    response = client.post("/auth/login", json={"username": "EMPLOYEE1@example.test", "password": "Employee-Test-Password-1"})
    assert response.status_code == 200
    result = response.json()
    assert result["expires_in"] == 1800
    assert db.get(User, "EMP1").password_hash != "Employee-Test-Password-1"
    headers = {"Authorization": f"Bearer {result['access_token']}"}
    assert client.get("/auth/me", headers=headers).json()["role"] == "Employee"
    # The token's client-controlled role claim cannot elevate the database role.
    assert client.get("/users", headers=auth("EMP1", "Admin")).status_code == 403
    # Existing trusted identity-provider subjects may be employee IDs; their
    # permissions still come from the linked database account.
    legacy_subject = {"Authorization": f"Bearer {_token('E1', 'Admin')}"}
    assert client.get("/employees/E1", headers=legacy_subject).status_code == 200
    assert client.get("/users", headers=legacy_subject).status_code == 403


def test_local_password_recovery_only_resets_matching_standalone_admin(auth_client):
    _, db = auth_client
    with db.begin():
        reset_standalone_admin_password(db, "ADMIN1@example.test", "New-Admin-Password-91!",
                                        "New-Admin-Password-91!", RESET_CONFIRMATION_PHRASE)
    admin = db.get(User, "ADMIN1")
    assert verify_password("New-Admin-Password-91!", admin.password_hash)
    assert not verify_password("Administrator-Test-1", admin.password_hash)


def test_local_password_recovery_rejects_non_admin_and_bad_confirmation(auth_client):
    _, db = auth_client
    with pytest.raises(ValueError, match="confirmation phrase"):
        with db.begin():
            reset_standalone_admin_password(db, "admin1@example.test", "New-Admin-Password-91!",
                                            "New-Admin-Password-91!", "wrong phrase")
    with pytest.raises(ValueError, match="standalone Admin"):
        with db.begin():
            reset_standalone_admin_password(db, "employee1@example.test", "New-Admin-Password-91!",
                                            "New-Admin-Password-91!", RESET_CONFIRMATION_PHRASE)


def test_admin_bootstrap_requires_employee_registered_email(auth_client):
    # This test intentionally uses an empty isolated DB to exercise the same
    # provisioning function used by the interactive local command.
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = factory()
    password = "Strong-Bootstrap-Password-47!"
    with pytest.raises(ValueError, match="14 and 128"):
        with db.begin():
            provision_initial_admin(db, "first@example.test", "short", "short", CONFIRMATION_PHRASE)
    with pytest.raises(ValueError, match="did not match"):
        with db.begin():
            provision_initial_admin(db, "first@example.test", password, password + "different",
                                    CONFIRMATION_PHRASE)
    with pytest.raises(ValueError, match="three of"):
        with db.begin():
            provision_initial_admin(db, "first@example.test", "alllowercasepassword", "alllowercasepassword",
                                    CONFIRMATION_PHRASE)
    with db.begin():
        db.add(User(user_id="EXISTING-HR", employee_id=None, username="taken@example.test",
            password_hash="not-used", role="HR", is_active=True))
    with pytest.raises(ValueError, match="Username already exists"):
        with db.begin():
            provision_initial_admin(db, "taken@example.test", password, password, CONFIRMATION_PHRASE)
    with db.begin():
        admin = provision_initial_admin(db, "System.Admin@example.test", password, password,
                                        CONFIRMATION_PHRASE)
    assert admin.employee_id is None
    assert admin.username == "system.admin@example.test"
    assert admin.role == "Admin" and admin.is_active and admin.created_at is not None
    assert admin.password_hash != password and admin.password_hash.startswith("scrypt$")
    with pytest.raises(ValueError, match="Admin already exists"):
        with db.begin():
            provision_initial_admin(db, "second.admin@example.test", password, password,
                                    CONFIRMATION_PHRASE)
    with pytest.raises(ValueError, match="confirmation phrase"):
        with db.begin():
            provision_initial_admin(db, "first@example.test", password, password, "NO")
    db.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_standalone_admin_login_and_employee_payroll_restrictions(auth_client):
    client, db = auth_client
    standalone = User(user_id="STANDALONE", employee_id=None, username="standalone@example.test",
        password_hash=hash_password("Standalone-Admin-Password-47!"), role="Admin", is_active=True)
    db.add(standalone)
    db.commit()
    login = client.post("/auth/login", json={"username": standalone.username,
        "password": "Standalone-Admin-Password-47!"})
    assert login.status_code == 200 and login.json()["expires_in"] == 1800
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["role"] == "Admin" and me.json()["employee_id"] is None
    assert client.get("/users", headers=headers).status_code == 200
    assert client.get("/payslips/employee/E1/runs", headers=headers).status_code == 403
    assert client.get("/payslips/E1/NO-RUN/data", headers=headers).status_code == 403
    assert client.get("/payroll/calculate/E1?month=2025-01", headers=headers).status_code == 403
    assert client.get("/payroll/runs/NO-RUN/items", headers=headers).status_code == 403


@pytest.mark.parametrize("headers", [None, {"Authorization": "Bearer garbage"}])
def test_missing_and_invalid_tokens_return_401(auth_client, headers):
    client, _ = auth_client
    response = client.get("/auth/me", headers=headers)
    assert response.status_code == 401


def test_expired_token_and_inactive_account_return_401(auth_client):
    client, _ = auth_client
    now = int(time.time())
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {_token('EMP1', exp=now-1, iat=now-1801)}"}).status_code == 401
    assert client.post("/auth/login", json={"username": "inactive@example.test", "password": "Inactive-Test-Password-1"}).status_code == 401


def test_multiple_sensitive_routes_require_role(auth_client):
    client, _ = auth_client
    paths = ["/employees", "/payroll/runs", "/ledger/accounts", "/reports/balance-sheet", "/users"]
    for path in paths:
        assert client.get(path).status_code == 401, path
    employee = auth()
    for path in paths:
        assert client.get(path, headers=employee).status_code == 403, path
    assert client.get("/attendance", headers=employee).status_code == 200


def test_employee_ownership_and_payroll_write_rejected(auth_client):
    client, _ = auth_client
    employee = auth()
    assert client.get("/employees/E1", headers=employee).status_code == 200
    assert client.get("/employees/E2", headers=employee).status_code == 403
    assert client.get("/payslips/employee/E2/runs", headers=employee).status_code == 403
    assert client.post("/payroll/runs/NO-SUCH-RUN/process", headers=employee).status_code == 403


def test_hr_cannot_run_admin_actions_and_admin_can_manage_users(auth_client):
    client, _ = auth_client
    hr = auth("HR1", "Admin")
    admin = auth("ADMIN1", "Admin")
    assert client.get("/users", headers=hr).status_code == 403
    assert client.post("/payroll/runs/nope/approve", headers=hr).status_code == 403
    assert client.patch("/users/ADMIN1", json={"is_active": False}, headers=admin).status_code == 409
    assert client.post("/users", json={"employee_id": None, "username": "new@example.test",
        "password": "New-Temporary-Password-1", "role": "HR"}, headers=admin).status_code == 201
    assert client.post("/users", json={"employee_id": None, "username": "standalone2@example.test",
        "password": "New-Temporary-Password-2", "role": "Admin"}, headers=admin).status_code == 422
    assert client.get("/users", headers=admin).status_code == 200


def test_deactivation_invalidates_existing_access_token(auth_client):
    client, _ = auth_client
    login = client.post("/auth/login", json={"username": "hr1@example.test", "password": "HumanResources-Test-1"})
    assert login.status_code == 200
    bearer = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/auth/me", headers=bearer).status_code == 200
    admin = auth("ADMIN1", "Admin")
    assert client.patch("/users/HR1", json={"is_active": False}, headers=admin).status_code == 200
    assert client.get("/auth/me", headers=bearer).status_code == 401
