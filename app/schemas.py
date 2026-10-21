from datetime import date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    department_id: str
    department_name: str
    cost_center: str
    description: str | None = None

class RoleOut(BaseModel):
    role_id: str
    department_id: str
    role_title: str
    level: int
    grade: str
    model_config = ConfigDict(from_attributes=True)

class EmployeeCreate(BaseModel):
    employee_id: str = Field(min_length=1, max_length=20)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    full_name: str = Field(min_length=1, max_length=201)
    work_email: str = Field(min_length=3, max_length=255)
    hire_date: date
    employment_status: str = "Active"
    employment_type: str = "Permanent"
    department_id: str
    role_id: str
    manager_id: str | None = None
    work_location: str | None = None
    work_mode: str | None = None

class EmployeePatch(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    full_name: str | None = Field(default=None, min_length=1, max_length=201)
    work_email: str | None = Field(default=None, min_length=3, max_length=255)
    employment_status: str | None = None
    employment_type: str | None = None
    department_id: str | None = None
    role_id: str | None = None
    manager_id: str | None = None
    work_location: str | None = None
    work_mode: str | None = None

class EmployeeOut(BaseModel):
    employee_id: str
    first_name: str
    last_name: str
    full_name: str
    work_email: str
    hire_date: date
    exit_date: date | None
    employment_status: str
    employment_type: str
    department_id: str
    department_name: str | None = None
    role_id: str
    role_title: str | None = None
    manager_id: str | None
    work_location: str | None
    work_mode: str | None
    model_config = ConfigDict(from_attributes=True)

class SalaryComponentAmountIn(BaseModel):
    component_id: str
    monthly_amount: Decimal = Field(ge=Decimal("0"), max_digits=14, decimal_places=2)

class SalaryRevisionCreate(BaseModel):
    effective_from: date
    revision_reason: str = Field(min_length=1, max_length=200)
    components: list[SalaryComponentAmountIn] = Field(min_length=1)
    role_id_after: str | None = None
    approved_by: str | None = Field(default=None, max_length=30)

class SalaryComponentOut(BaseModel):
    component_id: str
    component_name: str
    component_type: str
    taxable: bool
    is_fixed: bool
    monthly_amount: Decimal

class SalaryStructureOut(BaseModel):
    employee_id: str
    effective_date: date
    annual_fixed: Decimal
    components: list[SalaryComponentOut]

class SalaryRevisionOut(BaseModel):
    revision_id: str
    employee_id: str
    effective_from: date
    revision_reason: str
    previous_annual_fixed: Decimal | None
    new_annual_fixed: Decimal
    pct_change: Decimal | None
    role_id_after: str
    approved_by: str | None
    created_at: date
    model_config = ConfigDict(from_attributes=True)
