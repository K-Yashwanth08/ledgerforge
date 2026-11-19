
# LedgerForge – Complete Project

**Aura Workforce | Python Track**

LedgerForge is a FastAPI-based workforce management and financial management application developed across multiple project phases. It combines employee management, attendance, payroll processing, accounting, expense management, authentication, tax configuration, and financial reporting.

## Project Structure

```text
ledgerforge/
│
├── README.md
├── README_backup_before_consolidation.md
├── phase-1/
├── phase-2/
├── phase-3/
└── phase-4/       # To be added after completion
```

## Phase Overview

### Phase 1 – Employee Management Foundation

Implemented the foundational employee management system.

Key areas:
- Employee management and organization structure.
- Departments, roles, and employee assignments.
- Salary structures and salary revisions.
- FastAPI application and REST APIs.
- SQLAlchemy database models and Alembic migrations.
- CSV-based organization data loading.

Documentation: `phase-1/docs/`

### Phase 2 – Attendance, Payroll and Accounting

Extended the application with workforce operations and financial workflows.

Key areas:
- Attendance and leave management.
- Payroll processing and salary calculations.
- Employee salary history.
- Chart of accounts and accounting ledger.
- Client invoicing and receivables.
- Journal entries and financial transactions.

Documentation: `phase-2/docs/`

### Phase 3 – Financial Controls, Security and Reporting

Extended LedgerForge with financial controls and reporting capabilities.

Key areas:
- Vendor bills and expense management.
- Expense approval and payment workflows.
- Payroll-to-ledger integration.
- JWT authentication and role-based access control.
- Configurable tax and statutory parameters.
- Trial Balance, Profit and Loss, and Balance Sheet reports.
- Financial reconciliation and audit documentation.

Documentation: `phase-3/docs/`

### Phase 4 – Upcoming

This folder will be added when Phase 4 is released and completed.

## Technology Stack

- Python
- FastAPI
- SQLAlchemy
- Alembic
- SQLite / PostgreSQL
- REST APIs
- JWT authentication
- Pytest
- HTML, CSS and JavaScript dashboard

## Running the Application

The current development application is maintained at the repository root.

### 1. Clone the repository

```powershell
git clone https://github.com/K-Yashwanth08/ledgerforge.git
cd ledgerforge
```

### 2. Create a virtual environment

```powershell
python -m venv .venv
```

### 3. Activate the environment

```powershell
.\.venv\Scripts\Activate.ps1
```

### 4. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 5. Configure environment variables

```powershell
Copy-Item .env.example .env
```

Keep actual secrets and credentials in `.env`. Never commit this file.

### 6. Apply database migrations

```powershell
python -m alembic upgrade head
```

Back up existing databases before applying migrations.

### 7. Start the application

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8081
```

Open the dashboard at:

http://127.0.0.1:8081/

API documentation:

http://127.0.0.1:8081/docs

### 8. Run tests

```powershell
python -m pytest -q
```

## Development and Security Notes

- Each phase folder preserves its corresponding phase snapshot.
- The repository root contains the current integrated application.
- Keep `.env`, database credentials, JWT secrets, and private keys out of Git.
- Do not publish real employee, payroll, vendor, or financial personal data.
- Use synthetic or properly anonymized demonstration data for public review.
- Refer to each phase's `docs/` folder for implementation details and verification records.

## Repository

GitHub: https://github.com/K-Yashwanth08/ledgerforge

**Project:** LedgerForge  
**Track:** Python  
**Organization:** Aura Workforce

## Phase 4: Task 16 release-candidate setup

All application routers are available under `/api/v1` (for example, `POST /api/v1/auth/login` and `GET /api/v1/payroll/runs`). The original paths remain available for existing clients; new integrations should use the versioned paths. Interactive API documentation is at `/docs`.

### Start the Docker stack on a clean machine

Requirements: Git, Docker Desktop, and Docker Compose v2.

```powershell
git clone https://github.com/K-Yashwanth08/ledgerforge.git
Set-Location ledgerforge
Copy-Item .env.example .env
$secret = python -c "import secrets; print(secrets.token_urlsafe(48))"
(Get-Content .env) -replace '^LEDGERFORGE_JWT_SECRET=.*$', "LEDGERFORGE_JWT_SECRET=$secret" | Set-Content .env
# Edit POSTGRES_PASSWORD in .env to a unique local value before starting.
docker compose up --build
```

Compose starts PostgreSQL, Redis, the API, and a Celery worker. The API container applies Alembic migrations and loads the supplied company CSVs only when the employee table is empty. The loader replaces company-owned rows, so it is intentionally skipped for databases that already contain employees. PostgreSQL data persists in the `ledgerforge_pg` volume. Set `SEED_COMPANY_DATA=false` to skip loading. The local `.env` provides configuration at runtime and is excluded from the Docker build context; never put production values in `.env.example`.

Open `http://localhost:8000/docs` or `http://localhost:8000/api/v1/health`. Stop with `Ctrl+C`; use `docker compose down` to stop the containers while keeping the database volume. `docker compose down -v` deletes the local database volume.

### Queue an 18-month payroll batch

Authenticate as an existing HR or Admin user, then submit the first month of the 18-month period:

```powershell
$token = '<access token from /api/v1/auth/login>'
$headers = @{ Authorization = "Bearer $token" }
$job = Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/payroll/jobs/18-month -Headers $headers -ContentType 'application/json' -Body '{"start_month":"2025-01"}'
$job
Invoke-RestMethod -Uri "http://localhost:8000$($job.status_url)" -Headers $headers
```

The worker records the current month and completed payroll run IDs in Redis-backed job state. A failed batch reports its failed state; worker logs contain the underlying exception. Payroll is committed month by month, so completed months remain recorded if a later month fails.

### Tests, coverage, and CI

```powershell
python -m pip install -r requirements.txt
python -m coverage run --branch -m pytest -q tests
python -m coverage report -m
```

The GitHub Actions workflow at `.github/workflows/tests.yml` runs the test suite and prints branch coverage on every push and pull request. This catches regressions before changes are merged. CI uses an isolated test environment and does not access production credentials or data.

### Phase 4 Task 17 deployment preparation

The Render Blueprint is `render.yaml`; it defines the API, payroll worker, private persistent Redis-compatible queue, and hosted PostgreSQL. Compare hosting limits, deployment prerequisites, smoke-test configuration, and live-data export commands in [`docs/task17_deployment.md`](docs/task17_deployment.md). Run a live payroll check only after verified policy configuration and an approved employee tax election are present.
