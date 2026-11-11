# LedgerForge Phase 3 Final Acceptance Audit (Tasks 11â€“15)

**Audit date:** 2026-11-03 (Asia/Kolkata)  
**Scope:** Final acceptance verification following implementation and migration work. The live database progressed additively from `k6d9e31a4b72` through `l7e4a2c9d610` to `m8f41c2b7e90`; no historical payroll or ledger rows were rewritten. The duplicate-index migration was made idempotent.

## Specification and audit limits

No standalone Phase 3 specification file was found in the repository. This audit uses the supplied â€œDays 11 to 15. Spending, payroll-to-books, security, tax rules and financial reportsâ€ text and the later continuation of the final-remediation request. The first pasted remediation segment ended during Task 13; its continuation supplied additional Task 14/15 verification criteria. Requirements beyond those supplied texts were not assessed.

## Executive result

| Task | Implementation finding | Acceptance finding |
|---|---|---|
| 11 â€” Vendor bills / expenses | Implemented and tested; 30 vendors and 501 bills loaded and linked. | Meets supplied software checks. Source history has 14 flagged self-approvals; 23 bills are approved but unpaid. |
| 12 â€” Payroll-to-ledger | Implemented and tested; 18 runs and all 18 payroll journals are linked. | Reconciles to persisted ledger at INR 0.00 in every month. Reversal/idempotency tests pass. |
| 13 ? Authentication / roles | Login, roles, and standalone Admin bootstrap implemented; isolated security tests pass. | One active standalone Admin exists, but live login/account control remain unverified. |
| 14 â€” Configurable tax / statutory | Models, management APIs, calculation selection, report, and tests exist. | Election/declaration APIs, audit trail, effective-date regime selection, sample-policy blocking, and configuration preview are implemented. Live schema is at `m8f41c2b7e90`; central official sources are documented as candidates, while employer approval/applicability, employee inputs, and statutory transition handling remain open, so statutory acceptance is blocked. |
| 15 â€” Financial reports | Report APIs, dashboard section, CSV export, and tests exist. | Calculations match the checked-in dataset and balance. Screenshot evidence and a separate official reference dataset are absent. |

**Strict conclusion:** Tasks 11 and 12 meet the available software and reconciliation checks. Tasks 13â€“15 remain incomplete for the specific environment, authoritative-input, or evidence reasons below. Phase 3 as a whole is **not fully accepted**.

## Commands and evidence

| Verification | Result |
|---|---|
| `.venv\Scripts\python.exe -m pytest -q` | **92 passed, 1 warning, 0 failed** (74.04 s). Warning: Starlette deprecation notice for `httpx` in `TestClient`. |
| `.venv\Scripts\python.exe -m scripts.validate_phase3_inputs --data data` | **0 errors**; 14 historic separation-of-duties warnings; no exact or likely duplicate bill candidates. |
| `.venv\Scripts\python.exe verify_ledgerforge.py checks --data data` | **5/5 passed**. Check 2 (â€œPayroll equals ledger, every monthâ€) largest difference **INR 0.00**. |
| `.venv\Scripts\python.exe verify_ledgerforge.py summary --data data` | Revenue INR 1,260,930,052.00; expenses INR 1,036,246,464.42; profit INR 224,683,587.58; payroll employer cost INR 861,586,392.42 across 18 runs. |
| `.venv\Scripts\python.exe verify_ledgerforge.py trial-balance outputs\phase3_trial_balance.csv --data data` | 42 accounts compared; **0 mismatches**. |
| `alembic heads` / `alembic current` | Head and live database both `m8f41c2b7e90`. |
| Fresh SQLite migration rehearsal | Entire chain from empty database through `m8f41c2b7e90` completed successfully after making the duplicate-index migration safe; `h3b52e9d6f81` upgrade/downgrade rehearsal preserves the base unique index; Task 14 downgrade refuses destructive config loss. |
| Live Task 14 migration | Applied `m8f41c2b7e90` after a persistent verified SQLite backup; all pre-existing table hashes and historical payroll/ledger totals match. |
| `git diff --check` | Exit 0; only Git line-ending normalization warnings for existing CRLF/LF files. |
| `.venv\Scripts\python.exe -m compileall -q app scripts alembic` | Passed. |

