# Task 7 payroll input and policy blockers

This project has salary structures, revision history, attendance, role assignments, and a `payroll_items.csv` reference result. The reference monetary fields are comparison-only; the calculator must not read them as inputs.

## Inputs not supplied

The current `data/` directory has no approved variable-pay event file, employee-linked loan or advance repayment schedule, employee tax-regime election, employee tax declaration, other-income record, or prior-employer tax record. `salary_components.csv` describes variable pay and loan recovery components, but contains no employee events or approved amounts. `journal_lines.csv` has aggregate advance-recovery postings, which cannot identify an employee, EMI, or payroll period and must not be used to derive payroll deductions.

The supplied `statutory_rates.csv` and `tax_slabs.csv` explicitly mark values as samples for training. `tax_parameters.csv` also marks the values as samples. These values support deterministic software exercises only; they do not establish statutory compliance.

## Required variable-pay event input

Provide an approved event source with at least:

| Field | Expected representation |
|---|---|
| `event_id` | Stable unique identifier |
| `employee_id` | Existing employee ID |
| `component_type` | Approved earning code, such as bonus, incentive, or award |
| `amount` | Non-negative decimal string with currency precision |
| `earning_period_start`, `earning_period_end` | ISO dates defining the earning period |
| `effective_date` | ISO date determining payroll inclusion |
| `approval_status` | Explicit approved/rejected/pending state |
| `approved_by`, `approved_at` | Approver and timestamp for approved events |
| `idempotency_key` | Stable import/API replay key |

Only approved, unprocessed events for the payroll period should be considered. The owner must specify treatment for reversals, partial-period earning, and events approved after payroll close.

## Required loan and advance schedule

Provide employee-linked schedules with `loan_id`, `employee_id`, approved principal, opening outstanding balance and as-of date, approved recovery amount/EMI, effective start/end dates, status, and the recovery transaction history. Define priority when the available net pay cannot cover the approved recovery, treatment of overpayments, and how payroll recovery is reconciled against the loan balance. Do not infer these values from account 1300 journal totals.

## Required tax inputs and authoritative rules

Provide an approved employee election by financial year and effective date, declared deductions/exemptions with approval and proof state, other taxable income, prior-employer salary and TDS, and any mid-year regime change rules. Identify the authoritative financial-year source and the applicable slabs, standard deduction, rebate/marginal relief, cess, surcharge, rounding, and annualization rules. The calculator currently uses the `NEW` regime and supplied sample tables; that is not an employee election.

## Statutory and overtime rules requiring verification

Provide authoritative effective-dated rules for PF eligibility, wage basis/ceiling and employer contribution treatment; ESI eligibility, wage basis/threshold and contribution treatment; professional-tax state/territory schedules and applicability dates; and overtime eligibility, pay base, multiplier, period cap, working-hours divisor, and rounding. The current parameter table contains a single sample professional-tax threshold/amount and sample PF/ESI/overtime values.

## Historical run inputs

Newly calculated payroll items persist a JSON input snapshot containing the calculation version, rounding policy, selected salary rows, employee eligibility flags, relevant attendance and overtime assignments, selected effective statutory rates, tax parameters/slabs, and explicitly supplied variable-pay/other-deduction inputs. Existing imported payroll rows are not modified; their `calculation_input_snapshot` remains null because the original input evidence was not supplied. Their persisted payroll values remain readable but cannot be reconstructed from a fabricated snapshot.

## Acceptance blockers

Task 7 remains in progress until authoritative payroll rules and employee-level inputs are supplied, implemented, and the comparison against `payroll_items.csv` meets its acceptance threshold. Current mismatches must remain visible as comparison results, never be fed back into calculation inputs.
