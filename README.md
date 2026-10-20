# LedgerForge — Phase 1

LedgerForge is a FastAPI starter backed by SQLAlchemy. The current foundation provides a departments API and a repeatable CSV seed script. The supplied CSV files are in `data/`.

## Setup

1. **Prerequisites:** Install Python 3.11 or newer and Git; check with `python --version` and `git --version`.
2. **Obtain the project:** Clone your private `ledgerforge` repository with `git clone <repository-url>`, or use the project folder provided to you.
3. **Open the project:** In PowerShell, run `Set-Location D:\05_Starter_Project` (or your clone folder), then `code .`.
4. **Create a virtual environment:** Run `python -m venv .venv` from the project folder.
5. **Activate it on Windows:** Run `.\.venv\Scripts\Activate.ps1` in PowerShell.
6. **Install dependencies:** Run `python -m pip install -r requirements.txt`.
7. **Configure environment:** If `.env` does not exist, copy the safe template with `Copy-Item .env.example .env`. Set `DATA_DIR=data` in `.env`; preserve any other existing settings and keep secrets private.
8. **Seed the database:** Run `python -m scripts.seed_example`. It loads the supplied `data/departments.csv` rows and should report 11 departments.
9. **Start the API:** Run `python -m uvicorn app.main:app --host 127.0.0.1 --port 8081`. Open `http://127.0.0.1:8081/docs` and try `GET /departments` in Swagger UI.
10. **Run tests:** In a second terminal with the virtual environment active, run `python -m pytest -q`.

## Starter files

- `app/` contains the API, SQLAlchemy model, settings, and database session.
- `scripts/seed_example.py` loads department rows from the configured CSV directory.
- `data/` contains the supplied department, role, employee, and assignment CSV files.
- `tests/` contains the two starter API tests.
- `verify_ledgerforge.py` is at the project root. Its documented default validation directory is outside this workspace, so the validator's five checks cannot be run against the official dataset here.

Never commit `.env`, credentials, local database files, or the virtual environment. `.gitignore` excludes these local files.
