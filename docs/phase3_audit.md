# Phase 3 Audit and Dependency Plan

## Repository baseline

- Branch: `master`, tracking `origin/master`.
- Latest commit: `b00bcdb Implement Phase 2 attendance payroll and accounting`.
- Existing tags: `phase-1`, `phase-2`, and `v0.0.1`.
- Working tree was clean before this audit. No database migration, data loader, or application code was changed.
- Phase 2 includes employee, salary, attendance, leave, payroll calculation, ledger, invoice, receivable, and external JWT validation code. `docs/phase2_task7_blockers.md` documents unprovided payroll events, loan schedules, employee tax inputs, and authoritative statutory rules.
- `app/security.py` validates tokens issued by an upstream provider; it does not issue login tokens. The supplied `data/roles.csv` is the employee job-role catalog, not a demo user/permission list.

## Verification baseline

Command: `python verify_ledgerforge.py summary --data data`

```text
Revenue  1,260,930,052.00
Expenses 1,036,246,464.42
Profit   224,683,587.58
Payroll runs 18, employer cost 861,586,392.42
```

Command: `python verify_ledgerforge.py checks --data data`

Result: 5/5 checks passed. Journal entries balance with zero difference; payroll to ledger differs by INR 0.00 in every month; receivables match open invoices at INR 139,394,278.00; payroll employee references and exit-date checks pass.

The initial `python -m pytest -q` was run with system Python rather than the project virtual environment. It reported 57 passed and 3 failed because system Python had neither `pypdf` nor `reportlab`; the HR payslip request reached PDF generation and returned 503 for missing `reportlab`. Authentication and authorization remained enabled. `requirements.txt` already declares `pypdf>=4.0` and `reportlab>=4.0`, and both packages were installed in `.venv`.

Follow-up command: `\.venv\Scripts\python.exe -m pip show pypdf reportlab`

Result: `pypdf 6.21.2` and `reportlab 5.1.0` are installed in the project environment.

Follow-up command: `\.venv\Scripts\python.exe -m pytest -q`

Result: **60 passed, 1 warning, 0 failed** in 66.91 seconds. This includes both PDF parsing/rendering tests and the HR payslip authorization test. All 57 tests that passed in the system-Python run also pass in the project virtual environment. The remaining warning is Starlette's deprecation notice about using `httpx` with `TestClient`.

The official default verifier path (`../03_Data/csv`) is absent. Passing `--data data` uses the checked-in supplied dataset and succeeds.

## Phase 3 dependency assessment and execution plan

| Stage | Work | Dependency / current status |
|---|---|---|
| 1 | Repository audit | Complete. Findings and reproducible baseline recorded here. |
| 2 | Vendors and expense bills | Blocked: `data/` has no vendor or expense CSV/source, and the chart of accounts does not establish the intended account mapping for vendor bills. Need vendor/invoice identifiers, bill dates/amounts, vendor identity, and approved expense/AP/cash account mappings to build and reconcile the import. |
| 3 | Payroll runs to ledger | Existing 18 monthly runs and linked payroll ledger evidence are present; official reconciliation is INR 0.00. New approval/reversal lifecycle and regenerated runs depend on the missing approved employee inputs and statutory rules recorded in `docs/phase2_task7_blockers.md`. Do not recalculate or post new runs from sample policy values. |
| 4 / Task 13 | Login, roles and permissions | **Implemented; provisioning pending.** Login, database-backed roles, user administration, and protected routes are implemented. No approved initial Admin/user identity or credential was supplied; `roles.csv` remains a job catalog, not user permissions. See Task 13 details below. |
| 5 / Task 14 | Tax and statutory reports | **Blocked** for compliant calculations: `tax_slabs.csv`, `tax_parameters.csv`, and `statutory_rates.csv` explicitly label their values as samples. Employee declarations/elections and verified effective-dated statutory rules are absent. Do not present results from those samples as statutory reports. |
| 6 | Financial statements | Official source data and headline figures are present. The verifier's five integrity checks pass. This stage can proceed after the blocking earlier stages are resolved under the requested sequential execution strategy. |
| 7 | Dashboard and final integration | Depends on the routes, data, and authorization behavior established in Stages 2–6. The current dashboard uses existing APIs and must not be populated with fabricated records. |

