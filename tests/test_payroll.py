from datetime import date, datetime
from decimal import Decimal
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import (AttendanceRecord, ChartOfAccount, Department, Employee, EmployeeAssignment, EmployeeTaxElection, JournalEntry, JournalLine, PayrollItem, PayrollRun, Role, SalaryComponent,
                        SalaryRevision, SalaryStructure, StatutoryRate, TaxParameter, TaxSlab)
from app.payroll_service import _annual_tax, calculate_employee_month, run_payroll_month
from app.payslip_pdf import build_payslip_pdf, indian_currency
from app.payslip_service import get_payslip_data
from tests.test_attendance_leave import token
from tests.auth_support import seed_test_users

@pytest.fixture
def payroll_client(monkeypatch):
    monkeypatch.setattr(settings,"secret_key","test-only-signing-secret-at-least-32-bytes")
    engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
    Base.metadata.create_all(engine); Factory=sessionmaker(bind=engine,autoflush=False,expire_on_commit=False)
    with Factory.begin() as db:
        db.add(Department(department_id="D1",department_name="Test",cost_center="CC1"))
        db.add(Role(role_id="R1",department_id="D1",role_title="Engineer",level=1,grade="L1",band_min_annual=1,band_mid_annual=2,band_max_annual=3,overtime_eligible="Y",band_year=2026))
        db.add(Employee(employee_id="E1",first_name="Test",last_name="Person",full_name="Test Person",work_email="e1@example.test",hire_date=date(2020,1,1),employment_status="Active",employment_type="Permanent",department_id="D1",role_id="R1",pf_applicable="Y",esi_applicable="N"))
        db.add(EmployeeAssignment(assignment_id="AS1",employee_id="E1",effective_from=date(2020,1,1),effective_to=None,department_id="D1",role_id="R1"))
        db.add(EmployeeTaxElection(election_id="TE1", employee_id="E1", financial_year="FY2025-26",
            regime="NEW", election_date=date(2025,4,1), effective_from=date(2025,4,1),
            effective_to=None, approval_status="APPROVED", submitted_at=datetime(2025,4,1)))
        seed_test_users(db, {"E1": "Employee", "E2": "Employee", "HR1": "HR", "HR2": "HR", "HR3": "HR", "HR4": "HR",
                             "ADMIN1": "Admin", "ADMIN2": "Admin", "ADMIN3": "Admin"})
        db.add_all([SalaryComponent(component_id="BASIC",component_name="Basic",component_type="EARNING",taxable=True,calculation_rule="fixed",is_fixed=True),SalaryComponent(component_id="HRA",component_name="Housing",component_type="EARNING",taxable=True,calculation_rule="fixed",is_fixed=True)])
        db.flush()
        db.add(SalaryRevision(revision_id="SR1",employee_id="E1",effective_from=date(2020,1,1),revision_reason="test",previous_annual_fixed=None,new_annual_fixed=Decimal("18000"),pct_change=None,role_id_after="R1",approved_by=None,created_at=date(2020,1,1)))
        db.add_all([SalaryStructure(structure_id="SS1",employee_id="E1",component_id="BASIC",component_name="Basic",component_type="EARNING",monthly_amount=Decimal("1000"),effective_from=date(2020,1,1),effective_to=None,revision_id="SR1",is_active=True),SalaryStructure(structure_id="SS2",employee_id="E1",component_id="HRA",component_name="Housing",component_type="EARNING",monthly_amount=Decimal("500"),effective_from=date(2020,1,1),effective_to=None,revision_id="SR1",is_active=True)])
        for param,value,unit in [("PF_EMPLOYEE_RATE","12","%"),("PF_EMPLOYER_RATE","12","%"),("PF_WAGE_CEILING","15000","INR"),("ESI_EMPLOYEE_RATE","0.75","%"),("ESI_EMPLOYER_RATE","3.25","%"),("ESI_WAGE_LIMIT","21000","INR"),("PT_MONTHLY","200","INR"),("PT_GROSS_THRESHOLD","25000","INR"),("OT_MULTIPLIER","2","x"),("OT_MONTHLY_CAP_HOURS","50","hours"),("WORKING_HOURS_PER_MONTH","208","hours")]:
            db.add(StatutoryRate(parameter=param,effective_from=date(2025,4,1),value=Decimal(value),unit=unit,note="test"))
        db.add_all([TaxParameter(parameter="standard_deduction",value=Decimal("75000"),note="test"),TaxParameter(parameter="rebate_threshold_taxable",value=Decimal("1200000"),note="test"),TaxParameter(parameter="rebate_amount",value=Decimal("0"),note="test"),TaxParameter(parameter="health_education_cess_percent",value=Decimal("4"),note="test"),TaxSlab(slab_id="T1",regime="NEW",financial_year="FY2025-26",income_from=Decimal("0"),income_to=None,rate_percent=Decimal("0"),effective_from=date(2025,4,1),note="test")])
    session=Factory()
    def override(): yield session
    app.dependency_overrides[get_db]=override
    with TestClient(app) as client: yield client,session
    app.dependency_overrides.clear(); session.close(); Base.metadata.drop_all(engine); engine.dispose()

