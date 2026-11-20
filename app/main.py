import json
import logging
import logging.config
import time
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from sqlalchemy import text
from .routers import attendance, auth, departments, employees, expenses, invoices, ledger, leave, payroll, payslips, reports, roles, salaries, tax, users
from . import models  # register model metadata for Alembic
from .database import engine


class JsonLogFormatter(logging.Formatter):
    """Emit one compact JSON object per application log event."""
    def format(self, record: logging.LogRecord) -> str:
        payload = {"timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname, "logger": record.name, "message": record.getMessage()}
        for key in ("request_id", "method", "path", "status_code", "duration_ms"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


logging.config.dictConfig({"version": 1, "disable_existing_loggers": False,
    "formatters": {"json": {"()": JsonLogFormatter}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json", "stream": "ext://sys.stdout"}},
    "root": {"level": "INFO", "handlers": ["console"]}})
request_logger = logging.getLogger("ledgerforge.request")

app = FastAPI(title="LedgerForge", version="1.0.0-rc1", description="Employee operations and payroll foundation")
app.mount("/assets", StaticFiles(directory=Path(__file__).parent / "static"), name="assets")

@app.middleware("http")
async def structured_request_log(request: Request, call_next):
    request_id = uuid.uuid4().hex
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        request_logger.info("request_complete", extra={"request_id": request_id,
            "method": request.method, "path": request.url.path, "status_code": status_code,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2)})

@app.get("/health", tags=["system"])
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database health check failed") from exc
    return {"status": "ok", "service": "ledgerforge", "database": "ok"}
@app.get("/api/v1/health", tags=["system"])
def versioned_health(): return health()
routers = (departments.router, auth.router, users.router, employees.router, roles.router,
           salaries.router, attendance.router, leave.router, payroll.router, payslips.router,
           ledger.router, invoices.router, reports.router, tax.router, expenses.router)
for route in routers:
    app.include_router(route, prefix="/api/v1")
    # Preserve already deployed clients while publishing the versioned API.
    app.include_router(route, include_in_schema=False)

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard():
    return (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")
