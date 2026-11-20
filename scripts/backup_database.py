"""Create a PostgreSQL custom-format backup and a table-row-count manifest.

The output directory must be outside version control. Requires pg_dump and
DATABASE_URL. Credentials are passed to the child process through PG* env vars.
"""
import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

from sqlalchemy import MetaData, create_engine, func, select
from sqlalchemy.engine import make_url


def pg_environment(database_url: str) -> dict[str, str]:
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        raise ValueError("A PostgreSQL DATABASE_URL is required for pg_dump backups")
    env = os.environ.copy()
    env.update({"PGHOST": url.host or "localhost", "PGPORT": str(url.port or 5432),
        "PGUSER": url.username or "", "PGPASSWORD": url.password or "",
        "PGDATABASE": url.database or ""})
    if url.query.get("sslmode"):
        env["PGSSLMODE"] = str(url.query["sslmode"])
    return env


def table_counts(database_url: str) -> dict[str, int]:
    engine = create_engine(database_url)
    try:
        metadata = MetaData()
        metadata.reflect(bind=engine)
        with engine.connect() as connection:
            return {table.name: int(connection.scalar(select(func.count()).select_from(table)))
                    for table in sorted(metadata.tables.values(), key=lambda item: item.name)}
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="New .dump file outside Git")
    args = parser.parse_args()
    output = Path(args.output).resolve()
    manifest = output.with_suffix(output.suffix + ".manifest.json")
    if output.exists() or manifest.exists():
        parser.error("backup or manifest already exists; choose a new filename")
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        parser.error("DATABASE_URL is required")
    pg_env = pg_environment(database_url)
    if shutil.which("pg_dump") is None:
        parser.error("pg_dump must be installed and on PATH")
    counts = table_counts(database_url)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(["pg_dump", "--format=custom", "--no-owner", "--no-acl",
                        "--file", str(output)], env=pg_env, check=True)
        manifest.write_text(json.dumps({"format": "pg_dump_custom", "table_rows": counts},
            indent=2) + "\n", encoding="utf-8")
    except Exception:
        output.unlink(missing_ok=True)
        manifest.unlink(missing_ok=True)
        raise
    print(f"Backup created: {output.name}; row-count manifest: {manifest.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
