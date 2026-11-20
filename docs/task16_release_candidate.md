# Task 16 implementation and verification

## Implemented

- Application routers are available under `/api/v1`; original paths remain as hidden-schema compatibility routes. Health is available at `/api/v1/health`.
- `POST /api/v1/payroll/jobs/18-month` queues an 18-month batch in Celery. `GET /api/v1/payroll/jobs/{job_id}` returns Redis-backed state, month progress, and completed run IDs. Each monthly payroll commits independently.
- Docker Compose defines PostgreSQL, Redis, the API, and one Celery worker. The API applies migrations and runs the company CSV loader only when no employee rows exist.
- The Docker image uses a non-root account. `.dockerignore` excludes `.env` files and local databases. Compose supplies secrets at runtime from the untracked local `.env` file.
- GitHub Actions runs the current `tests/` suite and branch coverage on pushes and pull requests.

## Test evidence

Run from the repository root in PowerShell:

```powershell
python -m coverage run --branch -m pytest -q tests
python -m coverage report -m
```

Verified in the local `.venv`: **110 passed**, one Starlette deprecation warning, in 137.02 seconds. Branch coverage was **86% overall**. The weakest relevant utility found in the coverage report was `scripts/run_payroll_validation.py` at 41%; focused mismatch-classification tests raised it to **54%**. The new 18-month queue module is at **100%** coverage.

## Local setup

See the repository README for the clone, `.env` setup, and `docker compose up --build` commands. The compose YAML parses successfully and defines `db`, `redis`, `api`, and `worker` services.

## Outstanding release checks

Docker is not installed in the current environment, so image build, clean-volume startup, running-container screenshot, and an end-to-end Redis worker run could not be verified. The release-candidate tag was not created because those acceptance checks remain unverified. Do not treat the Compose acceptance item as passed until it is run on a machine with Docker Desktop.
