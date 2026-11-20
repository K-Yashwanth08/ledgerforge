# LedgerForge Phase 4 architecture

```mermaid
flowchart LR
    Browser[Responsive dashboard] -->|HTTPS / JSON / CSV| API[FastAPI application]
    API -->|SQLAlchemy| DB[(PostgreSQL)]
    API -->|enqueue / status| Redis[(Redis-compatible queue and result store)]
    Redis --> Worker[Celery payroll worker]
    Worker -->|monthly runs| DB
    Startup[Container startup] -->|Alembic migrations| DB
    Startup -->|empty database only| Loader[CSV seed loaders]
    Loader --> DB
    Render[Render Blueprint] --> API
    Render --> Worker
    Render --> DB
    Render --> Redis
```

The payroll worker commits one monthly run at a time. Job state and progress are
stored by Celery's result backend. CSV exports are generated from the database
by authenticated API routes. The live Render services, credentials, and hosting
evidence still need to be supplied by the deployment operator.