## Inputs needed to resume safely

1. Vendor and bill source files (or approved source schema plus account mappings and duplicate-detection policy).
2. Demo user identities with employee linkage, assigned roles, and an approved credential provisioning/reset method.
3. Authoritative effective-dated tax/statutory rules and employee-level elections/declarations and related payroll inputs. The outstanding detail is enumerated in `docs/phase2_task7_blockers.md`.
4. Run tests through `.venv` (or install `requirements.txt` into whichever Python environment is used) so PDF dependencies are available. No JWT configuration or authorization change was needed for the baseline fix.

No Phase 3 task is marked complete by this audit. No external source was fabricated and historical rows were not modified.

## Task 15 — Financial statements (implemented)

### Files changed

- Added `app/financial_reports.py` for Decimal-based, read-only report calculations from posted journal lines.
- Added `app/routers/reports.py` and registered it in `app/main.py`.
- Added `tests/test_financial_reports.py`.
- Added a Financial reports section to `app/static/index.html` and `app/static/dashboard_sections.js`.
- No migration was needed. No payroll calculations, accounting source CSVs, or existing financial records were changed.

### APIs

All report endpoints require the existing HR/Admin authorization dependency:

- `GET /reports/trial-balance?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
- `GET /reports/trial-balance.csv?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
- `GET /reports/profit-and-loss?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
- `GET /reports/balance-sheet?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`

When dates are omitted, reports use the current financial year through today. Trial Balance returns opening balances, period movements, closing balances, group rollups, and debit/credit totals. Group rows are rollups of descendants; statement totals count posting accounts once. The CSV includes the verifier-compatible `account_code,debit,credit` columns along with the opening, movement, and closing columns.

### Available dataset comparison

The plain command `python verify_ledgerforge.py summary` still cannot run because its default `../03_Data/csv` directory is absent. The checked-in snapshot was used with `--data data`:

```text
Revenue  1,260,930,052.00
Expenses 1,036,246,464.42
Profit   224,683,587.58
Payroll runs 18, employer cost 861,586,392.42
```

Against the loaded LedgerForge database for 2025-04-01 through 2026-09-30:

- Trial Balance closing debits and credits: INR 1,518,309,423.07 each; balanced.
- Trial Balance CSV command `python verify_ledgerforge.py trial-balance outputs/phase3_trial_balance.csv --data data`: 42 accounts compared, 0 mismatches.
- Profit and Loss: revenue INR 1,260,930,052.00; expenses INR 1,036,246,464.42; net profit INR 224,683,587.58. These match the verifier summary against the available dataset exactly.
- Balance Sheet: assets INR 463,762,958.65; liabilities INR 77,499,607.07; recorded equity INR 161,579,764.00; prior period earnings INR 0.00; current period profit INR 224,683,587.58; difference INR 0.00; balanced.

These figures are verified against the checked-in/loaded snapshot only. The verifier's trial-balance command compares cumulative debit and credit posting movements per account, not net closing balance columns; the separate API closing debit and credit totals also balance.

### Tests and dashboard

Command: `\.venv\Scripts\python.exe -m pytest -q`

Result at Task 15 implementation: **65 passed, 1 warning, 0 failed**. Following Tasks 11 and 12, the current full suite is **71 passed, 1 warning, 0 failed**; see the current run below. The original 60-test clean baseline remains passing.

The application started successfully with Uvicorn at `http://127.0.0.1:8123/`. Report screens are wired to authenticated APIs and include date controls, INR formatting, loading/empty/error states, and trial-balance CSV download. Screenshots were not captured: the in-app browser control call failed before opening a tab because its runtime rejected the request with `missing field sandboxPolicy`. The dashboard endpoints and data were verified through the automated API tests and direct report calculations.

### Task 15 acceptance status

- [x] Date-filtered Trial Balance, P&L, and Balance Sheet APIs.
- [x] Group account rollups without double-counting in totals.
- [x] Trial Balance closing debits equal closing credits.
- [x] P&L totals match the available verifier summary.
- [x] Balance Sheet equation balances to INR 0.00.
- [x] CSV export and authenticated dashboard section.
- [x] Automated tests pass with the full suite.
- [ ] Screenshots: blocked by the browser runtime error documented above.
- [ ] Comparison to an external official reference dataset: unavailable; only checked-in snapshot results are claimed.

