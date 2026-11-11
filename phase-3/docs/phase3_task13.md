# Phase 3 Task 13 ? Authentication and Roles

## Implementation and live environment

- The live application database is `sqlite:///./ledgerforge.db`, resolved from `D:\05_Starter_Project`. Tests use isolated in-memory SQLite databases.
- The `users.employee_id` column is already nullable in migration `k6d9e31a4b72`, with a foreign key and unique constraint for linked accounts. No schema migration is required for a standalone Admin. Existing employee-linked HR and Employee accounts remain supported.
- The live users table now contains exactly one active standalone Admin (`employee_id = NULL`), with no HR or Employee accounts. Its username matches the operator-provided email and does not match the demo email entered during the latest failed bootstrap retry. That retry did not create an account. Password hashes and credentials were not read or recorded.
- A random `LEDGERFORGE_JWT_SECRET` is configured in ignored local `.env`; its value is not included in docs or command output. JWT expiry remains 1,800 seconds. Login uses salted scrypt hashes, and API authorization reads the active account and role from the database.
- Standalone Admins can manage users and use Admin-authorized system functions. Employee-specific payslip, payroll calculation, and payroll item routes reject an Admin without an employee association. Employee and HR authorization behavior is unchanged. The user-management API rejects creation of unlinked Admin accounts; the initial bootstrap is the only path for that account type.

## One-time local bootstrap

Run from an interactive terminal in the project directory after configuring the signing secret and applying migrations:

```powershell
.\.venv\Scripts\python.exe scripts\create_initial_admin.py
```

The command takes no identity or password arguments. It prompts for a unique email, a password and confirmation through `getpass`, and the phrase `CREATE FIRST ADMIN`. Passwords must be 14 to 128 characters, meet a three-category strength check, and not contain the email username. It writes an active `Admin` row with `employee_id = NULL`, a scrypt hash, and a creation timestamp in one transaction. A database-level transaction lock serializes concurrent bootstrap attempts on SQLite and PostgreSQL. It refuses to run non-interactively, if a JWT secret is missing, if an Admin already exists, or if the username is taken. No startup hook provisions users.

The bootstrap is deliberately not executed automatically. The live database already contains one Admin, so do not rerun it. Verify login, `/auth/me`, user management, and denial on employee-specific payroll/payslip routes. Do not send credentials in chat.

### Recover access to an existing standalone Admin

If the existing Admin password is unknown, run the local interactive recovery command:

```powershell
.\.venv\Scripts\python.exe scripts\reset_standalone_admin_password.py
```

It accepts no credential arguments, requires a terminal and configured JWT secret, prompts with `getpass`, and resets only the matching active Admin account with no employee link. Enter the exact registered Admin email and type `RESET EXISTING ADMIN PASSWORD` at the confirmation prompt. This is a local operator action; do not paste the password into chat or a command line. It does not create a new account or change payroll/employee records.

## Verification

- Isolated tests exercise standalone account creation, password confirmation/strength, hash storage, duplicate bootstrap prevention, login, 30-minute token, `/auth/me`, Admin user management, and denial on employee-specific payroll/payslip paths. Existing employee ownership and HR restrictions remain covered.
- Full suite: **92 passed, 1 existing Starlette/httpx deprecation warning, 0 failed** (74.04 seconds). Compilation and `git diff --check` passed. `alembic current` and `alembic heads` both report `m8f41c2b7e90`; live SQLite confirms `employee_id` nullable and one active standalone Admin. No migration was needed for standalone Admin; m8 added Task 14 election/declaration tables.

**Status:** One active standalone Admin exists and its username matches the operator-provided email. Live login still needs verification; do not rerun the one-time bootstrap.
