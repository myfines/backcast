"""Disposable E2E server; reset only its fixed test database, before app startup."""

import os
from pathlib import Path
import sys
import uvicorn

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
test_db = root / "docs" / "e2e.sqlite3"
test_db.unlink(missing_ok=True)
os.environ["BACKCAST_DB"] = str(test_db)
os.environ["OPENAI_API_KEY"] = ""
os.environ["SEARCH_API_KEY"] = ""
uvicorn.run("services.api.main:app", host="127.0.0.1", port=8001)