Task 15 report calculations meet the available-data acceptance checks. Screenshot evidence and comparison to any separate official reference files remain unavailable.

## Tasks 11 and 12 — Vendor expenses and payroll lifecycle (implemented)

The supplied vendor and expense snapshots subsequently became available in `data/`; this supersedes the earlier dependency table's statement that vendor/expense source files were absent. Detailed implementation, reconciliation, tests, and limitations are recorded in [phase3_task11_12.md](phase3_task11_12.md).

Current verification:

- `python verify_ledgerforge.py summary --data data`: Revenue INR 1,260,930,052.00; Expenses INR 1,036,246,464.42; Profit INR 224,683,587.58; 18 payroll runs; employer cost INR 861,586,392.42.
- `python verify_ledgerforge.py checks --data data`: **5/5 passed**.
- Phase 3 input validator: **0 errors**, 14 historic separation-of-duties warnings.
- Current full test suite: **71 passed, 1 warning, 0 failed in 87.94 seconds**. The warning remains Starlette's `httpx` TestClient deprecation notice.

Tasks 11 and 12 were implemented without changing source CSVs, payroll calculations, historical journal entries, or existing financial amounts. Existing expense and salary-payment entries were linked to their new application records; migrations and loaders are idempotent. The 14 legacy self-approval records remain preserved and flagged; new approval requests enforce separation of duties.

## Current Phase 3 task statuses

- Task 11 — Vendor expenses: implemented; see [phase3_task11_12.md](phase3_task11_12.md) for validation, reconciliation, and historical data limitations.
- Task 12 — Payroll-to-ledger: implemented and reconciled against the available snapshot; see [phase3_task11_12.md](phase3_task11_12.md).
- Task 13 — Login, roles and permissions: **Implemented; initial operator provisioning and production secret configuration remain pending**.
- Task 14 — Tax and statutory reports: **Blocked** pending authoritative rules, employee declarations/elections, and payroll inputs documented above and in `docs/phase2_task7_blockers.md`.
- Task 15 — Financial statements: report calculations and available-data reconciliation pass; screenshot and external official-reference evidence remain unavailable as documented in the Task 15 section.

## Task 13 — Authentication, roles and permissions

### Architecture

- Added the `users` table and migration `k6d9e31a4b72`. Accounts contain an opaque user ID, optional employee link for Admin/HR, required employee link for Employee, normalized email username, scrypt password hash, role (`Admin`, `HR`, `Employee`), active flag, and creation timestamp. No password or hash appears in user API responses.
- `POST /auth/login` checks the username/password and active state, then issues an HS256 JWT with issuer, audience, subject, `iat`, and `exp`. Access tokens expire after 30 minutes. The role is read from the active database user on each request; client-supplied role claims cannot elevate access. Previously configured trusted JWTs with an employee ID as `sub` remain usable when that employee maps to an active user account.
- JWT signing requires `LEDGERFORGE_JWT_SECRET` (or compatible `JWT_SECRET` / `SECRET_KEY`) with at least 32 bytes. The built-in development placeholder and sample placeholder are rejected. Deactivation is checked on every protected request, which immediately invalidates that account's existing tokens.
- Added `GET /auth/me`, Admin-only user list/detail/create/update/password-reset APIs under `/users`, and the operator-run `scripts/create_initial_admin.py` for first-account provisioning. The bootstrap script takes a real existing employee ID and email from the operator and prompts for a password; it has no built-in identities or credentials.
- Dashboard login calls the real API. Its 30-minute bearer token is kept in tab-scoped `sessionStorage`; `/auth/me` controls role-based navigation, and sign-out clears the token. API dependencies enforce permissions independently of the UI.

### Role-permission matrix

