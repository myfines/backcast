"""Export deterministic OpenAPI and real fixture responses; never reads production DB."""

import json
import os
from pathlib import Path
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from services.api.main import app
from fastapi.testclient import TestClient


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    write(root / "docs" / "openapi.json", app.openapi())
    with tempfile.TemporaryDirectory() as directory:
        os.environ["BACKCAST_DB"] = str(Path(directory) / "fixtures.sqlite3")
        with TestClient(app) as client:
            for name, url in [
                ("authors", "/api/v1/authors"),
                ("claim", "/api/v1/claims/vision"),
                ("scorecard", "/api/v1/authors/kuo/scorecard"),
                ("report", "/api/v1/authors/kuo/report"),
            ]:
                result = client.get(url)
                result.raise_for_status()
                write(root / "docs" / "examples" / f"{name}.json", result.json())
    print("Exported OpenAPI and four seed-only response examples.")