The validator and verifier operate on the checked-in CSV snapshot. Separate read-only SQL queries against `ledgerforge.db` confirmed 18 runs, 7,340 payroll items, 18 posted linked payroll journals, and zero run-to-ledger difference by month. The live ledger totals were independently compared to the statements: trial balance closing debits and credits INR 1,518,309,423.07 each; P&L revenue INR 1,260,930,052.00, expenses INR 1,036,246,464.42, profit INR 224,683,587.58; balance sheet difference INR 0.00.

## Task 11 â€” Vendor Bills / Expenses

### Data and reconciliation

- Live database: **30 vendors, 501 bills, 478 payment records**. There are 478 paid bills and 23 approved/outstanding bills.
- Source CSV monthly expense totals and the linked expense journals match in **18/18 months**. Total taxable expense INR **168,245,930.00**, GST INR **29,230,907.90**, and gross bills INR **197,476,837.90**.
- Duplicate scan: **0 exact and 0 likely candidates** in the supplied source snapshot. Duplicate detection is additionally exercised by tests for exact matches (rejected) and likely matches (warned).
- Source-integrity validation reports **14 historical creator/approver matches**. The original records are retained and flagged; the new approval route rejects self-approval. Historical approval timestamps were not present in the CSV.
- The 23 source bills marked unpaid already have bill journals. They are represented as approved/outstanding and have no payment journal; payment does not re-expense them.

### Workflow and tests

The expense tests exercise submitted â†’ approved â†’ paid, payment-before-approval rejection, creator self-approval rejection, balanced bill and payment postings, exact/likely duplicate detection, idempotent payment replay, protected endpoints, and monthly/vendor report behavior. Bill posting debits expense and input GST and credits AP; payment debits AP and credits cash/bank. Payment replay returns the existing journal and does not duplicate expense debit.

**Finding:** The Task 11 workflow and data checks pass. Outstanding source-history exceptions are disclosed and are not evidence that the new workflow allows self-approval.

## Task 12 â€” Payroll-to-Ledger

### Persisted records and reconciliation

- **18 payroll runs**, **7,340 employee payroll items**, and **18/18 linked posted payroll journal entries** are present in the live database.
- Run status: 17 `PAID`; one `POSTED - PAYMENT PENDING`. The pending run has a payroll expense journal but no salary payment.
- Actual database totals: gross INR **849,626,960.27**; deductions INR **98,608,653.58**; net INR **751,018,306.69**; employer contributions INR **11,959,432.15**; employer cost INR **861,586,392.42**.
- Actual ledger payroll expense debit total: INR **861,586,392.42**. Run-to-ledger difference: **INR 0.00** overall and for each of the 18 months (April 2025â€“September 2026).
- Check 2 output: `PASS Payroll equals ledger, every month â€” largest monthly difference=0.00`.

### Lifecycle, idempotency, reversal

Tests cover draft creation and replay, processing through the existing payroll calculator, approval and ledger link, payment replay, and reversal journals. The historical data loader links existing runs and journals instead of recalculating source values. Test evidence supports one run per period and payment replay behavior. The available source snapshot contains one unpaid/pending run; it is not counted as a missing payroll expense posting.

**Finding:** Task 12 satisfies the supplied integration/reconciliation checks. Historical payroll is source snapshot data; this audit did not rerun payroll or alter ledger records.

## Task 13 â€” Authentication / Roles

### Authentication evidence

