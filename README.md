
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