def auth(sub="E1",role="employee"):
    return {"Authorization":f"Bearer {token(sub,role)}"}

def test_payroll_uses_decimal_and_separates_calculation_components(payroll_client):
    client,db=payroll_client
    from app.models import AttendanceRecord
    db.add(AttendanceRecord(attendance_id="A1",employee_id="E1",attendance_date=date(2025,4,2),weekday="Wed",status="ABSENT_LOP",overtime_hours=Decimal("55"),department_id="D1")); db.commit()
    result=calculate_employee_month(db,"E1","2025-04")
    assert result["monthly_fixed_gross"]==Decimal("1500.00")
    assert result["lop_days"]==1 and result["payable_days"]==29
    assert result["earned_fixed_pay"]==Decimal("1450.00")
    assert result["overtime_hours_paid"]==Decimal("50")
    assert result["overtime_pay"]==Decimal("721.15")
    assert result["gross_pay"]==Decimal("2171.15")
    assert result["pf_employee"]==Decimal("116.00")
    assert result["net_pay"]==Decimal("2055.15")
    assert result["policy_status"] == "UNVERIFIED"
    assert any("not independently verified" in item for item in result["warnings"])

def test_fixed_pay_totals_independently_rounded_salary_components(payroll_client):
    _,db=payroll_client
    basic=db.query(SalaryStructure).filter_by(employee_id="E1",component_id="BASIC").one()
    hra=db.query(SalaryStructure).filter_by(employee_id="E1",component_id="HRA").one()
    basic.monthly_amount=Decimal("10249")
    hra.monthly_amount=Decimal("5124")
    added_components=[
        SalaryComponent(component_id="CONV",component_name="Conveyance",component_type="EARNING",taxable=True,calculation_rule="fixed",is_fixed=True),
        SalaryComponent(component_id="MED",component_name="Medical",component_type="EARNING",taxable=True,calculation_rule="fixed",is_fixed=True),
        SalaryComponent(component_id="SPECIAL",component_name="Special",component_type="EARNING",taxable=True,calculation_rule="fixed",is_fixed=True),
    ]
    db.add_all(added_components)
    db.flush()
    db.add_all([
        SalaryStructure(structure_id="SS3",employee_id="E1",component_id="CONV",component_name="Conveyance",component_type="EARNING",monthly_amount=Decimal("1600"),effective_from=date(2020,1,1),effective_to=None,revision_id="SR1",is_active=True),
        SalaryStructure(structure_id="SS4",employee_id="E1",component_id="MED",component_name="Medical",component_type="EARNING",monthly_amount=Decimal("1250"),effective_from=date(2020,1,1),effective_to=None,revision_id="SR1",is_active=True),
        SalaryStructure(structure_id="SS5",employee_id="E1",component_id="SPECIAL",component_name="Special",component_type="EARNING",monthly_amount=Decimal("7399"),effective_from=date(2020,1,1),effective_to=None,revision_id="SR1",is_active=True),
        AttendanceRecord(attendance_id="LOP-2",employee_id="E1",attendance_date=date(2025,4,1),weekday="Tue",status="ABSENT_LOP",overtime_hours=Decimal("0"),department_id="D1"),
        AttendanceRecord(attendance_id="LOP-3",employee_id="E1",attendance_date=date(2025,4,2),weekday="Wed",status="ABSENT_LOP",overtime_hours=Decimal("0"),department_id="D1"),
    ])
    db.commit()
    result=calculate_employee_month(db,"E1","2025-04")
    assert result["basic"]==Decimal("9565.73")
    assert result["hra"]==Decimal("4782.40")
    assert result["conveyance"]==Decimal("1493.33")
    assert result["medical"]==Decimal("1166.67")
    assert result["special_allowance"]==Decimal("6905.73")
    assert result["earned_fixed_pay"]==Decimal("23913.86")

