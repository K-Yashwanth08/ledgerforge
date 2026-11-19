# Task 17: production deployment plan and evidence

Provider comparison checked on **2026-11-16**. Prices are USD, before taxes/egress, and can change.

| Provider | Sleep / availability | PostgreSQL and storage limits | Small always-on monthly cost |
|---|---|---|---:|
| Render | Free web services sleep after 15 idle minutes; paid web/worker plans stay on. A free database expires after 30 days. | Free Postgres is 1 GB, one database per workspace, no backups or pooling. Paid database plan chosen in `render.yaml`: 256 MB / 100 connections; configured 5 GB disk. | About **$31.20**: API $7 + worker $7 + Postgres compute $6 + 5 GB disk estimate $1.20 + persistent Key Value $10. Egress/overages extra. |
| Railway | Usage based; no free sleep guarantee on Hobby. | Hobby service volume limit is up to 5 GB. Postgres is a service backed by a volume; storage is $0.15/GB-month. | **$5 minimum** with $5 included usage; extra CPU/RAM/egress above included usage are metered. |
| Fly.io | Machines are billed by the second while running; autostop/autostart can reduce compute cost if configured. | Managed Postgres is available up to 1 TB; $0.28/GB-month storage. Basic managed cluster starts at $38/month and includes backups, HA, and pooling. | About **$42.66** for two 256 MB Machines ($2.19 each) plus Basic Postgres ($38) and 1 GB storage ($0.28), before queue and egress. |

Sources: [Render free-plan behavior and limits](https://render.com/docs/free), [Render pricing](https://render.com/pricing), [Render Postgres plan specs](https://render.com/docs/compute-plans), [Railway pricing and resource limits](https://docs.railway.com/pricing/plans), [Fly.io pricing](https://fly.io/pricing/), [Fly Managed Postgres limits and pricing](https://fly.io/docs/mpg/).

## Provider choice

Render is selected for this project because a single Blueprint can define the API, separate worker, persistent Redis-compatible Key Value, and managed PostgreSQL in the same Singapore region. The paid configuration avoids free web sleep and the expiring free database. Its 256 MB Postgres plan is a release-demo starting point only: 100 max connections and 256 MB RAM are tight, so Task 18 must measure and reassess it before real traffic. The listed monthly amount is an estimate from the published smallest plans; confirm the dashboard quote before provisioning.

## Repository changes

- `render.yaml` defines the Render services, private database/queue connections, generated JWT secret, migration/seed startup, and health path. No service credentials are hardcoded.
- `smoke_test.py` checks health, login, and a payroll calculation. It prints no token, password, employee identifier, or payroll amount.
- The existing mobile-responsive UI already provides login and payslip viewing. The payroll page now also records a monthly payroll run and links to the selected employee's saved payslip.
- Container startup runs migrations and loads all supplied source snapshots only when the key application tables are empty. Existing databases are left alone.

## Local seed-path evidence

The container initializer was exercised against a new temporary SQLite database, not the existing project database. Alembic completed and all seven loaders completed in order: 745 employees, 150,155 attendance rows, 18 payroll runs / 7,340 payroll items, plus the supplied ledger, invoices, expenses, and payments. The live-data exporter ran against this temporary database and `verify_ledgerforge.py checks --data <temporary-export>` reported **5/5 checks passed**. Temporary database/export files were removed. This verifies the seed workflow and bundled source snapshot; it is not a live-host result.

## Deployment steps once the GitHub and Render accounts are connected

1. Finish Task 16: build and start the Docker Compose stack, then commit the verified Task 16 changes and create `v1.0.0-rc1`. That tag is not present in this checkout yet.
2. In Render, connect `K-Yashwanth08/ledgerforge` and create a Blueprint from `render.yaml`. Choose the `v1.0.0-rc1` commit/tag for the first deploy. Review and confirm the service/database costs before provisioning.
3. Wait for API, worker, PostgreSQL, and Key Value resources to report healthy. The API startup applies Alembic migrations and loads the checked-in CSV source snapshots into a fresh database.
4. Open a Render shell on the API service and run `python -m scripts.create_initial_admin`. Complete the interactive email, password, and confirmation prompts. Sign in as that standalone Admin and provision an HR account linked to a loaded employee from the Users screen. Admin credentials are not seeded. To calculate payroll using the normal policy path, the employee also needs an approved tax election and the database needs independently verified, non-sample tax/statutory policy values.
5. Run the smoke test from PowerShell. Use the public service URL and the provisioned HR account:

   ```powershell
   $env:LEDGERFORGE_BASE_URL = 'https://<render-service>.onrender.com'
   $env:LEDGERFORGE_SMOKE_USERNAME = Read-Host 'HR login email'
   $securePassword = Read-Host 'HR password' -AsSecureString
   $env:LEDGERFORGE_SMOKE_PASSWORD = [Net.NetworkCredential]::new('', $securePassword).Password
   $env:LEDGERFORGE_SMOKE_EMPLOYEE_ID = Read-Host 'Loaded employee ID linked to the HR account'
   $env:LEDGERFORGE_SMOKE_MONTH = '2025-04'
   python smoke_test.py
   Remove-Item Env:LEDGERFORGE_SMOKE_PASSWORD
   ```

6. Open `https://<render-service>.onrender.com/docs` and the dashboard on a phone. Sign in with the HR user; record one payroll month, then open Payslips and download/view that employee's saved result.
7. For official checks, export the live database into a new local folder using the external database URL stored only in the current PowerShell process:

   ```powershell
   $env:DATABASE_URL = Read-Host 'Render external PostgreSQL URL'
   python -m scripts.export_phase2 --output outputs/live_export
   python verify_ledgerforge.py checks --data outputs/live_export
   Remove-Item Env:DATABASE_URL
   ```

Do not commit exported live data. It contains payroll and employee information. Run the `outputs/live_export` command only once per empty output directory; the exporter refuses to overwrite existing files.

## Current evidence and blockers

No Render/GitHub account integration is connected to this workspace. Docker is also unavailable, the release-candidate tag is absent, and no hosted database, credentials, or public URL were supplied. The repository's phase 3 audit also records that the supplied payroll policy is sample/unverified and authoritative tax inputs are not present. Therefore no hosted resource has been created, no live migration/login/payroll/check was run, and no phone screenshot or live link exists. Even after hosting is connected, a real payroll smoke test must wait for approved tax elections and verified production policy inputs; the app intentionally fails closed when these are missing or sample data. The deployment checklist above is prepared but those live acceptance items remain pending.

Initial capacity guess for Task 18: API/worker CPU and the small Postgres connection limit will constrain payroll and report requests before static dashboard delivery does. Measure request latency, database connections, and queue depth under concurrent load before increasing users or processing real payroll.
