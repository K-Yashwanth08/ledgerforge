# Phase 2 Task 6 — Attendance and leave

## Source inventory and quality

The loader inspected `attendance.csv` (150,155 rows, 14 columns, dates 2025-04-01 through 2026-09-30), `leave_types.csv` (6), `leave_requests.csv` (3,441), `leave_balances.csv` (441 snapshots), and `holidays.csv` (19). Attendance date format is ISO `YYYY-MM-DD`; numeric hours are decimal strings; flags use `Y`/`N`; time values are stored verbatim as strings. There are 82,052 `PRESENT`, 59,087 `WFH`, 7,135 `PAID_LEAVE`, 1,180 `ABSENT_LOP`, 572 `HALF_DAY_UNPAID`, and 129 `UNPAID_LEAVE` records. The source has 198 `MISSING_CHECKOUT` rows, no duplicate employee/date keys, and two extended-hour clock strings such as `24:25`.

**Missing checkout policy:** a missing checkout stays null. No checkout time, hours, or overtime are inferred. Monthly summaries retain source `hours_worked` and `overtime_hours` as reported and expose a separate `missing_checkout_records` count. Extended-hour time strings are retained unchanged.

**Calendar policy:** weekdays Monday–Friday count as working days, except every date in the supplied holidays table. A supported half-day is one half-day on a single non-holiday weekday. Requests cannot cross financial years. A pending/approved date overlap is rejected.

## Monthly summary manual check

Independent manual counts were made by streaming the source CSV for 2025-04-01 through 2025-04-30. Only rows whose `attendance_date` fell in this inclusive range were counted. Statuses are counted directly; `ABSENT_LOP` is 1 absent day, `HALF_DAY_UNPAID` is 0.5 absent day; `late_flag=Y` is one occurrence; overtime is the sum of provided `overtime_hours`; missing checkouts are counted from `data_quality_flag`.

| Employee | Present | WFH | Absent | Paid leave | Unpaid leave | Late | Overtime | Missing checkout | Service match |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| EMP-0002 | 2 | 18 | 0 | 0 | 0 | 1 | 0.00 | 0 | Yes |
| EMP-0004 | 12 | 5 | 0 | 3 | 0 | 0 | 0.00 | 0 | Yes |
| EMP-0006 | 18 | 1 | 0 | 1 | 0 | 1 | 0.00 | 0 | Yes |

## Leave and loading behavior

Source balances are snapshots as of 2026-09-30 for FY2026-27. CL, SL, and EL are imported as distinct balance records. Existing imported records win on key conflicts, so rerunning the loader does not reset decisions or balance mutations made through the API. Attendance CSV is streamed with `ATTENDANCE_BATCH_SIZE` rows per read batch (default 5,000); SQLite writes use parameterized executemany below the variable limit.

New paid leave applications reserve available balance when checking other pending requests. Approval uses a transaction, a balance version predicate, and a conditional balance decrement; a repeated/concurrent decision cannot deduct twice. Rejection does not change balance. Unpaid LOP does not require a paid leave balance. Half-days are represented by `is_half_day=true` and `days=0.50`; there is no per-hour half-day policy in the provided data.

## Authorization

The existing project had no authentication system. New attendance/leave endpoints use HS256 bearer tokens validated against configured issuer, audience, and secret. No login/token-issuing endpoint was added. An external identity provider must issue tokens containing `sub`, `iat`, `exp`, `iss`, `aud`, and optional `role=hr|admin`; the default development secret disables protected endpoints with HTTP 503. This is an integration boundary, not a claim of production identity security.

## API routes

- `GET /attendance?start_date=&end_date=&employee_id=&department_id=` (HR/admin)
- `GET /attendance/summary/{employee_id}?month=YYYY-MM` (HR/admin)
- `GET /leave/types`, `GET /leave/balances/{employee_id}`, `GET /leave/requests`
- `POST /leave/requests`, `POST /leave/requests/{id}/approve`, `POST /leave/requests/{id}/reject`