def test_overtime_rounds_exact_half_cent_up(payroll_client):
    _,db=payroll_client
    basic=db.query(SalaryStructure).filter_by(employee_id="E1",component_id="BASIC").one()
    hra=db.query(SalaryStructure).filter_by(employee_id="E1",component_id="HRA").one()
    basic.monthly_amount=Decimal("35199")
    hra.monthly_amount=Decimal("0")
    db.add(AttendanceRecord(attendance_id="OT-ROUND",employee_id="E1",attendance_date=date(2025,5,2),
        weekday="Fri",status="PRESENT",overtime_hours=Decimal("13"),department_id="D1"))
    db.commit()
    result=calculate_employee_month(db,"E1","2025-05")
    assert result["overtime_pay"]==Decimal("4399.88")

def test_overtime_uses_role_effective_on_each_attendance_date_and_inclusive_boundary(payroll_client):
    client,db=payroll_client
    employee=db.get(Employee,"E1")
    employee.role_id="R2"  # current role is ineligible
    db.add(Role(role_id="R2",department_id="D1",role_title="Analyst",level=1,grade="L1",
        band_min_annual=1,band_mid_annual=2,band_max_annual=3,overtime_eligible="N",band_year=2026))
    old=db.get(EmployeeAssignment,"AS1")
    old.effective_to=date(2025,4,1)  # inclusive: this date remains eligible
    db.add(EmployeeAssignment(assignment_id="AS2",employee_id="E1",effective_from=date(2025,4,2),
        effective_to=None,department_id="D1",role_id="R2"))
    db.add_all([
        AttendanceRecord(attendance_id="OT-OLD",employee_id="E1",attendance_date=date(2025,4,1),
            weekday="Tue",status="PRESENT",overtime_hours=Decimal("3"),department_id="D1"),
        AttendanceRecord(attendance_id="OT-NEW",employee_id="E1",attendance_date=date(2025,4,2),
            weekday="Wed",status="PRESENT",overtime_hours=Decimal("7"),department_id="D1"),
    ])
    db.commit()

    result=calculate_employee_month(db,"E1","2025-04")

    assert result["overtime_hours_paid"]==Decimal("3")
    assert result["overtime_pay"]==Decimal("43.27")
    response=client.get("/payroll/calculate/E1?month=2025-04",headers=auth())
    assert response.status_code==200
    assert Decimal(str(response.json()["overtime_hours_paid"]))==Decimal("3")

def test_payroll_run_is_persisted_and_idempotent(payroll_client):
    import json
    client,db=payroll_client
    first,warnings=run_payroll_month(db,"2025-04",date(2025,5,1))
    second,warnings2=run_payroll_month(db,"2025-04",date(2025,5,1))
    assert first.run_id==second.run_id and db.query(PayrollRun).count()==1 and db.query(PayrollItem).count()==1
    assert first.run_id.endswith("-V2") and first.calculation_version=="ledgerforge-payroll-2"
    assert warnings and warnings2 and first.total_gross==Decimal("1500.00")
    item=db.query(PayrollItem).filter_by(run_id=first.run_id,employee_id="E1").one()
    snapshot=json.loads(item.calculation_input_snapshot)
    assert snapshot["calculation_version"]==first.calculation_version
    assert snapshot["rounding"]=={"currency_decimal_places":2,"mode":"ROUND_HALF_UP"}
    assert snapshot["salary_components"] and snapshot["statutory_rates"]["PF_EMPLOYEE_RATE"]["value"]=="12.0000"
    assert snapshot["tax_slabs"] and snapshot["manual_inputs"]["variable_pay"]=="0.00"
    rate=db.query(StatutoryRate).filter_by(parameter="PF_EMPLOYEE_RATE").one()
    rate.value=Decimal("20");db.commit()
    assert json.loads(item.calculation_input_snapshot)["statutory_rates"]["PF_EMPLOYEE_RATE"]["value"]=="12.0000"
    res=client.get(f"/payroll/runs/{first.run_id}/items",headers=auth())
    assert res.status_code==200 and len(res.json())==1
    assert client.get("/payroll/runs",headers=auth()).status_code==403
    assert client.get("/payroll/runs",headers=auth("HR1","hr")).status_code==200

