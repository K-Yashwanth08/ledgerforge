# Salary history

The loader imports the supplied `data/salary_components.csv` (14 rows), `data/salary_revisions.csv` (2,459 rows), and `data/salary_structures.csv` (12,295 rows). Models and the migration preserve source IDs and snapshots. Monetary values use `Numeric` in SQLAlchemy and `Decimal` in calculations.

**Date convention:** both `effective_from` and `effective_to` are inclusive. Thus a raise effective January 1 closes the old structure on December 31; the new structure applies beginning January 1. `GET /employees/{id}/salary?effective_date=YYYY-MM-DD` returns the applicable component set. `GET /employees/{id}/salary/revisions` returns the full history. `POST /employees/{id}/salary/revisions` creates a revision transactionally and rejects duplicate dates, unknown employees/components/roles, negative amounts, and a revision dated before an existing active period.

## Source data audit

References in salary rows resolve to all 745 supplied employees, 58 roles, and 14 components. All 2,459 revisions have a matching employee and role; their 12,295 component rows point to the same employee, revision date, and matching component name/type. Fixed earning components match `new_annual_fixed` for every revision. The last revision role for each employee matches the current employee role. One employee has two revisions on 2021-04-01 (`SR-00439` market correction and `SR-00440` annual increment), which the history endpoint retains in revision-ID order.

Revision `SR-00439` has five structure rows (`SS-002191` through `SS-002195`) with `effective_from=2021-04-01` and `effective_to=2021-03-31`. These rows are retained exactly with `is_active=false`, because they have an empty/reversed interval; same-day revision `SR-00440` supplies the valid active periods. The loader reports this exception and does not silently rewrite or discard those source records. No other active salary intervals overlap.

Joining revisions have blank `previous_annual_fixed`, `pct_change`, and `approved_by`; these persist as `NULL`. `effective_to` is nullable for current salary periods. Salary fields are excluded from ordinary employee response schemas.
