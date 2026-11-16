import json
from pathlib import Path
import unittest
from services.api.main import app


class SnapshotTests(unittest.TestCase):
    def test_committed_openapi_matches_backend(self):
        path = Path(__file__).resolve().parents[1] / "docs" / "openapi.json"
        self.assertEqual(
            json.loads(path.read_text(encoding="utf-8")),
            app.openapi(),
            "API changed: run python scripts/export_contract.py and regenerate client types.",
        )
