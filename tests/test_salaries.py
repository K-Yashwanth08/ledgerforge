from datetime import date
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
from app.main import app
from app.models import Department, Role, Employee, SalaryComponent, SalaryRevision, SalaryStructure
from app.config import settings
from app.models import User
from tests.test_attendance_leave import token

@pytest.fixture
def salary_db(monkeypatch):
    monkeypatch.setattr(settings,"secret_key","test-only-signing-secret-at-least-32-bytes")
    engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
    Base.metadata.create_all(engine); Factory=sessionmaker(bind=engine,autoflush=False)
    with Factory.begin() as db:
        db.add(Department(department_id="D1",department_name="Engineering",cost_center="CC1"))
        db.add(Role(role_id="R1",department_id="D1",role_title="Engineer",level=1,grade="L1",band_min_annual=1,band_mid_annual=2,band_max_annual=3,overtime_eligible="N",band_year=2026))
        db.add(Employee(employee_id="E1",first_name="Test",last_name="Employee",full_name="Test Employee",work_email="test@example.test",hire_date=date(2020,1,1),employment_status="Active",employment_type="Permanent",department_id="D1",role_id="R1"))
        db.add(User(user_id="TEST-ADMIN",employee_id=None,username="test-admin@example.test",password_hash="test",role="Admin",is_active=True))
        db.add_all([SalaryComponent(component_id="BASIC",component_name="Basic",component_type="EARNING",taxable=True,calculation_rule="fixed",is_fixed=True),SalaryComponent(component_id="HRA",component_name="Housing",component_type="EARNING",taxable=True,calculation_rule="half basic",is_fixed=True)])
        db.flush()
        db.add(SalaryRevision(revision_id="SR-OLD",employee_id="E1",effective_from=date(2023,1,1),revision_reason="Joining",previous_annual_fixed=None,new_annual_fixed=Decimal("18000.00"),pct_change=None,role_id_after="R1",approved_by=None,created_at=date(2023,1,1)))
        db.add_all([SalaryStructure(structure_id="SS-B",employee_id="E1",component_id="BASIC",component_name="Basic",component_type="EARNING",monthly_amount=Decimal("1000"),effective_from=date(2023,1,1),effective_to=None,revision_id="SR-OLD",is_active=True),SalaryStructure(structure_id="SS-H",employee_id="E1",component_id="HRA",component_name="Housing",component_type="EARNING",monthly_amount=Decimal("500"),effective_from=date(2023,1,1),effective_to=None,revision_id="SR-OLD",is_active=True)])
    db=Factory()
    def override(): yield db
    app.dependency_overrides[get_db]=override
    with TestClient(app,headers={"Authorization":f"Bearer {token('TEST-ADMIN','admin')}"}) as client: yield client,db
    app.dependency_overrides.clear(); db.close(); Base.metadata.drop_all(engine); engine.dispose()

def revision_body(effective="2024-01-01"):
    return {"effective_from":effective,"revision_reason":"Annual increment","components":[{"component_id":"BASIC","monthly_amount":"1200.00"},{"component_id":"HRA","monthly_amount":"600.00"}]}

def test_inclusive_january_boundary_and_history(salary_db):
    client,db=salary_db
    r=client.post("/employees/E1/salary/revisions",json=revision_body()); assert r.status_code==201,r.text
    old=client.get("/employees/E1/salary?effective_date=2023-12-31").json()
    new=client.get("/employees/E1/salary?effective_date=2024-01-01").json()
    assert [x["monthly_amount"] for x in old["components"]]==["1000.00","500.00"]
    assert [x["monthly_amount"] for x in new["components"]]==["1200.00","600.00"]
    assert old["annual_fixed"]=="18000.00" and new["annual_fixed"]=="21600.00"
    assert db.get(SalaryStructure,"SS-B").effective_to==date(2023,12,31)
    history=client.get("/employees/E1/salary/revisions").json()
    assert [x["revision_id"] for x in history]==["SR-OLD",r.json()["revision_id"]]
    assert history[0]["previous_annual_fixed"] is None and history[0]["approved_by"] is None

def test_unknown_employee_salary_endpoints_return_404(salary_db):
    client,_=salary_db
    assert client.get("/employees/nope/salary?effective_date=2024-01-01").status_code==404
    assert client.get("/employees/nope/salary/revisions").status_code==404
    assert client.post("/employees/nope/salary/revisions",json=revision_body()).status_code==404

def test_duplicate_revision_date_rejected(salary_db):
    client,_=salary_db
    assert client.post("/employees/E1/salary/revisions",json=revision_body()).status_code==201
    assert client.post("/employees/E1/salary/revisions",json=revision_body()).status_code==422

def test_failed_revision_rolls_back_closure_and_insert(salary_db):
    client,db=salary_db
    def fail_flush(*args,**kwargs): raise RuntimeError("simulated persistence failure")
    event.listen(db,"before_flush",fail_flush)
    with pytest.raises(RuntimeError,match="simulated persistence failure"):
        client.post("/employees/E1/salary/revisions",json=revision_body())
    event.remove(db,"before_flush",fail_flush)
    assert db.get(SalaryStructure,"SS-B").effective_to is None
    assert db.query(SalaryRevision).count()==1

def test_negative_salary_is_rejected(salary_db):
    client,_=salary_db; body=revision_body(); body["components"][0]["monthly_amount"]="-1"
    assert client.post("/employees/E1/salary/revisions",json=body).status_code==422
