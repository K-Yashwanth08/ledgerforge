"""Apply migrations and optionally load company CSVs only into an empty DB."""
import os
import subprocess
import sys

from app.database import SessionLocal
from app.models import ChartOfAccount, Department, Employee, JournalEntry, PayrollRun, User

SEED_COMMANDS = (
    "scripts.load_company_data",
    "scripts.load_phase2_task9",
    "scripts.load_phase2_task6",
    "scripts.load_phase2_task7",
    "scripts.load_phase2_task10",
    "scripts.load_phase3_task11",
    "scripts.load_phase3_task12",
)


def initialize_database() -> None:
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    if os.getenv("SEED_COMPANY_DATA", "true").casefold() in {"1", "true", "yes"}:
        with SessionLocal() as db:
            # Only run destructive company-source replacement when the
            # application database is genuinely empty, not merely missing HR.
            needs_seed = all(db.query(model).count() == 0 for model in
                             (Department, Employee, ChartOfAccount, JournalEntry, PayrollRun, User))
        if needs_seed:
            # Seed all supplied snapshots in FK order. This path is never run
            # against a database containing application records.
            for module in SEED_COMMANDS:
                subprocess.run([sys.executable, "-m", module], check=True)


def main() -> None:
    initialize_database()
    port = os.getenv("PORT", "8000")
    os.execvp("uvicorn", ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", port])


if __name__ == "__main__":
    main()
