# API examples

Open `/docs` for interactive requests. The dashboard is at `/`.

```http
GET /health
GET /departments
GET /roles?department_id=D01
GET /employees?limit=20&offset=0&search=Anita&department_id=D01
GET /employees/EMP-0001
GET /employees/EMP-0001/team
```

Create a record with `POST /employees` and JSON containing `employee_id`, `first_name`, `last_name`, `full_name`, `work_email`, `hire_date`, `department_id`, and `role_id`. `manager_id` is optional. Update only supplied fields with `PATCH /employees/{employee_id}`. `DELETE` sets the exit date/status and retains the row. Employee list/detail responses intentionally exclude date of birth and compensation.

List and team routes show active employees only (`exit_date IS NULL`). Detail lookup can retrieve a departed employee for audit.

Salary history endpoints:

```http
GET /employees/EMP-0001/salary?effective_date=2026-10-01
GET /employees/EMP-0001/salary/revisions
```

For a change, `POST /employees/{employee_id}/salary/revisions` accepts `effective_from`, `revision_reason`, and a `components` array of `{ "component_id": "BASIC", "monthly_amount": "52000.00" }` values. Amounts are Decimal and nonnegative. Optional `role_id_after` and `approved_by` are retained on the revision.
