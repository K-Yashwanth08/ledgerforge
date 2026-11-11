# Phase 3 Task 15 — Financial Reports

## Implemented and verified

The project contains authenticated APIs and dashboard components for Trial Balance, Profit and Loss, and Balance Sheet. The Trial Balance CSV export omits group rows and is accepted by `verify_ledgerforge.py` when pointed at the checked-in snapshot. Automated tests cover report calculations, date filtering, group rollups, account totals, balance sheet equation, CSV export, and authorization.

Read-only calculations for 2025-04-01 through 2026-09-30:

| Report | Result |
|---|---:|
| Trial Balance closing debit | INR 1,518,309,423.07 |
| Trial Balance closing credit | INR 1,518,309,423.07 |
| P&L revenue | INR 1,260,930,052.00 |
| P&L expenses | INR 1,036,246,464.42 |
| P&L net profit | INR 224,683,587.58 |
| Balance Sheet assets | INR 463,762,958.65 |
| Balance Sheet liabilities | INR 77,499,607.07 |
| Balance Sheet equity (recorded) | INR 161,579,764.00 |
| Current-period profit | INR 224,683,587.58 |
| Assets equation difference | INR 0.00 |

The trial-balance checker compared 42 accounts and reported 0 mismatches against the checked-in `data/` snapshot.

Evidence files generated from persisted records are in `outputs/phase3_evidence/`:

- `task15_financial_report_summary.json`
- `migration_integrity.json`
- `task14_statutory_reconciliation.csv`

## Independent reference and screenshot status

The verifier’s default `../03_Data/csv` directory is absent. The checked-in `data/` files are not an independent official reference. Running `verify_ledgerforge.py summary` and its default Trial Balance comparison therefore fails with missing-file errors; passing `--data data` verifies only the available project snapshot.

No screenshots are included. The live users table has one active standalone Admin whose username matches the operator-provided email. Login has not been verified. After the operator signs in successfully, use these manual steps:

1. Start the app from the project root with `\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`.
2. Open `http://127.0.0.1:8000`, sign in with the existing standalone Admin, and open **Accounting → Financial reports**.
3. Select each report, set the period to 2025-04-01 through 2026-09-30, and load it. Capture genuine screenshots of Trial Balance, Profit and Loss, and Balance Sheet into `outputs/phase3_evidence/` using the requested filenames.
4. Capture the Trial Balance CSV download separately if the acceptance reviewer needs export evidence.

**Status:** Report implementation and reconciliation to the checked-in snapshot pass. Authenticated screenshot evidence and independent official-reference comparison remain pending.
