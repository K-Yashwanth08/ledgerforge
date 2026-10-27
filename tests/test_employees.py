import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
from app.main import app

@pytest.fixture
def client():
    engine=create_engine("sqlite://", connect_args={"check_same_thread":False}, poolclass=StaticPool)
    Base.metadata.create_all(engine); Testing=sessionmaker(bind=engine, autoflush=False)
    def override():
        with Testing() as db: yield db
    app.dependency_overrides[get_db]=override
    with Testing.begin() as db:
        from app.models import Department, Role
        db.add(Department(department_id="D1",department_name="Engineering",cost_center="CC1"))
        db.add(Role(role_id="R1",department_id="D1",role_title="Engineer",level=1,grade="L1",band_min_annual=1,band_mid_annual=2,band_max_annual=3,overtime_eligible="N",band_year=2026))
    with TestClient(app) as c: yield c
    app.dependency_overrides.clear(); Base.metadata.drop_all(engine); engine.dispose()

def payload(id="E1", manager=None):
    return {"employee_id":id,"first_name":"Ada","last_name":"Lovelace","full_name":"Ada Lovelace","work_email":f"{id.lower()}@example.test","hire_date":"2024-01-01","department_id":"D1","role_id":"R1","manager_id":manager,"work_location":"Pune","work_mode":"Hybrid"}

def test_list_and_sensitive_fields_excluded(client):
    client.post("/employees",json=payload())
    r=client.get("/employees"); assert r.status_code==200 and r.json()[0]["employee_id"]=="E1"
    assert "date_of_birth" not in r.json()[0] and "salary" not in r.json()[0]

def test_pagination(client):
    client.post("/employees",json=payload()); client.post("/employees",json=payload("E2"))
    assert len(client.get("/employees?limit=1&offset=0").json())==1

def test_search(client):
    client.post("/employees",json=payload())
    assert len(client.get("/employees?search=Ada").json())==1

def test_department_filter(client):
    client.post("/employees",json=payload())
    assert len(client.get("/employees?department_id=D1").json())==1

def test_create_employee(client):
    r=client.post("/employees",json=payload()); assert r.status_code==201

def test_partial_update(client):
    client.post("/employees",json=payload()); r=client.patch("/employees/E1",json={"work_mode":"Remote"})
    assert r.status_code==200 and r.json()["work_mode"]=="Remote" and r.json()["first_name"]=="Ada"

def test_missing_employee_404(client):
    assert client.get("/employees/nope").status_code==404

def test_invalid_input_422(client):
    body=payload(); body["hire_date"]="not-a-date"
    assert client.post("/employees",json=body).status_code==422

def test_soft_delete(client):
    client.post("/employees",json=payload())
    assert client.delete("/employees/E1").status_code==204
    assert client.get("/employees").json()==[]
    assert client.get("/employees/E1").json()["exit_date"]

def test_team_and_invalid_manager(client):
    client.post("/employees",json=payload())
    client.post("/employees",json=payload("E2","E1"))
    assert [x["employee_id"] for x in client.get("/employees/E1/team").json()]==["E2"]
    assert client.post("/employees",json=payload("E3","missing")).status_code==422

def test_department_role_consistency(client):
    b=payload(); b["department_id"]="D-missing"
    assert client.post("/employees",json=b).status_code==422

def test_role_lookup_is_filtered_for_the_form(client):
    roles=client.get("/roles?department_id=D1")
    assert roles.status_code==200 and roles.json()[0]["role_id"]=="R1"

def test_dashboard_exposes_employee_actions(client):
    page=client.get("/")
    assert page.status_code==200
    assert "Add employee" in page.text and "data-action=\"edit\"" in page.text and "data-action=\"delete\"" in page.text
    assert "not connected" not in page.text.lower()
    assert client.get("/assets/dashboard_sections.js").status_code==200

def test_setting_departed_status_soft_deletes_from_directory(client):
    client.post("/employees",json=payload())
    r=client.patch("/employees/E1",json={"employment_status":"Terminated"})
    assert r.status_code==200 and r.json()["exit_date"]
    assert client.get("/employees").json()==[]
