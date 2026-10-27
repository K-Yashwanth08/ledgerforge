# LedgerForge â€” Phase 1

LedgerForge is a FastAPI employee management foundation with a browser dashboard, SQLAlchemy data model, Alembic migrations, and a repeatable loader for the supplied organization and salary CSVs. The `/` dashboard supports employee create, view, edit, and soft-delete operations; interactive API documentation is at `/docs`.

## Phase 2 dashboard

The responsive dashboard at `/` provides live employee and department metrics, a searchable and paginated employee directory, employee management, an organisation view, and salary structure/revision viewing. The employee list accepts optional `search`, `department_id`, and `role_id` filters alongside `limit` and `offset`. Task 6 adds attendance summaries and leave APIs. Tasks 9 and 10 add the accounting ledger and client invoicing APIs; Tasks 7 and 8 remain in progress. Salary history and attendance are sensitive; access them only where authorized.

Use the existing local development command in step 9 to serve the interface. The theme toggle saves its preference in the browser. Set `window.LEDGERFORGE_API_BASE` before the dashboard script only when the API is hosted under a non-empty base path; same-origin is the default.

## Run this project in 10 steps

Commands below use Windows PowerShell. From Linux/macOS, replace activation with `source .venv/bin/activate` and use `cp .env.example .env`.

1. Install Python 3.11+ and Git. Check with `python --version` and `git --version`.
2. Open this folder: `Set-Location D:\05_Starter_Project`.
3. Create an environment: `python -m venv .venv`.
4. Activate it: `.\.venv\Scripts\Activate.ps1`.
5. Install dependencies: `python -m pip install -r requirements.txt`.
6. Create local settings if needed: `Copy-Item .env.example .env`. Keep `.env` private.
7. Create database tables: `python -m alembic upgrade head`.
8. Load supplied organization data: `python -m scripts.load_company_data`.
9. Start the app: `python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8081`. Open `http://127.0.0.1:8081/` for the dashboard or `/docs` for Swagger.
10. In another activated terminal, run `python -m pytest -q`.

## What is included

- `app/` contains settings, database setup, models, API routes, schemas, and the dashboard.
- `scripts/load_company_data.py` loads departments, roles, employees, assignment history, salary components, revisions, and structures from `data/` in one transaction. It replaces these seven company-owned tables during a successful run.
- `data/` contains 11 departments, 58 roles, 745 employees, 1,606 assignments, 14 salary components, 2,459 salary revisions, and 12,295 salary structures. Attendance is supplied but not loaded by this phase.
- `alembic/` contains the versioned schema migration.
- `docs/` records the data model, API usage, source-data notes, and completion status.

The directory and API omit date of birth and other personal/sensitive employee fields. Departed employees remain in the database for audit purposes; the directory and direct-report team endpoint show active employees by default. API deletion is a soft delete which sets an exit date and status.

The Phase 1 company-data loader is a source refresh: a successful run replaces its seven company-owned tables, including salary revisions. The separate Task 6 loader streams attendance in batches and does not overwrite records already loaded by ID. Keep the source CSV files unchanged.

Phase 2 Task 9 and Task 10 loaders import chart-of-accounts/journal and client/receivables snapshots idempotently. Run `python -m scripts.load_phase2_task9` before `python -m scripts.load_phase2_task10` after applying migrations. See [Task 9 ledger notes](docs/phase2_task9.md) and [Task 10 invoicing notes](docs/phase2_task10.md) for route and behavior details.

The employee form uses `GET /departments` and `GET /roles?department_id=D01` to populate validated selections. Salary APIs use inclusive effective dates. Request `GET /employees/{employee_id}/salary?effective_date=YYYY-MM-DD` to retrieve applicable components, or `GET /employees/{employee_id}/salary/revisions` for history. A salary change can be recorded with `POST /employees/{employee_id}/salary/revisions`; the service closes each previous component through the day before the new effective date and retains its history. Read `docs/salary_history.md` for the five invalid source intervals preserved as inactive rows.

## Configuration and database

`DATABASE_URL` and `DATA_DIR` are read from environment variables or `.env`. The safe local default is SQLite. Set `DATABASE_URL` to a PostgreSQL URL to use PostgreSQL. To rebuild from scratch, use a new/empty database, run `python -m alembic upgrade head`, then load company data. Do not delete a database that contains work you need.

## Common issues

- **PowerShell blocks activation:** run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then activate again.
- **CSV missing:** check `DATA_DIR` and confirm all seven required files exist there.
- **Database URL error:** confirm SQLite URL spelling or that PostgreSQL is running and its driver is installed.
- **Port in use:** choose another port with `--port 8082`.
- **Old schema:** back up the database and apply `python -m alembic upgrade head`.

The existing local database was at Alembic revision `32155c5c0f3f` before this salary work. The new migrations were applied and verified on a separate test database; apply `python -m alembic upgrade head` to upgrade an existing database before using salary endpoints. Back it up first. The root `verify_ledgerforge.py` checks accounting/payroll exports and uses an external default directory `../03_Data/csv`; those accounting source tables are outside this employee-management starter dataset. Do not treat its checks as run until the required files are present.