| Capability | Admin | HR | Employee |
|---|---:|---:|---:|
| Manage user accounts and reset passwords | Yes | No | No |
| Read employee directory; create/update employee records | Yes | Yes | Own record only |
| Mark an employee departed | Yes | Yes | No |
| View all attendance, leave, salary and payslip records | Yes | Yes | Own records only |
| Submit leave for own linked employee account | Yes, when linked | Yes, when linked | Yes |
| Approve/reject leave | Yes | Yes | No |
| Create/process payroll runs and read run reports | Yes | Yes | No |
| Approve, pay, or reverse payroll | Yes | No | No |
| Vendor/expense management, approval and reporting | Yes | Yes | No |
| Pay an expense bill | Yes | No | No |
| Read accounting ledger and financial statements | Yes | Yes | No |
| Create/reverse journal entries; post payroll to ledger | Yes | No | No |
| Client/invoice workflows | Yes | Yes, except financial payments/cancellation | No |
| Record invoice payments or cancel invoices | Yes | No | No |

Expense approval still enforces creator/approver separation of duties. Static reference reads for `/departments` and `/roles`, `/health`, the login endpoint, dashboard shell, and static assets are intentionally public; they expose no employee, payroll, or financial records. All other business API endpoints are protected by the required current-user or role dependency, with employee ownership checks on employee-scoped endpoints.

### Protected API route families

- `/auth/me`; all `/users` list/detail/create/update/reset operations (Admin only).
- `/employees`, `/employees/stats`, employee detail/team, and employee mutations (HR/Admin for directory and edits; self-only detail for Employee; departure is Admin-only).
- `/employees/{employee_id}/salary` (self or HR/Admin); salary revisions/history (HR/Admin).
- `/attendance` and `/attendance/summary/{employee_id}` (Employee requests are scoped to their linked employee ID; HR/Admin may query across employees).
- `/leave/*` (authenticated; balances and requests are self-scoped for Employee; HR/Admin can review and decide requests).
- `/payroll/*` (Employee can access only own calculation/items; run management HR/Admin; approval, payment, and reversal Admin-only).
- `/payslips/*` (self or HR/Admin).
- `/vendors`, `/expenses*` (HR/Admin; payments Admin-only).
- `/ledger/*` (reads HR/Admin; journal mutations, reversal, payroll posting Admin-only).
- `/clients`, `/invoices`, `/receivables` (HR/Admin; payment/cancellation Admin-only).
- `/reports/*` (HR/Admin).

### Security verification

Added `tests/test_auth_rbac.py` covering login/password hashing, database-backed roles, missing/invalid/expired tokens, inactive login, account deactivation invalidating an existing token, six protected routes, employee cross-record/payslip denial, payroll write denial, HR denial of Admin actions, and Admin user management. Test identities are clearly synthetic, isolated to disposable test databases, and are not loaded into `data/` or the application database.

Current full test command: `.venv\\Scripts\\python.exe -m pytest -q`.

Result: **79 passed, 1 warning, 0 failed in 71.54 seconds**. This is eight new Task 13 authentication/RBAC tests above the 71-test baseline. Python compile checks and JavaScript `node --check` checks pass. The existing Starlette/httpx TestClient deprecation warning remains.

### Missing inputs and limitations

- No approved demo-user identity/role mapping or initial Admin credential was supplied. No application accounts were created or seeded. The current workspace also has no configured signing secret. Consequently a fresh deployment cannot accept a real dashboard login until an operator configures a strong `LEDGERFORGE_JWT_SECRET`, runs migrations, and provisions the first Admin with the interactive bootstrap script using an existing employee identity.
- No rate limiter, email verification, token refresh flow, or self-service password reset is included. Admin password reset is supported; tokens last 30 minutes and inactive accounts are revoked immediately.
- HR/Admin users may be unlinked to an employee, in which case audit fields use the opaque user ID. Employee accounts must be linked to an existing employee record.
- Department and role reference endpoints remain publicly readable; they contain organization reference data and no employee financial data.

## Task 14 follow-up — Configurable tax and statutory rules

The effective-dated configuration models, Admin-only management APIs, payroll configuration selection, and monthly PF/ESI/TDS report are implemented. See [phase3_task14.md](phase3_task14.md). Tests cover role restrictions, slab boundary validation, effective-date calculation changes, preserving earlier calculation results, and reconciliation of statutory report totals to payroll runs.

The statutory-compliance acceptance remains pending: all supplied tax/statutory files identify sample values, and no authoritative effective-dated rules or employee regime elections/declarations are available. The existing sample rules remain visibly labeled and calculations return warnings. No production compliance claim is made.