- User model/table and migration exist. Password storage uses salted `scrypt`; tests verify the stored value differs from the plaintext password.
- Login issues HS256 tokens with a 1,800-second lifetime. Authentication validates signature, issuer, audience, issue/expiry times, active database identity, and database-backed role.
- Tests cover login, invalid/missing/expired tokens, inactive login, immediate access revocation after deactivation, role denial, employee cross-record denial, HR denial of Admin actions, and Admin user management.
- **Live-state blocker:** the live `users` table now has **1 active standalone Admin** (`employee_id = NULL`), with no HR or Employee accounts. Its username matches the operator-provided email and does not match the demo email entered in the latest failed bootstrap retry. That retry did not create the account. Login and account ownership verification remain pending; password hashes were not read.
- The user model and existing migration already permit `employee_id = NULL`. The one-time local bootstrap creates a standalone Admin without an employee link, using a transaction lock to serialize concurrent attempts. The live DB now has one active standalone Admin; the latest retry was rejected as duplicate and did not create a second account. Admins without employee association are denied employee-specific payroll/payslip endpoints.

### Route-by-route security inventory

Role notation: **Public** means no bearer token; **Auth** means any active role; **HR/Admin** and **Admin** are the named roles. Employee ownership checks apply only to Employee accounts; HR/Admin may access organization-wide records where indicated. â€œDirect testâ€ identifies route-specific or representative family tests; it does not imply every path has an individual test.

