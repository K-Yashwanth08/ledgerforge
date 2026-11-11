# Phase 2 Task 9 — General ledger

## Scope

Task 9 adds a chart of accounts, immutable posted journal entries, account balances, and payroll posting. Journal entries are stored with their lines; edits and deletes are intentionally not exposed. Corrections use a new reversing entry linked to the original.

## API

All routes require an HR or admin bearer token. Tokens are validated by the shared authentication layer; the application does not issue tokens.

- `GET /ledger/accounts?active_only=true`
- `GET /ledger/accounts/{account_code}/balance?as_of=YYYY-MM-DD`
- `GET /ledger/journal-entries` with optional date, status, source type, limit, and offset filters
- `GET /ledger/journal-entries/{entry_id}`
- `POST /ledger/journal-entries`
- `POST /ledger/journal-entries/{entry_id}/reverse`
- `POST /ledger/payroll-runs/{run_id}/post`

Entries require at least two lines, active leaf accounts, a positive debit or credit per line, and equal debit and credit totals. Posting records the period and April–March financial year from the entry date. Account balances sum posted lines through the requested date and use the account's normal balance direction.

Payroll posting groups stored payroll item amounts into expense and liability lines and links the resulting entry to its payroll run. Repeating a payroll post returns the existing journal entry. Manual journal entries and reversals are committed transactionally by their API routes.

## Source import

After applying migrations, run `python -m scripts.load_phase2_task9`. The loader reads `chart_of_accounts.csv`, `journal_entries.csv`, and `journal_lines.csv` in bounded batches. Existing identifiers win on conflicts, so reruns do not replace posted records. Task 10's invoice and payment data references this chart of accounts and journal history.

## Reconciliation

The bundled checker was run against an export of the loaded database. Its journal-balance check passed with zero unbalanced entries and zero debit/credit difference. The payroll-to-ledger check also passed with a largest monthly difference of INR 0.00.
