import shutil
from datetime import date
from decimal import Decimal
import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base
from app.models import Department, Role, Employee, EmployeeAssignment, SalaryComponent, SalaryRevision, SalaryStructure
from scripts import load_company_data as loader
from app.salary_service import get_structure, get_revision_history

@pytest.fixture
def isolated_loader(tmp_path, monkeypatch):
    engine=create_engine("sqlite://", connect_args={"check_same_thread":False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(loader,"engine",engine)
    monkeypatch.setattr(loader,"SessionLocal",sessionmaker(bind=engine,autoflush=False))
    monkeypatch.setattr(loader.settings,"data_dir",str(tmp_path / "data"))
    data=tmp_path / "data"; data.mkdir()
    for name in ("departments.csv","roles.csv","employees.csv","employee_assignments.csv","salary_components.csv","salary_revisions.csv","salary_structures.csv"):
        shutil.copy(loader.Path(__file__).parents[1] / "data" / name, data / name)
    yield engine, data
    engine.dispose()

def counts(engine):
    with sessionmaker(bind=engine)() as db:
        return tuple(db.query(m).count() for m in (Department,Role,Employee,EmployeeAssignment,SalaryComponent,SalaryRevision,SalaryStructure))

def test_loader_is_idempotent(isolated_loader):
    engine,_=isolated_loader
    loader.main(); first=counts(engine)
    loader.main(); second=counts(engine)
    assert first==(11,58,745,1606,14,2459,12295) and second==first
    with sessionmaker(bind=engine)() as db:
        joining=db.get(SalaryRevision,"SR-00001")
        assert joining.previous_annual_fixed is None and joining.pct_change is None and joining.approved_by is None
        assert db.query(SalaryStructure).filter_by(is_active=False).count()==5
        before=get_structure(db,"EMP-0079",date(2021,3,31))
        after=get_structure(db,"EMP-0079",date(2021,4,1))
        assert next(x for x in before["components"] if x["component_id"]=="BASIC")["monthly_amount"]==Decimal("18518.00")
        assert next(x for x in after["components"] if x["component_id"]=="BASIC")["monthly_amount"]==Decimal("20694.00")
        assert {x.revision_id for x in get_revision_history(db,"EMP-0079")} >= {"SR-00439","SR-00440"}

def test_failed_loader_keeps_previous_data(isolated_loader):
    engine,data=isolated_loader
    loader.main(); before=counts(engine)
    employees=pd.read_csv(data / "employees.csv",dtype=str,keep_default_na=False)
    employees.loc[0,"work_email"]=employees.loc[1,"work_email"]
    employees.to_csv(data / "employees.csv",index=False)
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        loader.main()
    assert counts(engine)==before