| Method and path | Authentication / allowed roles | Ownership restriction | Test evidence / result |
|---|---|---|---|
| GET `/health` | Public | None | No direct security test located; public health response only. |
| GET `/` | Public | None | `test_auth_rbac` checks login page; pass. |
| GET `/departments` | Public | None | Public reference data; no route-specific auth test. |
| GET `/departments/{department_id}` | Public | None | Public reference data; no route-specific auth test. |
| GET `/roles` | Public | None | Public reference data; no route-specific auth test. |
| POST `/auth/login` | Public | Credentials required | `test_auth_rbac` login, invalid/inactive login; pass. |
| GET `/auth/me` | Auth | Current account only | Missing/invalid/expired/deactivated token tests; pass. |
| GET `/attendance` | Auth | Employee sees own records; HR/Admin can query across employees | Representative protected-route and own attendance tests; pass. |
| GET `/attendance/summary/{employee_id}` | Auth | Employee self-only | Attendance/leave test family; exact route coverage not confirmed in the route-security test. |
| GET `/employees` | HR/Admin | Organization-wide | `test_auth_rbac` tests missing/wrong role; pass. |
| GET `/employees/stats` | HR/Admin | Organization-wide | Protected by `hr_actor`; no direct route-specific test located. |
| GET `/employees/{employee_id}` | Auth | Employee self-only | Cross-employee denial and own-record test; pass. |
| POST `/employees` | HR/Admin | Organization-wide | `test_auth_rbac` representative protected route; pass. |
| PATCH `/employees/{employee_id}` | HR/Admin | Organization-wide | Protected by `hr_actor`; no direct mutation authorization test located. |
| DELETE `/employees/{employee_id}` | Admin | Organization-wide | Protected by `admin_actor`; HR denial covered for other Admin actions, not this path specifically. |
| GET `/employees/{employee_id}/team` | HR/Admin | Organization-wide | Protected by `hr_actor`; no direct route test located. |
| GET `/employees/{employee_id}/salary` | Auth | Employee self-only | Salary tests cover records; no direct cross-employee salary authorization test located. |
| GET `/employees/{employee_id}/salary/revisions` | HR/Admin | Organization-wide | Salary test family; route authorization coverage not confirmed. |
| POST `/employees/{employee_id}/salary/revisions` | HR/Admin | Organization-wide | Salary test family; route authorization coverage not confirmed. |
| GET `/vendors` | HR/Admin | Organization-wide | `test_expenses` protected-route test; pass. |
| POST `/vendors` | HR/Admin | Organization-wide | Expense test family; no direct role matrix for this path. |
| GET `/vendors/{vendor_id}` | HR/Admin | Organization-wide | Expense test family; no direct role matrix for this path. |
| PATCH `/vendors/{vendor_id}` | HR/Admin | Organization-wide | Expense test family; no direct role matrix for this path. |
| POST `/expenses/duplicate-check` | HR/Admin | Organization-wide | Duplicate test; pass. |
| GET `/expenses/reports/monthly` | HR/Admin | Organization-wide | Expense report test; pass. |
| GET `/expenses/reports/vendor-wise` | HR/Admin | Organization-wide | Expense report test; pass. |
| GET `/expenses/reports/outstanding` | HR/Admin | Organization-wide | Expense report test; pass. |
| GET `/expenses/reports/paid-unpaid` | HR/Admin | Organization-wide | Expense report test; pass. |
| GET `/expenses` | HR/Admin | Organization-wide | Expense test family; authorization is on route. |
| POST `/expenses` | HR/Admin | Submitter recorded; cannot approve own bill | Creation/self-approval tests; pass. |
| GET `/expenses/{expense_id}` | HR/Admin | Organization-wide | Expense test family. |
| POST `/expenses/{expense_id}/approve` | HR/Admin | Creator and approver must differ | Self-approval and valid approval tests; pass. |
| POST `/expenses/{expense_id}/payments` | Admin | Organization-wide | Payment-before-approval, balanced entry and replay tests; pass. |
| GET `/clients` | HR/Admin | Organization-wide | Ledger/invoice test family; no dedicated role test located. |
| POST `/clients` | HR/Admin | Organization-wide | Ledger/invoice test family; no dedicated role test located. |
| GET `/clients/{client_id}` | HR/Admin | Organization-wide | Ledger/invoice test family; no dedicated role test located. |
| PATCH `/clients/{client_id}` | HR/Admin | Organization-wide | Ledger/invoice test family; no dedicated role test located. |
| GET `/invoices` | HR/Admin | Organization-wide | Ledger/invoice test family; no dedicated role test located. |
| POST `/invoices` | HR/Admin | Organization-wide | Invoice workflow tests; no dedicated role test located. |
| GET `/invoices/{invoice_id}` | HR/Admin | Organization-wide | Invoice workflow tests; no dedicated role test located. |
| PATCH `/invoices/{invoice_id}` | HR/Admin | Organization-wide | Invoice workflow tests; no dedicated role test located. |
| POST `/invoices/{invoice_id}/send` | HR/Admin | Organization-wide | Invoice workflow tests; no dedicated role test located. |
| POST `/invoices/{invoice_id}/payments` | Admin | Organization-wide | Invoice payment tests; role denial not directly confirmed. |
| POST `/invoices/{invoice_id}/cancel` | Admin | Organization-wide | Invoice cancellation tests; role denial not directly confirmed. |
| GET `/receivables` | HR/Admin | Organization-wide | Receivables test family; no dedicated role test located. |
| GET `/ledger/accounts` | HR/Admin | Organization-wide | Representative protected-route test; pass. |
| GET `/ledger/accounts/{account_code}/balance` | HR/Admin | Organization-wide | Protected by `hr_actor`; no path-specific role test located. |
| GET `/ledger/journal-entries` | HR/Admin | Organization-wide | Protected by `hr_actor`; no path-specific role test located. |
| GET `/ledger/journal-entries/{entry_id}` | HR/Admin | Organization-wide | Protected by `hr_actor`; no path-specific role test located. |
| POST `/ledger/journal-entries` | Admin | Organization-wide | Admin dependency; no direct role test for this path. |
| POST `/ledger/journal-entries/{entry_id}/reverse` | Admin | Organization-wide | Ledger reversal tests; role denial not directly confirmed. |
| POST `/ledger/payroll-runs/{run_id}/post` | Admin | Organization-wide | Payroll lifecycle tests cover approval posting; legacy route role test not individually confirmed. |
| GET `/leave/holidays` | Auth | Shared calendar data | Leave test family; no direct auth matrix for this route. |
| GET `/leave/types` | Auth | Shared reference data | Leave test family; no direct auth matrix for this route. |
| GET `/leave/balances/{employee_id}` | Auth | Employee self-only | Leave test family; cross-employee route test not confirmed. |
| GET `/leave/requests` | Auth | Employee forced to own employee ID; HR/Admin can filter broadly | Leave test family; route-specific authorization test not confirmed. |
| POST `/leave/requests` | Auth | Employee request uses linked employee ID | Leave test family; route-specific authorization test not confirmed. |
| POST `/leave/requests/{request_id}/approve` | HR/Admin | Organization-wide | Leave test family; role test not confirmed. |
| POST `/leave/requests/{request_id}/reject` | HR/Admin | Organization-wide | Leave test family; role test not confirmed. |
| GET `/payroll/calculate/{employee_id}` | Auth | Employee self-only; standalone Admin without employee link denied; linked Admin/HR allowed | Employee cross-record and standalone Admin tests; pass. |
| POST `/payroll/runs` | HR/Admin | Organization-wide | Payroll lifecycle tests cover Admin/HR operations. |
| POST `/payroll/runs/draft` | HR/Admin | Organization-wide | Draft/idempotency test; pass. |
| POST `/payroll/runs/{run_id}/process` | HR/Admin | Organization-wide | Employee write denial and lifecycle test; pass. |
| POST `/payroll/runs/{run_id}/approve` | Admin | Organization-wide | HR denial and approval lifecycle tests; pass. |
| POST `/payroll/runs/{run_id}/payments` | Admin | Organization-wide | HR denial and replay tests; pass. |
| POST `/payroll/runs/{run_id}/reverse` | Admin | Organization-wide | Reversal test; role denial not directly confirmed. |
| GET `/payroll/runs` | HR/Admin | Organization-wide | Representative protected-route tests; pass. |
| GET `/payroll/runs/{run_id}` | HR/Admin | Organization-wide | Protected by `hr_actor`; no route-specific test located. |
| GET `/payroll/runs/{run_id}/items` | Auth | Employee restricted to own employee ID; standalone Admin without employee link is denied; linked Admin/HR can query all | Cross-record and standalone Admin tests; pass. |
| GET `/payslips/employee/{employee_id}/runs` | Auth | Employee self-only; standalone Admin without employee link denied; linked Admin/HR allowed | Cross-employee and standalone Admin denial; pass. |
| GET `/payslips/{employee_id}/{run_id}/data` | Auth | Employee self-only; standalone Admin without employee link denied; linked Admin/HR allowed | Cross-record and standalone Admin denial; pass. |
| GET `/payslips/{employee_id}/{run_id}` | Auth | Employee self-only; standalone Admin without employee link denied; linked Admin/HR allowed | Payslip access and standalone Admin denial; pass. |
| GET `/reports/statutory/monthly` | HR/Admin | Organization-wide | Payroll test verifies report reconciliation; missing-token test not specific to this route. |
| GET `/reports/trial-balance` | HR/Admin | Organization-wide | Report authorization and calculation tests; pass. |
| GET `/reports/trial-balance.csv` | HR/Admin | Organization-wide | CSV export test; report auth not separately tested for export path. |
| GET `/reports/profit-and-loss` | HR/Admin | Organization-wide | Report authorization and calculation tests; pass. |
| GET `/reports/balance-sheet` | HR/Admin | Organization-wide | Representative route auth and balance test; pass. |
| GET `/tax/configuration` | HR/Admin | Organization-wide policy configuration | Task 14 test confirms HR read; live migration now applied. |
| POST `/tax/configuration/slabs` | Admin | Organization-wide policy change | HR denial, slab boundary and effective-date tests; pass on test schema. |
| POST `/tax/configuration/parameters` | Admin | Organization-wide policy change | Effective-date test; HR denial not individually tested. |
| POST `/tax/configuration/statutory-rates` | Admin | Organization-wide policy change | Admin dependency present; no direct route test located. |
| GET `/users` | Admin | User directory | HR/Employee denial and Admin management tests; pass. |
| GET `/users/{user_id}` | Admin | User directory | Admin dependency; no direct route-specific denial test located. |
| POST `/users` | Admin | User provisioning | Admin creation test; pass. |
| PATCH `/users/{user_id}` | Admin | User provisioning/deactivation | Admin update and deactivation revocation tests; pass. |
| POST `/users/{user_id}/password` | Admin | User password reset | Admin dependency; direct reset test not located. |

