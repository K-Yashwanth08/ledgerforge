from datetime import date
from decimal import Decimal
from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

class Department(Base):
    __tablename__ = "departments"
    department_id: Mapped[str] = mapped_column(String(10), primary_key=True)
    department_name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    cost_center: Mapped[str] = mapped_column(String(20))
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    roles: Mapped[list["Role"]] = relationship(back_populates="department")

class Role(Base):
    __tablename__ = "roles"
    role_id: Mapped[str] = mapped_column(String(10), primary_key=True)
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.department_id"), index=True)
    role_title: Mapped[str] = mapped_column(String(150))
    level: Mapped[int] = mapped_column(Integer)
    grade: Mapped[str] = mapped_column(String(100))
    band_min_annual: Mapped[float] = mapped_column(Numeric(12, 2))
    band_mid_annual: Mapped[float] = mapped_column(Numeric(12, 2))
    band_max_annual: Mapped[float] = mapped_column(Numeric(12, 2))
    overtime_eligible: Mapped[str] = mapped_column(String(1))
    band_year: Mapped[int] = mapped_column(Integer)
    department: Mapped[Department] = relationship(back_populates="roles")

class Employee(Base):
    __tablename__ = "employees"
    employee_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    full_name: Mapped[str] = mapped_column(String(201), index=True)
    work_email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    gender: Mapped[str | None] = mapped_column(String(30), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    hire_date: Mapped[date] = mapped_column(Date)
    exit_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    employment_status: Mapped[str] = mapped_column(String(30), index=True)
    employment_type: Mapped[str] = mapped_column(String(30))
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.department_id"), index=True)
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.role_id"), index=True)
    manager_id: Mapped[str | None] = mapped_column(ForeignKey("employees.employee_id"), nullable=True, index=True)
    work_location: Mapped[str | None] = mapped_column(String(100), nullable=True)
    work_mode: Mapped[str | None] = mapped_column(String(30), nullable=True)
    highest_education: Mapped[str | None] = mapped_column(String(150), nullable=True)
    prior_experience_years: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    career_gap_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    commute_distance_km: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    pf_applicable: Mapped[str | None] = mapped_column(String(1), nullable=True)
    esi_applicable: Mapped[str | None] = mapped_column(String(1), nullable=True)
    notice_period_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resignation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    exit_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(150), nullable=True)
    created_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    department: Mapped[Department] = relationship()
    role: Mapped[Role] = relationship()
    manager: Mapped["Employee | None"] = relationship(remote_side="Employee.employee_id", foreign_keys=[manager_id])

class EmployeeAssignment(Base):
    __tablename__ = "employee_assignments"
    assignment_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.employee_id"), index=True)
    effective_from: Mapped[date] = mapped_column(Date, index=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.department_id"))
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.role_id"))
    job_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    manager_id: Mapped[str | None] = mapped_column(ForeignKey("employees.employee_id"), nullable=True)
    change_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)

class SalaryComponent(Base):
    __tablename__ = "salary_components"
    component_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    component_name: Mapped[str] = mapped_column(String(120), unique=True)
    component_type: Mapped[str] = mapped_column(String(40), index=True)
    taxable: Mapped[bool] = mapped_column(default=False)
    calculation_rule: Mapped[str] = mapped_column(String(500))
    is_fixed: Mapped[bool] = mapped_column(default=False)
    structures: Mapped[list["SalaryStructure"]] = relationship(back_populates="component")

class SalaryRevision(Base):
    __tablename__ = "salary_revisions"
    revision_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.employee_id"), index=True)
    effective_from: Mapped[date] = mapped_column(Date, index=True)
    revision_reason: Mapped[str] = mapped_column(String(200))
    previous_annual_fixed: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    new_annual_fixed: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    pct_change: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    role_id_after: Mapped[str] = mapped_column(ForeignKey("roles.role_id"), index=True)
    approved_by: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[date] = mapped_column(Date)
    __table_args__ = (CheckConstraint("new_annual_fixed >= 0", name="ck_salary_revision_new_nonnegative"),)

class SalaryStructure(Base):
    __tablename__ = "salary_structures"
    structure_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.employee_id"), index=True)
    component_id: Mapped[str] = mapped_column(ForeignKey("salary_components.component_id"), index=True)
    component_name: Mapped[str] = mapped_column(String(120))  # source snapshot
    component_type: Mapped[str] = mapped_column(String(40))  # source snapshot
    monthly_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    effective_from: Mapped[date] = mapped_column(Date, index=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    revision_id: Mapped[str] = mapped_column(ForeignKey("salary_revisions.revision_id"), index=True)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    component: Mapped[SalaryComponent] = relationship(back_populates="structures")
    __table_args__ = (
        CheckConstraint("monthly_amount >= 0", name="ck_salary_structure_nonnegative"),
        CheckConstraint("effective_to IS NULL OR effective_to >= effective_from OR is_active = 0", name="ck_salary_structure_dates"),
        Index("ix_salary_structure_lookup", "employee_id", "effective_from", "effective_to", "is_active"),
        Index("uq_active_salary_component_start", "employee_id", "component_id", "effective_from", unique=True,
              sqlite_where=text("is_active = 1"), postgresql_where=text("is_active")),
    )
