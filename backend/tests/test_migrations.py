import os
import sqlite3
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def _alembic(db_url: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND,
        env={**os.environ, "DATABASE_URL": db_url},
        capture_output=True,
        text=True,
    )


def test_migrations_apply_and_match_the_models(tmp_path):
    db = tmp_path / "echo.db"
    url = f"sqlite+aiosqlite:///{db}"
    up = _alembic(url, "upgrade", "head")
    assert up.returncode == 0, up.stderr
    tables = {r[0] for r in sqlite3.connect(db).execute("select name from sqlite_master")}
    assert {"physicians", "patients", "specialists", "referrals", "match_runs"} <= tables
    # `alembic check` fails if the models have drifted from the migrations.
    check = _alembic(url, "check")
    assert check.returncode == 0, check.stdout + check.stderr