The table is based on route decorators and endpoint ownership checks, plus the listed tests. It does not assert that every route has its own security test. Public routes are limited to health, the dashboard/static assets, login, and organization reference data (`/departments`, `/roles`).

## Task 14 ? Configurable Tax / Statutory

- Tax configuration remains in the existing effective-dated `tax_slabs`, `tax_parameters`, and `statutory_rates` tables. Admin-only configuration routes remain in place. The non-writing `scripts/preview_tax_configuration.py` validates proposed CSV bundles, including provenance/approval columns, Decimal values, slab continuity, effective dates, overlaps, and required parameters/rates. The current `data/` bundle is rejected: 27 sample rows, 28 unapproved rows, and 69 validation errors. Evidence: `outputs/phase3_evidence/task14_import_preview.json`.
- Added employee election, declaration, and audit tables/API endpoints. Employees submit only for their linked employee ID; HR/Admin review; effective periods and duplicate declarations are checked; every submission/review is audit logged. Payroll now requires an approved effective-dated employee tax election and fails on missing/conflicting elections. It no longer defaults silently to NEW.
- Payroll calculation blocks when applicable tax/statutory rows are marked SAMPLE/TRAINING. Missing `rebate_amount` is an incomplete configuration error. The monthly statutory report distinguishes employee deductions from employer contributions and reports persisted-item vs payroll-run totals/differences/match status and sample/unverified policy status.
- Official tax, rebate/cess/deduction, PF, ESI and state-level inputs remain absent. The configuration API does not provide a verified policy-owner approval registry; free-form source notes do not prove official provenance. No official values or employee election/declaration data were invented. See [task14_required_external_inputs.md](task14_required_external_inputs.md).
- Historical source reconciliation matches PF employee/employer, ESI employee/employer, TDS, and employer contribution sums in all 18 months at INR 0.00. These are sample-data matches, not statutory correctness. The new election/declaration/audit tables each currently contain zero rows.
- Migration `m8f41c2b7e90` added only the election/declaration/audit tables. A clean full-chain rehearsal passed. Before the live migration, `backups/ledgerforge_pre_m8_task14.db` passed SQLite `integrity_check` and matched all existing table hashes. After migration, every pre-existing table hash matched: 18 payroll runs, 7,340 payroll items, 2,524 journals, 6,784 lines, employer cost INR 861,586,392.42, and journal difference INR 0.00. The earlier l7 migration's missing pre-backup caveat remains on record.

