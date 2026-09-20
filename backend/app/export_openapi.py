"""Regenerate the backend's committed API contract: `uv run python -m app.export_openapi`.

The spec lives at backend/openapi.json. The repo-root openapi.json is a different, frozen file: the
old prototype API that the frontend's `npm run gen:api` still generates its legacy types from.
"""

import json
from pathlib import Path

from app.main import app

SPEC_PATH = Path(__file__).resolve().parents[1] / "openapi.json"


def render() -> str:
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    SPEC_PATH.write_text(render())
    print(f"wrote {SPEC_PATH}")
