"""Idempotently import the supplied organization CSVs as one transaction."""
from pathlib import Path
from decimal import Decimal
import pandas as pd
from sqlalchemy import delete
from app.config import settings
from app.database import Base, engine, SessionLocal
from app.models import Department, Role, Employee, EmployeeAssignment, SalaryComponent, SalaryStructure, SalaryRevision

FILES = {"departments":("departments.csv", Department), "roles":("roles.csv", Role), "employees":("employees.csv", Employee), "employee_assignments":("employee_assignments.csv", EmployeeAssignment), "salary_components":("salary_components.csv", SalaryComponent), "salary_revisions":("salary_revisions.csv", SalaryRevision), "salary_structures":("salary_structures.csv", SalaryStructure)}
DATE_FIELDS = {"hire_date", "exit_date", "date_of_birth", "resignation_date", "created_at", "effective_from", "effective_to"}
INT_FIELDS = {"level", "band_year", "career_gap_months", "notice_period_days", "job_level"}
FLOAT_FIELDS = {"band_min_annual", "band_mid_annual", "band_max_annual", "prior_experience_years", "commute_distance_km"}
DECIMAL_FIELDS = {"monthly_amount", "previous_annual_fixed", "new_annual_fixed", "pct_change"}

def read_table(filename, model):
    path = Path(settings.data_dir) / filename
    if not path.is_file(): raise FileNotFoundError(f"Required company CSV is missing: {path}")
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    required = {c.name for c in model.__table__.columns if not c.nullable and not c.autoincrement and c.default is None and c.server_default is None}
    missing = required - set(df.columns)
    if missing: raise ValueError(f"{path} is missing required columns: {', '.join(sorted(missing))}")
    if df.empty: raise ValueError(f"{path} contains no rows")
    if df.iloc[:,0].duplicated().any(): raise ValueError(f"{path} contains duplicate identifiers")
    rows=[]
    for row in df.to_dict("records"):
        clean={}
        for key,value in row.items():
            if value == "": clean[key]=None
            elif key in DATE_FIELDS: clean[key]=pd.to_datetime(value, errors="raise").date()
            elif key in INT_FIELDS: clean[key]=int(value)
            elif key in DECIMAL_FIELDS: clean[key]=Decimal(value)
            elif key in FLOAT_FIELDS: clean[key]=float(value)
            elif key in {"taxable", "is_fixed"}:
                if value not in {"Y", "N"}: raise ValueError(f"{path}: {key} must be Y or N")
                clean[key]=value == "Y"
            else: clean[key]=value
        rows.append(clean)
    return rows