def test_pending_payroll_run_can_be_returned_without_pay_date(payroll_client):
    client,db=payroll_client
    run=PayrollRun(run_id="PR-PENDING",period_start=date(2026,9,1),period_end=date(2026,9,30),pay_date=None,
        employees_paid=1,total_gross=Decimal("100.00"),total_deductions=Decimal("0.00"),total_net=Decimal("100.00"),
        total_employer_contributions=Decimal("0.00"),total_employer_cost=Decimal("100.00"),
        status="POSTED - PAYMENT PENDING",run_by=None,approved_by=None,created_at=None,approved_at=None,
        idempotency_key=None,journal_entry_id=None,calculation_version="imported")
    db.add(run);db.commit()
    response=client.get("/payroll/runs/PR-PENDING",headers=auth("HR1","hr"))
    assert response.status_code==200 and response.json()["pay_date"] is None

def test_unknown_salary_period_is_not_calculated(payroll_client):
    client,_=payroll_client
    assert client.get("/payroll/calculate/E1?month=2025-4",headers=auth()).status_code==422
    assert client.get("/payroll/calculate/E2?month=2025-04",headers=auth()).status_code==403

def test_new_hire_salary_structure_is_selected_from_hire_date(payroll_client):
    _,db=payroll_client
    employee=db.get(Employee,"E1"); employee.hire_date=date(2025,4,2)
    for structure in db.query(SalaryStructure).filter_by(employee_id="E1").all():
        structure.effective_from=date(2025,4,2)
    db.commit()
    result=calculate_employee_month(db,"E1","2025-04")
    assert result["days_employed"]==29
    assert result["monthly_fixed_gross"]==Decimal("1500.00")
    assert result["earned_fixed_pay"]==Decimal("1450.00")

def test_failed_payroll_run_does_not_persist_partial_results(payroll_client):
    from app.models import AttendanceRecord
    _,db=payroll_client
    db.add(Employee(employee_id="E2",first_name="Second",last_name="Person",full_name="Second Person",
        work_email="e2@example.test",hire_date=date(2020,1,1),employment_status="Active",employment_type="Permanent",
        department_id="D1",role_id="R1",pf_applicable="Y",esi_applicable="N"))
    db.add(EmployeeTaxElection(election_id="TE2", employee_id="E2", financial_year="FY2025-26",
        regime="NEW", election_date=date(2025,4,1), effective_from=date(2025,4,1),
        effective_to=None, approval_status="APPROVED", submitted_at=datetime(2025,4,1)))
    db.add(SalaryRevision(revision_id="SR2",employee_id="E2",effective_from=date(2020,1,1),revision_reason="test",
        previous_annual_fixed=None,new_annual_fixed=Decimal("18000"),pct_change=None,role_id_after="R1",
        approved_by=None,created_at=date(2020,1,1)))
    for structure_id,component_id,name,amount in [("SS3","BASIC","Basic","1000"),("SS4","HRA","Housing","500")]:
        db.add(SalaryStructure(structure_id=structure_id,employee_id="E2",component_id=component_id,
            component_name=name,component_type="EARNING",monthly_amount=Decimal(amount),effective_from=date(2020,1,1),
            effective_to=None,revision_id="SR2",is_active=True))
    db.add(AttendanceRecord(attendance_id="E2-OT",employee_id="E2",attendance_date=date(2025,4,2),weekday="Wed",
        status="PRESENT",overtime_hours=Decimal("1"),department_id="D1"))
    db.commit()
    with pytest.raises(HTTPException,match="No effective role assignment"):
        run_payroll_month(db,"2025-04",date(2025,5,1))
    assert db.query(PayrollRun).count()==0 and db.query(PayrollItem).count()==0

