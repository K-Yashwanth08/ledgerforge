# Phase 2 Task 10 — Clients and receivables

## Scope

Task 10 adds client records, draft invoices, invoice line items, payments, and client receivables. Invoices use INR and calculate GST from the supplied invoice tax rates: 0% and 18%. Other rates are rejected because the source data does not define them. Each line posts revenue to an active income account.

## API

All routes require an HR or admin bearer token. Tokens are validated by the shared authentication layer; the application does not issue tokens.

- `GET /clients` with optional name search, active-only filter, limit, and offset
- `POST /clients`, `GET /clients/{client_id}`, and `PATCH /clients/{client_id}`
- `GET /invoices` with optional status, client, invoice number search, limit, and offset
- `POST /invoices`, `GET /invoices/{invoice_id}`, and `PATCH /invoices/{invoice_id}`
- `POST /invoices/{invoice_id}/send`
- `POST /invoices/{invoice_id}/payments`
- `POST /invoices/{invoice_id}/cancel`
- `GET /receivables`

Invoices start as drafts. Draft edits recalculate line amounts, subtotal, GST, total, and outstanding balance. Sending posts accounts receivable, revenue, and GST output as a balanced journal entry. Sent invoices cannot be edited. The explicit transition map allows draft to sent/overdue/cancelled, sent or overdue to partial/paid/cancelled, and partial to overdue/partial/paid. Paid and cancelled are terminal. Repeating send or cancellation returns the already completed state without adding another journal entry.

Payments post a bank receipt against receivables and update the invoice balance. An idempotency key only replays when invoice, amount, date, payment mode, and reference all match. A conditional database update reserves outstanding balance as part of the same transaction as the payment and journal rows, preventing concurrent overpayments. Overdue status is refreshed from due dates when invoices or receivables are listed.

Drafts can be cancelled directly. A sent invoice with no payments is cancelled by posting a reversing journal entry. Invoices with payments cannot be cancelled through this route; they require a refund or credit-note workflow.

## Source import

Apply migrations and load Task 9's chart of accounts and journal history first. Then run `python -m scripts.load_phase2_task10`. The loader imports `clients.csv`, `invoices.csv`, `invoice_items.csv`, and `invoice_payments.csv` in bounded batches. Existing identifiers win on conflicts, and imported payment keys are namespaced to avoid colliding with API-created idempotency keys.

## Reconciliation

The bundled checker was run against an export of the loaded database. Its receivables check passed: account 1100 and open invoice balances both totaled INR 139,394,278.00. The endpoint returned client-level balances for 22 clients; the first three open balances were CL-002 INR 17,671,562.00, CL-008 INR 14,211,212.00, and CL-017 INR 10,641,476.00.
