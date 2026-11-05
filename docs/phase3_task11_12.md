# Phase 3 Tasks 11 and 12 — Vendor expenses and payroll lifecycle

## Scope and data safeguards

Implemented vendor and expense bill workflows (Task 11) and payroll run lifecycle/payment/reversal support (Task 12). Financial values use `Decimal`. No payroll formula, tax rule, supplied source CSV, or existing financial amount/journal entry was changed. Database changes are limited to the new business records and references needed to associate supplied source rows with their existing posted ledger entries.

## Input validation and reconciliation

Command: `python -m scripts.validate_phase3_inputs --data data`

Result: exit code 0; 0 validation errors; 14 legacy separation-of-duties warnings. The input snapshot contains 30 vendors, 501 expense bills, 18 payroll runs, 2,524 journal entries, and 6,784 journal lines. IDs and idempotency keys are unique; duplicate exact/likely bill candidates are zero. Account/vendor/date/GST/amount relationships and bill/payment journal links validate.

| Snapshot check | Result |
|---|---:|
| Expense records | 501 |
| Paid / unpaid source statuses | 478 / 23 |
| Expense months reconciled to posted ledger | 18 / 18 |
| Expense taxable amount | INR 168,245,930.00 |
| Expense GST input | INR 29,230,907.90 |
| Expense gross amount | INR 197,476,837.90 |
| Payroll months reconciled to ledger employer cost | 18 / 18, all INR 0.00 difference |
| Payroll salary payments present | 17; one source run remains payment-pending |

Expense source totals and linked ledger debits/credits match month by month. The 23 source bills marked `UNPAID` already have an approved bill journal but no payment entry; these are imported as `APPROVED`, preserving the raw source status. This allows payment to be recorded without expensing the bill a second time. The 14 source rows where submitter equals approver are retained as historical warnings and marked as legacy SoD violations; new approvals reject self-approval. Source approval timestamps are not supplied and are left null in imported history.

Task 12 loading associates existing payroll records with their existing salary-payment entries. All 18 payroll runs reconcile to their posted payroll journal by month. The source reversal reference `MJ-0001` resolves through its source ID to the original payroll entry; the source history is retained as supplied.

## Implemented APIs and behavior

All endpoints use the existing `hr_actor` authorization dependency.

Task 11 endpoints include:

- `GET/POST /vendors`, `GET /vendors/{vendor_id}`, `PATCH /vendors/{vendor_id}`
- `GET/POST /expenses`, `GET /expenses/{expense_id}`
- `POST /expenses/duplicate-check`
- `POST /expenses/{expense_id}/approve`
- `POST /expenses/{expense_id}/payments`
- `GET /expenses/reports/monthly`, `/vendor-wise`, `/outstanding`, and `/paid-unpaid`

The service validates expense, payable, GST, and cash/bank account types; prevents duplicate bill postings and repeated payments; posts the bill once and pays approved balances against Accounts Payable. Reports include monthly, vendor, outstanding, and payment-status views.

Task 12 endpoints include:

- `POST /payroll/runs/draft`
- `POST /payroll/runs` and `POST /payroll/runs/{run_id}/process`
- `POST /payroll/runs/{run_id}/approve`
- `POST /payroll/runs/{run_id}/payments`
- `POST /payroll/runs/{run_id}/reverse`

Draft/process and payment operations are idempotent. Posting requires approval. A reversal preserves original journals and creates reversal entries; if a run has been paid, its salary payment is reversed before its payroll expense journal.

## Files added or changed

- Added migrations `i4c63e8a91bd` (vendors/expense bills/history/payments) and `j5a8f2c61d40` (payroll lifecycle fields and payment records).
- Added `app/expense_service.py`, `app/routers/expenses.py`, `scripts/load_phase3_task11.py`, `scripts/load_phase3_task12.py`, `scripts/phase3_input_validation.py`, and `scripts/validate_phase3_inputs.py`.
- Updated `app/models.py`, `app/schemas.py`, `app/payroll_service.py`, `app/routers/payroll.py`, `app/routers/ledger.py`, and `app/main.py`.
- Added `tests/test_expenses.py` and `tests/test_phase3_input_validation.py`; extended `tests/test_payroll.py` for draft/idempotent processing, approval, payment replay, and reversal.
- `data/vendors.csv` and `data/expenses.csv` are supplied inputs and were not edited.

Both loaders were run twice. The first run inserted/link-created the expected business records; the second run inserted zero records. Existing ledger journals were not recreated.

## Verification

Available snapshot verifier command: `python verify_ledgerforge.py summary --data data`

```text
Revenue  1,260,930,052.00
Expenses 1,036,246,464.42
Profit   224,683,587.58
Payroll runs 18, employer cost 861,586,392.42
```

These figures are verified against the available checked-in dataset only. They are not claimed as reconciled to missing official reference data. `python verify_ledgerforge.py checks --data data` reports **5/5 checks passed**: journals balance, payroll matches the ledger each month, receivables match open invoices, employee references exist, and no payroll is after an employee exit date.

Current full test command: `.venv\Scripts\python.exe -m pytest -q`

Result: **71 passed, 1 warning, 0 failed in 87.94 seconds**. This retains the prior 60-test clean baseline and adds Task 15 reports, expense/validator coverage, and payroll lifecycle coverage. The one warning is the existing Starlette deprecation notice about `httpx` with `TestClient`.

## Remaining limitations

- Fourteen historic bills have source submitter and approver identities that are the same. They are preserved and flagged; correcting source history requires an authoritative correction record.
- Historical approval timestamps are absent from the source file.
- The 23 imported unpaid bills have approval evidence/journals but no payment evidence. They remain approved/outstanding until a real payment is recorded.
- The available snapshot is not an external official reference dataset. Reconciliation claims are limited to its own linked journal data.
- Screenshots were not requested for Tasks 11 and 12; no new dashboard screens were added for these workflows.

## Acceptance status

- [x] Vendor and expense source data validates with no structural or financial errors.
- [x] Vendor/bill approval, duplicate detection, payment, and reports use existing authentication.
- [x] New approval enforces separation of duties; historical exceptions are flagged.
- [x] Payroll draft, process, approval, payment, and reversal lifecycle is implemented and idempotent where applicable.
- [x] Existing payroll/expense journals reconcile to the supplied source snapshot.
- [x] Full test suite passes and the available-data verifier passes all checks.
- [ ] Historical SoD and missing approval-time evidence are unresolved source-data limitations.
