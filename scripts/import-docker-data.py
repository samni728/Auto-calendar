#!/usr/bin/env python3
"""Copy the current project's Docker PostgreSQL data into the source-mode SQLite DB."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import Date, DateTime, create_engine, delete, insert, select, text

PROJECT_DIR = Path(__file__).resolve().parent.parent
SERVER_DIR = PROJECT_DIR / "server"
sys.path.insert(0, str(SERVER_DIR))

from app import models  # noqa: E402, F401
from app.db import Base  # noqa: E402

TABLES = (
    "users",
    "workspaces",
    "workspace_memberships",
    "rooms",
    "provider_connections",
    "oauth_states",
    "timeline_events",
    "event_mirrors",
    "user_sessions",
    "audit_logs",
)


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=PROJECT_DIR,
        check=check,
        text=True,
        capture_output=True,
    )


def dotenv() -> dict[str, str]:
    values: dict[str, str] = {}
    path = PROJECT_DIR / ".env"
    if not path.exists():
        return values
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def postgres_was_running() -> bool:
    result = run(["docker", "compose", "ps", "--services", "--status", "running"])
    return "postgres" in result.stdout.splitlines()


def start_postgres() -> None:
    run(["docker", "compose", "up", "-d", "postgres"])
    config = dotenv()
    user = config.get("POSTGRES_USER", "autocalendar")
    database = config.get("POSTGRES_DB", "autocalendar")
    for _ in range(30):
        result = run(
            [
                "docker", "compose", "exec", "-T", "postgres", "psql",
                "-U", user, "-d", database, "-At", "-c", "SELECT 1",
            ],
            check=False,
        )
        if result.returncode == 0:
            return
        time.sleep(1)
    raise RuntimeError("Docker PostgreSQL did not become ready")


def export_postgres() -> dict[str, list[dict]]:
    config = dotenv()
    user = config.get("POSTGRES_USER", "autocalendar")
    database = config.get("POSTGRES_DB", "autocalendar")
    exported: dict[str, list[dict]] = {}
    for table_name in TABLES:
        sql = f'SELECT row_to_json(source_row)::text FROM "{table_name}" AS source_row'
        result = run(
            [
                "docker", "compose", "exec", "-T", "postgres", "psql",
                "-U", user, "-d", database, "-At", "-c", sql,
            ]
        )
        exported[table_name] = [json.loads(line) for line in result.stdout.splitlines() if line]
    return exported


def convert_row(table_name: str, row: dict) -> dict:
    table = Base.metadata.tables[table_name]
    converted = dict(row)
    for column in table.columns:
        value = converted.get(column.name)
        if value is None:
            continue
        if isinstance(column.type, DateTime) and isinstance(value, str):
            converted[column.name] = datetime.fromisoformat(value.replace("Z", "+00:00"))
        elif isinstance(column.type, Date) and not isinstance(column.type, DateTime) and isinstance(value, str):
            converted[column.name] = date.fromisoformat(value)
    return converted


def sqlite_path(database_url: str) -> Path:
    prefix = "sqlite+pysqlite:///"
    if not database_url.startswith(prefix):
        raise RuntimeError("Docker data import is only available for the source-mode SQLite database")
    return Path(database_url.removeprefix(prefix)).resolve()


def import_sqlite(exported: dict[str, list[dict]], database_url: str) -> Path:
    path = sqlite_path(database_url)
    if not path.exists():
        raise RuntimeError("Source SQLite database does not exist; run the schema migration first")
    backup = path.with_name(f"{path.name}.backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(path, backup)
    engine = create_engine(database_url)

    preserved_sessions: list[tuple[str, dict]] = []
    with engine.connect() as connection:
        session_table = Base.metadata.tables["user_sessions"]
        user_table = Base.metadata.tables["users"]
        for row in connection.execute(
            select(session_table, user_table.c.email).join(
                user_table, session_table.c.user_id == user_table.c.id
            )
        ).mappings():
            session = {key: row[key] for key in session_table.columns.keys()}
            preserved_sessions.append((row["email"], session))

    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys = OFF"))
        for table_name in reversed(TABLES):
            connection.execute(delete(Base.metadata.tables[table_name]))
        for table_name in TABLES:
            rows = [convert_row(table_name, row) for row in exported[table_name]]
            if rows:
                connection.execute(insert(Base.metadata.tables[table_name]), rows)

        imported_users = {
            row.email: row.id
            for row in connection.execute(select(
                Base.metadata.tables["users"].c.email,
                Base.metadata.tables["users"].c.id,
            ))
        }
        token_hashes = set(connection.execute(select(
            Base.metadata.tables["user_sessions"].c.token_hash
        )).scalars())
        for email, session in preserved_sessions:
            imported_user_id = imported_users.get(email)
            if not imported_user_id or session["token_hash"] in token_hashes:
                continue
            session["user_id"] = imported_user_id
            connection.execute(insert(Base.metadata.tables["user_sessions"]), session)
            token_hashes.add(session["token_hash"])
        connection.execute(text("PRAGMA foreign_keys = ON"))
    return backup


def main() -> int:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        print("DATABASE_URL is required", file=sys.stderr)
        return 2
    was_running = postgres_was_running()
    try:
        start_postgres()
        exported = export_postgres()
        if not exported["users"] or not exported["workspaces"]:
            raise RuntimeError("Docker database does not contain an initialized workspace")
        backup = import_sqlite(exported, database_url)
        counts = ", ".join(f"{table}={len(rows)}" for table, rows in exported.items())
        print(f"Imported Docker data: {counts}")
        print(f"Previous SQLite backup: {backup}")
        return 0
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        detail = exc.stderr.strip() if isinstance(exc, subprocess.CalledProcessError) else str(exc)
        print(f"Import failed: {detail}", file=sys.stderr)
        return 1
    finally:
        if not was_running:
            run(["docker", "compose", "stop", "postgres"], check=False)


if __name__ == "__main__":
    raise SystemExit(main())
