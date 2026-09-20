"""The repo-root config files agree with the backend and with each other.

These files (`docker-compose.yml`, the CI workflow, the two OpenAPI specs) are read by people,
not by the app, so nothing else notices when they drift from `app/config.py`.
"""

import json
import re
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

from app.config import Settings
from app.export_openapi import SPEC_PATH

ROOT = Path(__file__).resolve().parents[2]


def test_docker_compose_postgres_matches_the_default_database_url():
    compose = (ROOT / "docker-compose.yml").read_text()

    def value(key: str) -> str:
        return re.search(rf"^\s*{key}:\s*(\S+)", compose, flags=re.MULTILINE).group(1)

    url = make_url(Settings.model_fields["database_url"].default)
    assert (url.username, url.password, url.database) == (
        value("POSTGRES_USER"),
        value("POSTGRES_PASSWORD"),
        value("POSTGRES_DB"),
    )
    assert url.drivername == "postgresql+asyncpg" and url.host == "localhost" and url.port == 5432
    # Local-only: a database with a public password must not be reachable from other machines.
    assert '"127.0.0.1:5432:5432"' in compose and '"127.0.0.1:6379:6379"' in compose


def test_the_two_openapi_specs_are_separate_and_the_frontends_input_exists():
    # The backend's spec lives in backend/; the export script and its committed copy agree on that.
    assert SPEC_PATH == ROOT / "backend" / "openapi.json" and SPEC_PATH.exists()
    # The repo-root spec is the frontend's `gen:api` input. Whatever it reads must exist, and the
    # frontend CI job compares the generated types against it.
    scripts = json.loads((ROOT / "frontend" / "package.json").read_text())["scripts"]
    source = re.search(r"openapi-typescript\s+(\S+)", scripts["gen:api"]).group(1)
    assert (ROOT / "frontend" / source).resolve().exists()


def test_ci_checks_the_backend_spec_where_it_lives():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "uv sync --frozen" in ci and "uv run pytest" in ci
    assert (
        "git diff --exit-code openapi.json" in ci
    )  # relative to backend/, i.e. backend/openapi.json
    assert "requirements" not in ci  # the old pip-based install is gone


@pytest.mark.parametrize("name", ["uv.lock", ".python-version", "openapi.json", "alembic.ini"])
def test_files_ci_relies_on_are_committed_in_backend(name):
    assert (ROOT / "backend" / name).exists()
