# Phase 3 Task 14 ? Configurable Tax and Statutory Rules

## Implemented

- Existing `tax_slabs`, `tax_parameters`, and `statutory_rates` remain the configuration source. Their effective dates, active flags, FY/regime keys, Decimal values, and existing Admin-only configuration routes are reused. No duplicate payroll engine or tax tables were added for these configurations.
- Added employee tax election submissions and review under `/tax/elections`; employee declaration submissions and review under `/tax/declarations`; and per-employee audit history under `/tax/audit/{employee_id}`. Employees can submit and read only their linked records. HR/Admin can review; decisions and submissions are audit logged. Overlapping elections and duplicate deduction-code declarations are rejected.
- Payroll selects the approved employee election effective for the employee and payroll date. Missing or conflicting elections fail closed; there is no silent NEW-regime fallback. Existing saved runs and calculation snapshots are unchanged.
- Payroll calculation blocks when applicable tax/statutory rows are explicitly labeled SAMPLE/TRAINING. The monthly statutory report separates employee PF/ESI deductions from employer contributions and includes expected persisted run totals, calculated payroll-item totals, differences, match flags, and a `policy_status`. A source-record reconciliation is not represented as legal compliance.
- `scripts/preview_tax_configuration.py --directory <folder>` validates a proposed three-file CSV bundle without writing to the database. It checks required columns, financial values, slab contiguity and ranges, effective-date overlap, duplicate versions, required parameter/rate names, per-row approval status, source reference, and sample markers. It returns a JSON validation report and never activates policy.

## Authoritative input status

No official tax rules, PF/ESI source documents, employee elections, or deduction declarations were provided. Existing checked-in values are training data and must not be used for production payroll. The preview of `data/` reports **27 sample rows, 28 unapproved rows, and 69 validation errors**; it is not production-ready. Evidence is in `outputs/phase3_evidence/task14_import_preview.json`. Required source owners, fields, and validation steps are listed in [task14_required_external_inputs.md](task14_required_external_inputs.md).

Approved declarations are recorded with status, reviewer, timestamp, optional supporting-document reference, and audit events. Their amounts are not applied to taxable income yet: the official deduction codes, caps, and mapping to taxable basis are not supplied. The taxable-basis limitation also remains: the existing engine annualizes fixed monthly salary; variable pay/overtime and employee-specific declarations are not incorporated. Configuration rows have a free-form note rather than a verified approval registry; preview is validation only. These gaps prevent statutory acceptance.

## Historical reconciliation

`outputs/phase3_evidence/task14_statutory_reconciliation.csv` compares all 7,340 persisted payroll items against the checked-in historical CSV for April 2025?September 2026. PF employee/employer, ESI employee/employer, and TDS match each source month at INR 0.00 difference; employer PF+ESI matches each run?s contribution total at INR 0.00. This is a historical sample-data match, not an independent or authoritative tax calculation.

The three new election/declaration/audit tables currently contain zero rows; no employee data was invented. Counts are in `outputs/phase3_evidence/task14_employee_inputs_status.json`.

## Migration and integrity

Migration `m8f41c2b7e90` adds only election, declaration, and audit tables. A clean migration chain passed. Before applying it to the live SQLite database, a persistent SQLite backup was written to the ignored `backups/ledgerforge_pre_m8_task14.db`, passed `PRAGMA integrity_check`, and matched all pre-existing table hashes. After migration, every pre-existing table hash matched the backup. Payroll remains 18 runs and 7,340 items; journals remain 2,524 entries and 6,784 lines; employer cost remains INR 861,586,392.42; debit-credit difference remains INR 0.00. The earlier `l7e4a2c9d610` migration's missing pre-backup caveat remains documented in the final audit.

## Verification and status

Election/declaration ownership, approval, audit, duplicate and missing-election tests pass. Sample-policy payroll rejection and CSV preview tests pass. Full suite results are in `phase3_final_audit.md`.

**Status: BLOCKED for statutory acceptance.** Official central tax, ESI, and the 17 September 2026 EPF ceiling change have now been sourced and recorded in [required inputs](task14_required_external_inputs.md). They remain candidate inputs, not employer-approved production configuration. Employee elections/declarations, jurisdiction and coverage decisions, policy-owner approval, deduction/taxable-basis mapping, and correct effective-date handling are still required. In particular, the current monthly payroll engine cannot split the EPF ceiling change effective 17 September 2026 and uses an older wage-base assumption; do not activate that configuration until the engine and transition rules are reviewed. Historical calculations remain unchanged.