def main():
    tables={name:read_table(*spec) for name,spec in FILES.items()}
    # Check references up front so errors are understandable and no rows are changed.
    dept_ids={r["department_id"] for r in tables["departments"]}
    role_ids={r["role_id"] for r in tables["roles"]}
    emp_ids={r["employee_id"] for r in tables["employees"]}
    component_ids={r["component_id"] for r in tables["salary_components"]}
    revision_ids={r["revision_id"] for r in tables["salary_revisions"]}
    for row in tables["roles"]:
        if row["department_id"] not in dept_ids: raise ValueError(f"Role {row['role_id']} references unknown department {row['department_id']}")
    for row in tables["employees"]:
        if row["department_id"] not in dept_ids or row["role_id"] not in role_ids: raise ValueError(f"Employee {row['employee_id']} references an unknown department or role")
        if row["manager_id"] and row["manager_id"] not in emp_ids: raise ValueError(f"Employee {row['employee_id']} references unknown manager {row['manager_id']}")
    for row in tables["employee_assignments"]:
        if row["employee_id"] not in emp_ids or row["department_id"] not in dept_ids or row["role_id"] not in role_ids: raise ValueError(f"Assignment {row['assignment_id']} has an unknown employee, department or role")
        if row["effective_to"] and row["effective_to"] < row["effective_from"]: raise ValueError(f"Assignment {row['assignment_id']} ends before it starts")
    for row in tables["salary_revisions"]:
        if row["employee_id"] not in emp_ids or row["role_id_after"] not in role_ids: raise ValueError(f"Salary revision {row['revision_id']} references an unknown employee or role")
        if row["new_annual_fixed"] < 0 or (row["previous_annual_fixed"] is not None and row["previous_annual_fixed"] < 0): raise ValueError(f"Salary revision {row['revision_id']} contains a negative salary")
    current_roles={row["employee_id"]:row["role_id"] for row in tables["employees"]}
    latest_revisions={}
    for row in sorted(tables["salary_revisions"],key=lambda x:(x["effective_from"],x["revision_id"])):
        latest_revisions[row["employee_id"]]=row
    for employee_id, revision in latest_revisions.items():
        if revision["role_id_after"] != current_roles[employee_id]: raise ValueError(f"Latest salary revision role does not match employee {employee_id} current role")
    revisions={r["revision_id"]:r for r in tables["salary_revisions"]}
    components={r["component_id"]:r for r in tables["salary_components"]}
    invalid_period_ids=set()
    for row in tables["salary_structures"]:
        if row["employee_id"] not in emp_ids or row["component_id"] not in component_ids or row["revision_id"] not in revision_ids: raise ValueError(f"Salary structure {row['structure_id']} references an unknown employee, component or revision")
        if revisions[row["revision_id"]]["employee_id"] != row["employee_id"] or revisions[row["revision_id"]]["effective_from"] != row["effective_from"]: raise ValueError(f"Salary structure {row['structure_id']} disagrees with its revision employee/date")
        component=components[row["component_id"]]
        if (row["component_name"],row["component_type"]) != (component["component_name"],component["component_type"]): raise ValueError(f"Salary structure {row['structure_id']} component snapshot does not match component master")
        if row["monthly_amount"] < 0: raise ValueError(f"Salary structure {row['structure_id']} contains a negative amount")
        if row["effective_to"] and row["effective_to"] < row["effective_from"]:
            invalid_period_ids.add(row["structure_id"])
    # Keep every source row; explicitly disable the five empty/reversed source periods.
    for row in tables["salary_structures"]:
        row["is_active"] = row["structure_id"] not in invalid_period_ids
    intervals={}
    for row in tables["salary_structures"]:
        if not row["is_active"]: continue
        key=(row["employee_id"],row["component_id"])
        intervals.setdefault(key,[]).append(row)
    for key, rows in intervals.items():
        end=None; seen=False
        for row in sorted(rows,key=lambda x:x["effective_from"]):
            if seen and (end is None or row["effective_from"] <= end): raise ValueError(f"Overlapping active salary periods for {key}")
            end=row["effective_to"]; seen=True
    fixed_by_revision={}
    for row in tables["salary_structures"]:
        component=components[row["component_id"]]
        if component["component_type"] == "EARNING" and component["is_fixed"]:
            fixed_by_revision[row["revision_id"]]=fixed_by_revision.get(row["revision_id"],Decimal("0"))+row["monthly_amount"]
    for revision in tables["salary_revisions"]:
        annual=(fixed_by_revision.get(revision["revision_id"],Decimal("0"))*Decimal("12")).quantize(Decimal("0.01"))
        if annual != revision["new_annual_fixed"]: raise ValueError(f"Salary revision {revision['revision_id']} annual fixed amount does not match fixed earning components")
    if invalid_period_ids:
        print(f"Source data note: preserving {len(invalid_period_ids)} invalid salary periods as inactive: {', '.join(sorted(invalid_period_ids))}")
    with SessionLocal.begin() as db:
        # Replace only the company-owned data atomically, deleting children first.
        db.execute(delete(SalaryStructure)); db.execute(delete(SalaryRevision)); db.execute(delete(EmployeeAssignment))
        db.execute(delete(Employee)); db.execute(delete(Role)); db.execute(delete(Department)); db.execute(delete(SalaryComponent))
        db.add_all([Department(**r) for r in tables["departments"]]); db.flush()
        db.add_all([Role(**r) for r in tables["roles"]]); db.flush()
        db.add_all([SalaryComponent(**r) for r in tables["salary_components"]]); db.flush()
        employees=[Employee(**{**r,"manager_id":None}) for r in tables["employees"]]
        db.add_all(employees); db.flush()
        for row in tables["employees"]:
            db.query(Employee).filter_by(employee_id=row["employee_id"]).update({"manager_id":row["manager_id"]}, synchronize_session=False)
        db.add_all([EmployeeAssignment(**r) for r in tables["employee_assignments"]])
        db.add_all([SalaryRevision(**r) for r in tables["salary_revisions"]]); db.flush()
        db.add_all([SalaryStructure(**r) for r in tables["salary_structures"]])
    print("Company data loaded transactionally:")
    with SessionLocal() as db:
        for name,(_,model) in FILES.items():
            count=db.query(model).count(); print(f"  {name}: CSV {len(tables[name])} / database {count}")
            if count != len(tables[name]): raise RuntimeError(f"Count mismatch for {name}")

if __name__ == "__main__":
    main()