**Finding:** Software coverage improved; statutory acceptance remains **BLOCKED**. Official central tax and ESI sources, plus the EPF wage-ceiling change effective 2026-09-17, were sourced and documented as candidate inputs. They were not activated. Employer applicability/approval, employee elections/declarations, state professional-tax rules, deduction treatment, and payroll support for the mid-month EPF transition remain outstanding. See [required inputs and official-source findings](task14_required_external_inputs.md).

## Task 15 â€” Financial Reports

- Trial balance, P&L, balance sheet, CSV export, authenticated report APIs, dashboard section, and report tests exist.
- Trial balance verifier: 42 accounts, 0 mismatches. Ledger debit/credit closing totals both INR 1,518,309,423.07.
- P&L matches checked-in data summary exactly: revenue INR 1,260,930,052.00; expenses INR 1,036,246,464.42; profit INR 224,683,587.58.
- Balance sheet: assets INR 463,762,958.65; liabilities INR 77,499,607.07; equity INR 161,579,764.00; current profit INR 224,683,587.58; difference INR 0.00.
- The default separate reference location `../03_Data/csv` is absent; required files and comparison steps are in [task15_required_reference_data.md](task15_required_reference_data.md). The checked-in `data/` snapshot is not a separate official reference dataset. No report screenshots were found in the repository.
- The requested screenshot files `outputs/phase3_evidence/task15_trial_balance.png`, `task15_profit_loss.png`, and `task15_balance_sheet.png` are not present. Without a verified login to the existing Admin, capturing the authenticated dashboard would require bypassing authentication; this was not done.
- The users table supports a nullable employee association already; no migration was needed for standalone Admins. Live revision is `m8f41c2b7e90`.