def test_tax_slab_revision_is_selected_by_effective_date(payroll_client):
    _,db=payroll_client
    db.add(TaxSlab(slab_id="T2",regime="NEW",financial_year="FY2025-26",income_from=Decimal("0"),
        income_to=None,rate_percent=Decimal("100"),effective_from=date(2025,5,1),note="test revision"))
    db.commit()
    params={"standard_deduction":Decimal("0"),"rebate_threshold_taxable":Decimal("0"),"rebate_amount":Decimal("0"),
            "health_education_cess_percent":Decimal("0")}
    april=_annual_tax(db,Decimal("1000"),"FY2025-26",params,date(2025,4,1))
    may=_annual_tax(db,Decimal("1000"),"FY2025-26",params,date(2025,5,1))
    assert april==Decimal("0.00") and may==Decimal("1000.00")

def test_tax_calculation_uses_the_selected_regime_slabs(payroll_client):
    _, db = payroll_client
    db.add(TaxSlab(slab_id="OLD-TAX", regime="OLD", financial_year="FY2025-26",
        income_from=Decimal("0"), income_to=None, rate_percent=Decimal("10"),
        effective_from=date(2025,4,1), note="test"))
    db.commit()
    params={"standard_deduction":Decimal("0"),"rebate_threshold_taxable":Decimal("0"),
        "rebate_amount":Decimal("0"),"health_education_cess_percent":Decimal("0")}
    new_tax=_annual_tax(db,Decimal("1000"),"FY2025-26",params,date(2025,4,1),"NEW")
    old_tax=_annual_tax(db,Decimal("1000"),"FY2025-26",params,date(2025,4,1),"OLD")
    assert new_tax==Decimal("0.00") and old_tax==Decimal("100.00")

def test_task14_configurations_are_admin_only_effective_dated_and_change_recalculation(payroll_client):
    client, db = payroll_client
    assert calculate_employee_month(db, "E1", "2025-04")["tds"] == Decimal("0.00")
    assert client.get("/tax/configuration", headers=auth("HR1", "hr")).status_code == 200
    slab_body = {"financial_year": "FY2025-26", "regime": "NEW", "effective_from": "2025-05-01",
        "note": "Approved test policy source; isolated test configuration",
        "slabs": [{"lower_limit": "0", "upper_limit": None, "tax_rate": "50"}]}
    assert client.post("/tax/configuration/slabs", json=slab_body,
        headers=auth("HR1", "hr")).status_code == 403
    bad = {**slab_body, "slabs": [
        {"lower_limit": "0", "upper_limit": "100", "tax_rate": "10"},
        {"lower_limit": "99", "upper_limit": None, "tax_rate": "20"}]}
    assert client.post("/tax/configuration/slabs", json=bad,
        headers=auth("ADMIN1", "admin")).status_code == 422
    assert client.post("/tax/configuration/slabs", json=slab_body,
        headers=auth("ADMIN1", "admin")).status_code == 201
    params = {"financial_year": "FY2025-26", "regime": "NEW", "effective_from": "2025-05-01",
        "note": "Approved test policy source; isolated test configuration",
        "values": {"standard_deduction": "0", "rebate_threshold_taxable": "0", "rebate_amount": "0",
                    "health_education_cess_percent": "0"}}
    assert client.post("/tax/configuration/parameters", json=params,
        headers=auth("ADMIN1", "admin")).status_code == 201
    assert calculate_employee_month(db, "E1", "2025-05")["tds"] == Decimal("750.00")
    assert calculate_employee_month(db, "E1", "2025-04")["tds"] == Decimal("0.00")

