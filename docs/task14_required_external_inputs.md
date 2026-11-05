# Task 14 ? Required authoritative tax and statutory inputs

Production statutory payroll remains blocked until the payroll policy owner supplies and approves the following. The repository tax/statutory CSVs explicitly label the values as samples. Do not import them as production policy.

| Required input | Fields to supply | Provider | Validation before activation |
|---|---|---|---|
| Financial-year tax policy | Financial year, jurisdiction, regime identifiers, effective dates, publication/version reference | Tax policy owner / statutory authority | Match official publication and effective dates; preserve source copy and checksum. |
| Tax slabs | FY, regime, lower/upper limits, rate, effective start/end, approval status, source reference | Tax policy owner | Decimal ranges; zero start; contiguous non-overlapping ranges; exactly one final open-ended band per version. |
| Rebate threshold and amount, cess, standard deduction and other deductions | FY, regime, parameter name/value/unit, eligibility, effective dates, source reference | Tax policy owner | Confirm units, limits, interactions, and applicable employee classes against official policy. |
| PF rules | Employee/employer rates, wage base, ceilings, coverage/eligibility conditions, effective dates, exclusions, source | Payroll/statutory policy owner | Verify rules and ceilings by effective date; calculate employee and employer shares independently. |
| ESI rules | Employee/employer rates, wage base, eligibility threshold, coverage conditions, effective dates, source | Payroll/statutory policy owner | Verify ceiling, wage definition, continuation/eligibility rules, and rounding. |
| Professional tax and other local statutory rules | Applicable state/jurisdiction, slabs/thresholds, frequency, effective dates | Local payroll/statutory policy owner | Confirm jurisdiction and official schedule; do not infer from employee location. |
| Employee regime elections | Employee ID, FY, selected regime, election date, effective start/end, employee attestation | Each employee; HR validates identity | Reject overlap; retain prior elections; use only approved election effective on payroll period. |
| Employee declarations | Employee ID, FY, deduction code, declared amount, evidence reference, submission date, approval state | Employee submits; HR/tax reviewer approves | Validate supported deduction code, amount, document reference, applicable limits and approval trail. |

## Import format and process

The non-writing preview command expects these three UTF-8 CSV files in one directory: `tax_slabs.csv`, `tax_parameters.csv`, and `statutory_rates.csv`. Include `approval_status`, `source_reference`, and `note` on every row. Parameter rows must include FY, regime, and effective dates. Monetary values and rates must be decimal strings. Current sample CSVs do not meet this production-import contract.

Preview without database changes:

```powershell
.\.venv\Scripts\python.exe scripts\preview_tax_configuration.py --directory <approved-policy-csv-folder>
```

A production-ready preview is a validation result, not proof that the named source is authoritative. The responsible policy owner must independently verify and approve the source. After validation, configure in a non-production database first, test boundary and effective-date cases, compare against independently calculated examples, and obtain payroll-owner sign-off. Keep the original historical payroll snapshots unchanged. Employee elections/declarations must be reviewed through the authenticated API and retained with audit history.

## Official central sources reviewed (candidate inputs only)

The following government sources were checked on 2026-11-03. They establish national rules that may be candidates for configuration; they do not constitute employer approval, confirm employee applicability, or authorize replacing the sample configuration. Preserve their date ranges and the exact source versions when preparing a controlled import.

- FY 2025-26 / AY 2026-27 individual new-regime slabs and rebate: [Income Tax Department FAQ](https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/itr-2/itr-2-faqs) and [Finance Bill 2026 Memorandum, rates and 4% cess](https://www.indiabudget.gov.in/doc/memo.pdf). The official sources specify slabs ₹0–4L 0%, ₹4–8L 5%, ₹8–12L 10%, ₹12–16L 15%, ₹16–20L 20%, ₹20–24L 25%, and above ₹24L 30%; the new-regime rebate is up to ₹60,000 for taxable income up to ₹12L. The assessment-year terminology applies to FY 2025-26.
- Tax Year 2026-27 is governed by the Income-tax Act, 2025. The [Income Tax Department transition FAQ](https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/objective-and-scope-new-act-faq) and Finance Bill 2026 memorandum identify the new tax-year terminology and rates. The memorandum is a bill memorandum, so the policy owner must confirm final enactment and any later notifications before using it as an approved configuration.
- New-regime employee standard deduction: CBDT's [AY 2026-27 ITR validation rules](https://www.incometax.gov.in/iec/foportal/sites/default/files/2026-05/CBDT_e-Filing_ITR%201_Validation%20Rules_AY%202026-27.pdf) specify a ₹75,000 maximum. Verify eligibility and regime treatment before importing.
- ESI: [ESIC official overview](https://esic.gov.in/attachments/esistatedirectoratefile/ef84365f31f15306ddb397902d675858.pdf) lists ₹21,000 monthly wage limit (₹25,000 for persons with disabilities), employee rate 0.75%, employer rate 3.25%, and daily-wage employee exemption. A simple threshold/rate-only model does not represent all these eligibility and contribution-period rules.
- EPF ceiling: [PIB / Ministry of Labour release](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2311968&lang=2&reg=48) reports the statutory coverage ceiling increased to ₹25,000 effective 17 September 2026. Existing configuration/code used ₹15,000 and a basic-wage base. The payroll engine selects rates using the first day of the month and cannot split September 2026 at the 17th; the wage definition, membership/eligibility, EPS treatment, and transition handling therefore need a policy-owner-approved implementation before activating this change. Earlier periods must retain the historic ceiling.

These are *official-source findings*, not production-ready approved inputs. Do not activate them from this document alone.

## Remaining blockers

All checked-in tax/statutory CSV values are training/sample values. Even though central rules are now sourced, the employer's jurisdiction and applicable PF/ESI coverage, tax-policy owner approval, state-specific professional tax schedule, effective-dated employee regime elections, employee declarations/evidence/approval, and any organization-specific payroll policies remain missing. The engine currently stores approved deductions but does not apply them because deduction mapping/limits and the taxable-income treatment require confirmation. It also does not model all employee-specific ESI/PF eligibility or the 17 September 2026 PF transition. No production configuration was activated.
