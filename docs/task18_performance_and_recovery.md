# Task 18: performance and recovery evidence

## Current state

The API has pagination on employee, payroll-run/item, and journal-entry lists.
The health route now runs `SELECT 1` against the configured database and returns
503 when it cannot connect. Request completion logs are emitted as JSON with a
request ID, method, path, status, and duration.

No runtime, query-plan, before/after index, load-test, or restore measurements
are recorded by this repository yet. Do not fill the table below with estimates.

| Measurement | Result | Evidence file / date |
|---|---|---|
| 18-month payroll runtime on disposable restored data | Pending | |
| Three slowest queries and EXPLAIN plans | Pending | |
| Index changes and before/after timings | Pending | |
| Backup restore into a fresh database | Pending | |
| Per-table row-count comparison | Pending | |

## Safe measurement sequence

1. Restore a backup into a disposable database and point `DATABASE_URL` only at
   that copy. Do not benchmark by creating payroll runs in the live database.
2. Time the 18-month job and record database size, employee count, machine size,
   and whether the database cache was warm. Preserve worker logs and job status.
3. Use PostgreSQL `EXPLAIN (ANALYZE, BUFFERS)` for the slowest observed SQL
   statements. Capture plans before proposing indexes; rerun the same workload
   afterward. Do not claim a gain without both measurements.
4. For a load test, use a disposable environment and synthetic accounts/data.
   No Locust scenario is currently included.

## PostgreSQL backup and restore rehearsal

Requires `pg_dump`, `pg_restore`, and SQLAlchemy's PostgreSQL driver. Backups
contain confidential employee and financial data. Store them outside Git, use a
restricted location, and do not paste database URLs into shared logs. The backup
command snapshots table row counts before `pg_dump`; quiesce writes during the
backup so the manifest and dump describe the same logical state.

```powershell
$env:DATABASE_URL = Read-Host 'Source PostgreSQL URL'
python -m scripts.backup_database --output backups/phase4-rehearsal.dump
```

Create a new empty PostgreSQL database for the restore rehearsal. The script
refuses a non-empty target. It restores into the database named by the URL and
compares every restored table row count with the backup manifest.

```powershell
$env:LEDGERFORGE_RESTORE_DATABASE_URL = Read-Host 'Fresh disposable target PostgreSQL URL'
python -m scripts.restore_verify --backup backups/phase4-rehearsal.dump
Remove-Item Env:LEDGERFORGE_RESTORE_DATABASE_URL
Remove-Item Env:DATABASE_URL
```

Record the command output, database/tool versions, restore duration, and row
counts in the measurement table above. Delete or securely retain the backup
according to the data owner’s policy; do not commit it.
