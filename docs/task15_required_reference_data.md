# Task 15 ? Required independent official reference data

The verifier's default source directory `../03_Data/csv` is absent. The checked-in `data/` directory is the application/training snapshot and is not an independent reference. Do not create substitute data. Request the original official Phase 3 reference bundle from the specification/data owner or instructor.

## Files expected by the official verifier

For `verify_ledgerforge.py checks` and `summary`, supply these independent CSV files in one directory using the exact file names:

- `chart_of_accounts.csv`: at minimum `account_code`, `account_type` (the official checker also consumes account metadata for report classification).
- `journal_entries.csv`: at minimum `entry_id`, `source_type`, `source_id`.
- `journal_lines.csv`: at minimum `entry_id`, `account_code`, `debit`, `credit`.
- `payroll_runs.csv`: at minimum `run_id`, `total_employer_cost`.
- `payroll_items.csv`: at minimum `run_id`, `employee_id`, `gross_pay`, `total_deductions`, `net_pay`, `period_start`.
- `invoices.csv`: at minimum `status`, `balance_due`.
- `employees.csv`: at minimum `employee_id`, `exit_date`.

Use the same authoritative release and date scope for all files. The audited application coverage is 2025-04-01 through 2026-09-30. Include the full reference period, stable IDs/keys, and numeric monetary columns without formatted currency symbols. Include opening balances or prior-period lines if the official trial balance is cumulative.

## Comparison procedure

1. Preserve the delivered source files unchanged and record provider, release/date, and checksums. Confirm they were not exported from this LedgerForge database or generated report output.
2. Run `.venv\Scripts\python.exe verify_ledgerforge.py summary` and `checks` with the reference directory configured as the official input. Record revenue, expenses, profit, payroll run count, and employer cost.
3. Export Trial Balance CSV from the application for the identical cutoff and run `verify_ledgerforge.py trial-balance <application-export.csv> --data <official-reference-directory>`. It compares account-level debit/credit totals from official journal lines; acceptance tolerance is one paisa. Record account count and mismatches.
4. Compare P&L by official account classification and period; compare Balance Sheet assets, liabilities, equity, and current-period profit at the same cutoff. Record `Assets - (Liabilities + Equity + Current Profit)` and explain any non-zero difference from source records.
5. Keep checked-in snapshot results and independent-reference results in separate evidence files.

**Current status:** The official reference bundle is not present, so independent-reference comparison cannot be claimed. The checked-in snapshot comparison is reported separately in `phase3_task15.md`.
