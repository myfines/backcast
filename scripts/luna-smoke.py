"""Replay a real in-session Luna answer through actual backend quote checks.

The answer is a saved model output, not a persistent Luna connection. External
evidence is fetched for real. The database is isolated from users' demo data.
"""

import json
import argparse
import os
from pathlib import Path
import secrets
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from fastapi.testclient import TestClient
from services.api.main import app

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=root / "docs/examples/luna-analysis.json")
    parser.add_argument("--output", type=Path, default=root / "docs/examples/luna-smoke-result.json")
    args = parser.parse_args()
    token = secrets.token_urlsafe(24)
    os.environ["BACKCAST_DB"] = str(root / ".local/luna-smoke.sqlite3")
    os.environ["RESEARCH_WORKER_TOKEN"] = token
    (root / ".local").mkdir(exist_ok=True)
    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    with TestClient(app) as client:
        created = client.post("/api/v1/text-audits", json=fixture["material"])
        created.raise_for_status()
        job = created.json()
        result = client.post(
            "/api/v1/research-jobs/" + job["id"] + "/analysis",
            json=fixture["analysis"],
            headers={"X-Worker-Token": token},
        )
        result.raise_for_status()
        data = result.json()
    output = {
        "job_id": data["id"],
        "status": data["status"],
        "mode": data["mode"],
        "coverage": data["coverage"],
        "result": data["result"],
    }
    path = args.output
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, ensure_ascii=True, indent=2))
