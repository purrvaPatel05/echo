"""Write the OpenAPI spec to <repo>/openapi.json. Frontend generates its types from it.

    python -m app.export_openapi
"""
import json
from pathlib import Path

from .main import api

out = Path(__file__).resolve().parents[2] / "openapi.json"
out.write_text(json.dumps(api.openapi(), indent=2) + "\n")
print("wrote", out)
