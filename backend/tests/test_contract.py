from app.export_openapi import SPEC_PATH, render


def test_committed_openapi_is_current():
    assert SPEC_PATH.read_text() == render(), (
        "openapi.json is stale. Run: uv run python -m app.export_openapi"
    )
