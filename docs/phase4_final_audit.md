# Phase 4 final audit and handover status

**Status: NOT READY FOR SUBMISSION.** This report intentionally separates code
present in the repository from live evidence that has not been captured.

| Task | Repository implementation | Verification / external evidence | Status |
|---|---|---|---|
| 16 — Release candidate | Versioned API, Celery job/status, Docker/Compose, tests and CI are present. | Fresh suite and actual Redis worker acceptance run pending; `v1.0.0-rc1` tag absent. Historical test/coverage results are in `docs/task16_release_candidate.md`. | Partial |
| 17 — Deployment | Render Blueprint, migrations/seed startup and smoke script are present. | No live Render URL, hosted login/run/payslip evidence, or live export. See `docs/task17_deployment.md`. | Partial |
| 18 — Performance/recovery | Pagination, DB health check, JSON request logging, backup/restore rehearsal scripts are present. | Runtime/query plans/index measurements and restore/row-count rehearsal are pending. No report cache or Locust workload is included. | Partial |
| 19 — Exports/docs | Employee, payroll, and journal CSV routes support date ranges and inclusive `since` filters. Architecture diagram is in `docs/phase4_architecture.md`. | Tests, ten README examples, and outside-reader feedback still need to be collected. | Partial |
| 20 — Handover | Export/checker tooling and this report are present. | The checked-in data passed five local integrity checks; no live export, payroll comparison, release tag, demo, or final challenge handover is recorded. | Not complete |

## Local data checker evidence

On 2026-11-20, `python verify_ledgerforge.py checks --data data` reported 5/5
passes against the repository’s checked-in data. This is not a claim about a
live deployment or a separate official reference dataset.

## Remaining manual evidence

- Fresh `pytest` and coverage output, plus an actual Compose/Redis worker run.
- Deployment from a reviewed RC commit/tag and live migration/login/payroll/
  payslip checks, after approved policy inputs and employee elections exist.
- Live data export and official checks; do not commit the export.
- Performance measurements and a backup restore into a fresh database.
- Evidence that another person followed the README, their feedback, and fixes.
- Five-minute demo recording/link and the separately specified final challenge.
- Release review followed by the intended `v1.0.0-rc1` and `v1.0.0` tags.
