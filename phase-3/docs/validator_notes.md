# Validator notes

The workspace-root `verify_ledgerforge.py` contains these five `checks` checks:

1. **Every journal entry balances:** compares each entry's debit and credit totals and also checks the overall difference.
2. **Payroll equals ledger, every month:** compares payroll-run employer cost with payroll expense debits in the journal, grouped by source run.
3. **Receivables equal open invoices:** compares the accounts-receivable ledger balance with balances on sent, overdue, or partially paid invoices; draft and cancelled invoices are excluded.
4. **Payroll employees exist:** counts payroll rows whose employee ID is not present in the employee table.
5. **Nobody is paid after leaving:** checks that payroll period start is not later than an employee's exit date.

The checks were inspected but did not complete: the root script expects `../03_Data/csv/journal_entries.csv` and other finance exports, and that data directory is absent. The separately referenced `04_Validation_Vault/verify_ledgerforge.py` is also absent from this workspace. No official validator pass result is claimed.