The exact default commands `verify_ledgerforge.py summary` and `verify_ledgerforge.py trial-balance outputs\phase3_trial_balance.csv` fail because `../03_Data/csv` is missing. Their `--data data` versions pass, but are not an independent official comparison.

**Finding:** Report implementation and checked-in-data reconciliation pass; evidence acceptance remains incomplete because screenshots and comparison to a separate official reference dataset are absent. The JWT secret is now configured, but live authenticated dashboard verification is pending confirmation that the existing Admin account is controlled by the operator.

## Defects and recommended follow-up

1. **Task 13 login verification:** one active standalone Admin already exists; do not rerun bootstrap. Sign in locally with its existing credentials and verify `/auth/me` and role access.
2. **Tax acceptance:** approve applicable official central rules, supply state-specific rules and employee elections/declarations, and address the September 2026 PF transition before production statutory calculations.
3. **Task 15 evidence:** after login to the confirmed Admin account, capture the three authenticated report screens and provide the separate official reference dataset for comparison.

## Final acceptance matrix

| Task | Implementation | Environment | Tests | Official data | Evidence | Final status |
|---|---|---|---|---|---|---|
| 13 | Login, scrypt hashing, 30-minute JWT, database roles, standalone Admin bootstrap and ownership checks implemented. | Valid random secret in ignored `.env`; live users table has one active standalone Admin with no employee link; username matches operator-provided email. Live login remains unverified. | Security checks included in full **92 passed** suite; one existing warning. | Not applicable. | Automated tests and route inventory exist; live login and authenticated dashboard verification remain pending. | **PARTIALLY COMPLETE** |
| 14 | Effective-dated schemas/APIs/calculator/report implemented; migration `m8f41c2b7e90` is live; safe duplicate-index migration fix verified from empty DB; upgrade and downgrade preserve the index invariant. | Current and head revisions match at `m8f41c2b7e90`. A verified persistent backup was used before m8; the earlier l7 migration lacked a persistent pre-backup. | Full suite **92 passed**; migration tests: clean chain and existing-revision clone passed; 18-month record reconciliation is zero difference. | Official central tax/ESI/EPF sources are documented as candidates, not activated. Employer approval/applicability, employee elections/declarations, and state PT rules are missing; checked-in config is sample data. | Generated monthly report reconciliation is present, but it only validates stored sample payroll values. September 2026 EPF transition is not modeled. | **BLOCKED** for statutory acceptance |
| 15 | Reports, endpoints, dashboard section, and CSV export implemented; ledger calculations balance. | Live endpoints are protected; authenticated dashboard verification waits on Admin login confirmation. | Financial report tests included in full **92 passed** suite. | Separate official reference directory missing; checked-in data alone used. | Genuine JSON report summary and Trial Balance CSV check exist; three requested screenshots are missing. | **IMPLEMENTED â€“ EVIDENCE PENDING** |

## Audit disposition

- Task 11: **Pass with disclosed historical data exceptions.**
- Task 12: **Pass** for the supplied 18-month payroll-to-ledger check.
- Task 13: **PARTIALLY COMPLETE**; implementation/tests pass and one active standalone Admin exists, but live login remains unverified.
- Task 14: **BLOCKED** for statutory acceptance; schema/migration work is complete and official central sources are documented, but employer approval, employee elections/declarations, state PT rules, and September 2026 EPF transition handling remain outstanding.
- Task 15: **Implementation pass; evidence acceptance incomplete** due missing screenshots and separate official reference data.
- Phase 3: **Not fully complete / not ready for final acceptance.**