def test_task14_monthly_statutory_report_reconciles_to_payroll_run(payroll_client):
    client, db = payroll_client
    run_payroll_month(db, "2025-04", date(2025, 5, 1))
    response = client.get("/reports/statutory/monthly?start_date=2025-04-01&end_date=2025-04-30",
        headers=auth("HR1", "hr"))
    assert response.status_code == 200
    result = response.json()
    assert result["reconciled"] is True
    assert result["policy_status"] == "UNVERIFIED"
    assert result["official_compliance_claimed"] is False
    assert Decimal(str(result["totals"]["pf_employee"])) == Decimal("120.00")
    assert Decimal(str(result["totals"]["tds"])) == Decimal("0.00")

def test_employee_tax_elections_and_declarations_are_owned_approved_and_audited(payroll_client):
    client, db = payroll_client
    existing_election = db.get(EmployeeTaxElection, "TE1")
    existing_election.effective_to = date(2025, 4, 30)
    db.commit()
    election = {"financial_year": "FY2025-26", "regime": "OLD",
        "election_date": "2025-04-01", "effective_from": "2025-05-01", "effective_to": None}
    submitted = client.post("/tax/elections", json=election, headers=auth())
    assert submitted.status_code == 201 and submitted.json()["approval_status"] == "PENDING"
    election_id = submitted.json()["election_id"]
    assert client.post("/tax/elections", json={**election, "effective_from": "2025-06-01"},
        headers=auth()).status_code == 409
    assert client.post("/tax/elections", json={**election, "employee_id": "E2"},
        headers=auth()).status_code == 403
    assert client.get("/tax/elections/E2", headers=auth()).status_code == 403
    reviewed = client.post(f"/tax/elections/{election_id}/review",
        json={"decision": "APPROVED", "note": "verified test election"}, headers=auth("HR1", "hr"))
    assert reviewed.status_code == 200 and reviewed.json()["approval_status"] == "APPROVED"
    assert reviewed.json()["reviewed_by"] == "HR1"

    declaration = {"financial_year": "FY2025-26", "deduction_code": "DECLARED_DEDUCTION",
        "declared_amount": "12345.67", "supporting_document_reference": "vault://test/ref-1"}
    response = client.post("/tax/declarations", json=declaration, headers=auth())
    assert response.status_code == 201 and response.json()["approval_status"] == "PENDING"
    declaration_id = response.json()["declaration_id"]
    assert client.post("/tax/declarations", json={**declaration, "employee_id": "E2"},
        headers=auth()).status_code == 403
    assert client.get("/tax/declarations/E2", headers=auth()).status_code == 403
    approved = client.post(f"/tax/declarations/{declaration_id}/review",
        json={"decision": "APPROVED", "note": "documents checked"}, headers=auth("HR1", "hr"))
    assert approved.status_code == 200 and approved.json()["approval_status"] == "APPROVED"
    audit = client.get("/tax/audit/E1", headers=auth())
    assert audit.status_code == 200 and [event["action"] for event in audit.json()] == [
        "SUBMITTED", "APPROVED", "SUBMITTED", "APPROVED"]

def test_payroll_fails_closed_when_employee_has_no_approved_tax_election(payroll_client):
    client, db = payroll_client
    election = db.get(EmployeeTaxElection, "TE1")
    db.delete(election)
    db.commit()
    with pytest.raises(HTTPException, match="No approved tax-regime election"):
        calculate_employee_month(db, "E1", "2025-04")
    assert client.get("/payroll/calculate/E1?month=2025-04", headers=auth()).status_code == 503

def test_payroll_fails_closed_when_applicable_policy_is_sample(payroll_client):
    _, db = payroll_client
    db.query(StatutoryRate).filter_by(parameter="PF_EMPLOYEE_RATE").one().note = "SAMPLE policy input"
    db.commit()
    with pytest.raises(HTTPException, match="configuration is sample data"):
        calculate_employee_month(db, "E1", "2025-04")

