"""Restore a custom PostgreSQL dump into an empty database and compare row counts.

This is destructive to the target database. Use a freshly created disposable DB
and set LEDGERFORGE_RESTORE_DATABASE_URL explicitly before running.
"""
import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

from sqlalchemy import MetaData, create_engine, func, select
from sqlalchemy.engine import make_url

from scripts.backup_database import table_counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", required=True, help="Path to .dump file")
    args = parser.parse_args()
    backup = Path(args.backup).resolve()
    manifest_path = backup.with_suffix(backup.suffix + ".manifest.json")
    target_url = os.environ.get("LEDGERFORGE_RESTORE_DATABASE_URL", "")
    if not backup.is_file() or not manifest_path.is_file():
        parser.error("backup and its .manifest.json file are both required")
    if not target_url:
        parser.error("Set LEDGERFORGE_RESTORE_DATABASE_URL to a fresh disposable PostgreSQL database")
    url = make_url(target_url)
    if url.get_backend_name() != "postgresql":
        parser.error("LEDGERFORGE_RESTORE_DATABASE_URL must use PostgreSQL")
    if shutil.which("pg_restore") is None:
        parser.error("pg_restore must be installed and on PATH")
    before = table_counts(target_url)
    if any(before.values()):
        parser.error("target database is not empty; restore refused")
    env = os.environ.copy()
    env.update({"PGHOST": url.host or "localhost", "PGPORT": str(url.port or 5432),
        "PGUSER": url.username or "", "PGPASSWORD": url.password or "",
        "PGDATABASE": url.database or ""})
    if url.query.get("sslmode"):
        env["PGSSLMODE"] = str(url.query["sslmode"])
    subprocess.run(["pg_restore", "--exit-on-error", "--no-owner", "--no-acl",
                    "--dbname", url.database or "", str(backup)], env=env, check=True)
    expected = json.loads(manifest_path.read_text(encoding="utf-8"))["table_rows"]
    actual = table_counts(target_url)
    differences = {name: {"backup": expected.get(name, 0), "restored": actual.get(name, 0)}
                   for name in sorted(set(expected) | set(actual))
                   if expected.get(name, 0) != actual.get(name, 0)}
    if differences:
        print(json.dumps({"status": "MISMATCH", "tables": differences}, indent=2))
        return 1
    print(json.dumps({"status": "PASS", "tables_compared": len(expected),
                      "rows_by_table": actual}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
