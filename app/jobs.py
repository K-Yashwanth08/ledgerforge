"""Celery configuration and background payroll batch task."""
import os
from calendar import monthrange
from datetime import date

from celery import Celery

from .database import SessionLocal
from .payroll_service import run_payroll_month

celery_app = Celery("ledgerforge", broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
                    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1"))
celery_app.conf.update(task_track_started=True, result_expires=60 * 60 * 24,
                       task_serializer="json", result_serializer="json", accept_content=["json"])


def month_sequence(start_month: str, months: int = 18) -> list[tuple[str, date]]:
    year, month = map(int, start_month.split("-"))
    if not 1 <= month <= 12:
        raise ValueError("start_month must be a valid YYYY-MM month")
    result = []
    for _ in range(months):
        last_day = monthrange(year, month)[1]
        result.append((f"{year:04d}-{month:02d}", date(year, month, last_day)))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return result


@celery_app.task(bind=True, name="ledgerforge.run_18_month_payroll")
def run_18_month_payroll(self, start_month: str) -> dict:
    periods = month_sequence(start_month)
    run_ids = []
    for index, (month, pay_date) in enumerate(periods, start=1):
        self.update_state(state="PROGRESS", meta={"current": index - 1, "total": 18,
                                                   "month": month, "run_ids": run_ids})
        with SessionLocal() as db:
            run, _warnings = run_payroll_month(db, month, pay_date, run_by="background-job")
            run_ids.append(run.run_id)
        self.update_state(state="PROGRESS", meta={"current": index, "total": 18,
                                                   "month": month, "run_ids": run_ids})
    return {"current": 18, "total": 18, "run_ids": run_ids}