def test_payslip_pdf_is_readable_and_matches_persisted_run(payroll_client):
    from pypdf import PdfReader
    from io import BytesIO
    client,db=payroll_client
    db.add(AttendanceRecord(attendance_id="LOP-1",employee_id="E1",attendance_date=date(2025,4,15),
        weekday="Tue",status="ABSENT_LOP",overtime_hours=Decimal("0"),department_id="D1"));db.commit()
    run,_=run_payroll_month(db,"2025-04",date(2025,5,1))
    data=get_payslip_data(db,"E1",run.run_id)
    pdf=build_payslip_pdf(data)
    reader=PdfReader(BytesIO(pdf)); text="\n".join(p.extract_text() or "" for p in reader.pages)
    item=db.query(PayrollItem).filter_by(run_id=run.run_id,employee_id="E1").one()
    amounts={row["label"]:row["amount"] for row in data["earnings"]}
    assert amounts["Basic salary"]==item.basic
    assert amounts["House rent allowance"]==item.hra
    assert sum(amounts.values(),Decimal("0.00"))==item.gross_pay
    assert sum((row["amount"] for row in data["deductions"]),Decimal("0.00"))==item.total_deductions
    assert (len(reader.pages)==1 and "NET PAY" in text and indian_currency(item.gross_pay) in text
            and indian_currency(item.total_deductions) in text and indian_currency(item.net_pay) in text)
    r=client.get(f"/payslips/E1/{run.run_id}",headers=auth())
    assert r.status_code==200 and r.headers["content-type"]=="application/pdf"
    assert r.headers["content-disposition"]==f'attachment; filename="payslip-E1-{run.run_id}.pdf"'

def test_payslip_owner_hr_and_invalid_identifiers(payroll_client):
    client,db=payroll_client
    run,_=run_payroll_month(db,"2025-04",date(2025,5,1))
    assert client.get(f"/payslips/E1/{run.run_id}").status_code==401
    assert client.get("/payslips/employee/E1/runs").status_code==401
    available=client.get("/payslips/employee/E1/runs",headers=auth())
    assert available.status_code==200 and available.json()[0]["run_id"]==run.run_id
    assert Decimal(str(available.json()[0]["net_pay"]))==db.query(PayrollItem).filter_by(run_id=run.run_id,employee_id="E1").one().net_pay
    assert client.get("/payslips/employee/E1/runs",headers=auth("E2")).status_code==403
    assert client.get("/payslips/employee/E2/runs",headers=auth("E2")).status_code==403
    assert client.get(f"/payslips/E1/{run.run_id}",headers=auth("E2")).status_code==403
    assert client.get(f"/payslips/E1/{run.run_id}",headers=auth("HR1","hr")).status_code==200
    assert client.get("/payslips/E1/unknown",headers=auth()).status_code==404
    assert client.get(f"/payslips/E2/{run.run_id}",headers=auth("E2")).status_code==403

def test_indian_currency_grouping_uses_decimal():
    assert indian_currency(Decimal("123456.78"))=="INR 1,23,456.78"

def test_company_legal_details_are_configurable_and_rendered(payroll_client,monkeypatch):
    from io import BytesIO
    from pypdf import PdfReader
    from app.config import settings
    client,db=payroll_client
    monkeypatch.setattr(settings,"company_legal_name","LedgerForge Registered Private Limited")
    monkeypatch.setattr(settings,"company_address","14 Finance Park, Bengaluru & Karnataka")
    monkeypatch.setattr(settings,"company_contact_email","payroll@example.org")
    monkeypatch.setattr(settings,"company_contact_phone",None)
    run,_=run_payroll_month(db,"2025-04",date(2025,5,1))
    data=get_payslip_data(db,"E1",run.run_id)
    assert data["company_details_configured"] is True and data["company_details_note"] is None
    response=client.get(f"/payslips/E1/{run.run_id}",headers=auth())
    text="\n".join(p.extract_text() or "" for p in PdfReader(BytesIO(response.content)).pages)
    assert "LedgerForge Registered Private Limited" in text
    assert "14 Finance Park, Bengaluru & Karnataka" in text
    assert "payroll@example.org" in text

def test_company_details_reject_unreplaced_placeholders_and_invalid_email():
    from pydantic import ValidationError
    from app.config import Settings
    with pytest.raises(ValidationError):
        Settings(_env_file=None,company_legal_name="REPLACE_WITH_REGISTERED_LEGAL_NAME")
    with pytest.raises(ValidationError):
        Settings(_env_file=None,company_contact_email="not-an-email")

