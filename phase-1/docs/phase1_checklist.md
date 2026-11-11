# Phase 1 checklist

| Requirement | Status | Evidence |
|---|---|---|
| FastAPI health, departments, Swagger | Verified | `GET /health`, `/departments`, `/docs` smoke check |
| Browser employee dashboard | Verified | `GET /` returned HTML; uses employee and department APIs |
| Department, role, employee, assignment, and salary models | Implemented | `app/models.py`, Alembic revisions `32155c5c0f3f`, `1870488a8545`, `fbedb25799e5` |
| Official company CSV loader | Verified | CSV/DB counts: 11, 58, 745, 1,606, 14, 2,459, 12,295; idempotency confirmed |
| Employee REST endpoints | Implemented and tested | `app/routers/employees.py`, pytest suite |
| Soft delete and active team behavior | Implemented and tested | Employee API and tests |
| Salary models, loader, service, and APIs | Implemented and tested | Salary CSVs: 14 components, 2,459 revisions, 12,295 structures; migration and boundary tests passed |
| Official validator | Blocked by missing finance files | `04_Validation_Vault/verify_ledgerforge.py` and `../03_Data/csv` are absent; root validator dependencies unavailable |
| Ruff/lint run | Not run | Ruff is not configured/installed |
| Git tags/milestones | Not created | Awaiting user review/approval; existing `master` branch preserved |