def test_payroll_draft_process_approve_pay_and_reverse_lifecycle(payroll_client):
    client,db=payroll_client
    account_rows=[("1001","Bank - Test","ASSET","DEBIT"),("1300","Employee advances","ASSET","DEBIT"),
        ("2100","Salaries Payable","LIABILITY","CREDIT"),("2110","PF Payable","LIABILITY","CREDIT"),
        ("2120","ESI Payable","LIABILITY","CREDIT"),("2130","TDS Payable","LIABILITY","CREDIT"),
        ("2140","PT Payable","LIABILITY","CREDIT"),("5001","Wages","EXPENSE","DEBIT"),
        ("5002","Overtime","EXPENSE","DEBIT"),("5003","Variable pay","EXPENSE","DEBIT"),
        ("5004","Employer PF","EXPENSE","DEBIT"),("5005","Employer ESI","EXPENSE","DEBIT")]
    db.add_all([ChartOfAccount(account_code=code,account_name=name,account_type=kind,normal_balance=normal,
        parent_code=None,is_group=False,statement="Test",is_active=True) for code,name,kind,normal in account_rows])
    db.commit()
    draft_body={"month":"2025-04","pay_date":"2025-05-01","idempotency_key":"april-run-draft-001"}
    draft=client.post("/payroll/runs/draft",json=draft_body,headers=auth("HR1","hr"))
    assert draft.status_code==201 and draft.json()["status"]=="DRAFT"
    run_id=draft.json()["run_id"]
    repeated_draft=client.post("/payroll/runs/draft",json=draft_body,headers=auth("HR1","hr"))
    assert repeated_draft.json()["run_id"]==run_id
    payment_body={"payment_date":"2025-05-03","bank_account_code":"1001","payment_mode":"NEFT",
        "idempotency_key":"april-run-payment-001"}
    assert client.post(f"/payroll/runs/{run_id}/payments",json=payment_body,headers=auth("HR1","hr")).status_code==403
    processed=client.post(f"/payroll/runs/{run_id}/process",headers=auth("HR1","hr"))
    assert processed.status_code==200 and processed.json()["status"]=="PROCESSED"
    assert processed.json()["employees_paid"]==1
    processed_again=client.post(f"/payroll/runs/{run_id}/process",headers=auth("HR1","hr"))
    assert processed_again.json()["run_id"]==run_id and db.query(PayrollRun).count()==1
    approved=client.post(f"/payroll/runs/{run_id}/approve",headers=auth("ADMIN1","admin"))
    assert approved.status_code==200 and approved.json()["status"]=="APPROVED"
    payroll_entry=db.get(JournalEntry,approved.json()["journal_entry_id"])
    assert payroll_entry.total_debit==payroll_entry.total_credit
    payment=client.post(f"/payroll/runs/{run_id}/payments",json=payment_body,headers=auth("ADMIN2","admin"))
    assert payment.status_code==201 and Decimal(str(payment.json()["amount"]))==Decimal(str(approved.json()["total_net"]))
    assert db.get(JournalEntry,payment.json()["ledger_entry_id"]).total_debit==db.get(JournalEntry,payment.json()["ledger_entry_id"]).total_credit
    replay=client.post(f"/payroll/runs/{run_id}/payments",json=payment_body,headers=auth("ADMIN2","admin"))
    assert replay.status_code==201 and replay.json()["ledger_entry_id"]==payment.json()["ledger_entry_id"]
    reversed_run=client.post(f"/payroll/runs/{run_id}/reverse",json={"entry_date":"2025-05-04","reason":"Test reversal"},headers=auth("ADMIN3","admin"))
    assert reversed_run.status_code==200 and reversed_run.json()["status"]=="REVERSED"
    for entry_id in (reversed_run.json()["reversal_entry_id"],reversed_run.json()["payment_reversal_entry_id"]):
        entry=db.get(JournalEntry,entry_id)
        assert entry.total_debit==entry.total_credit
    assert db.query(PayrollItem).count()==1 and db.query(JournalEntry).count()==4
