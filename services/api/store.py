import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone
from .seed import EXPERTS, CLAIMS


def utcnow():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def db():
    path = os.getenv("BACKCAST_DB", str(Path(__file__).resolve().parents[2] / "backcast.sqlite3"))
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS authors (id TEXT PRIMARY KEY, data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sources (id TEXT PRIMARY KEY, author_id TEXT, data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS claims (id TEXT PRIMARY KEY, author_id TEXT, source_id TEXT, data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS evidence (id TEXT PRIMARY KEY, claim_id TEXT, data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS verdicts (id INTEGER PRIMARY KEY, claim_id TEXT, data TEXT NOT NULL, created_at TEXT);
        CREATE TABLE IF NOT EXISTS reviews (id TEXT PRIMARY KEY, claim_id TEXT, note TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS follows (author_id TEXT PRIMARY KEY, created_at TEXT);
        CREATE TABLE IF NOT EXISTS audits (id INTEGER PRIMARY KEY, action TEXT, record_id TEXT, created_at TEXT, data TEXT);
        CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, claim_id TEXT NOT NULL, data TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS claims_author_idx ON claims(author_id);
        CREATE INDEX IF NOT EXISTS evidence_claim_idx ON evidence(claim_id);
        CREATE INDEX IF NOT EXISTS reviews_claim_idx ON reviews(claim_id);
        """)
        if "status" not in {row["name"] for row in c.execute("PRAGMA table_info(reviews)")}:
            c.execute("ALTER TABLE reviews ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'")
        for row in c.execute("SELECT id,data FROM jobs").fetchall():
            job = json.loads(row["data"])
            if job["status"] in ("queued", "running"):
                job.update(
                    status="failed",
                    error="服务重启导致任务中断；请重新发起核验。",
                    updated_at=utcnow(),
                )
                c.execute(
                    "UPDATE jobs SET data=? WHERE id=?",
                    (json.dumps(job, ensure_ascii=False), row["id"]),
                )
        for a in EXPERTS:
            c.execute(
                "INSERT OR IGNORE INTO authors VALUES (?,?)",
                (a["id"], json.dumps(a, ensure_ascii=False)),
            )
        for claim in CLAIMS:
            source_id = "seed-" + claim["id"]
            c.execute(
                "INSERT OR IGNORE INTO sources VALUES (?,?,?)",
                (
                    source_id,
                    claim["author_id"],
                    json.dumps(
                        {
                            "url": claim["source_url"],
                            "text": claim["text"],
                            "published_at": claim["published_at"],
                            "provenance": "人工转述，非全文快照",
                            "recorded_at": utcnow(),
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
            if not c.execute("SELECT id FROM claims WHERE id=?", (claim["id"],)).fetchone():
                save_claim(c, claim, source_id)


def audit(c, action, id, data):
    c.execute(
        "INSERT INTO audits(action,record_id,created_at,data) VALUES (?,?,?,?)",
        (action, id, utcnow(), json.dumps(data, ensure_ascii=False)),
    )


def save_claim(c, claim, source_id):
    c.execute(
        "INSERT INTO claims VALUES (?,?,?,?)",
        (claim["id"], claim["author_id"], source_id, json.dumps(claim, ensure_ascii=False)),
    )
    for e in claim.get("evidence", []):
        c.execute(
            "INSERT INTO evidence VALUES (?,?,?)",
            (e["id"], claim["id"], json.dumps(e, ensure_ascii=False)),
        )
    c.execute(
        "INSERT INTO verdicts(claim_id,data,created_at) VALUES (?,?,?)",
        (claim["id"], json.dumps(claim["verdict"], ensure_ascii=False), utcnow()),
    )
    audit(c, "claim_created", claim["id"], claim)


def all_claims():
    with db() as c:
        return [json.loads(r["data"]) for r in c.execute("SELECT data FROM claims")]


def all_authors():
    with db() as c:
        followed = {r["author_id"] for r in c.execute("SELECT author_id FROM follows")}
        authors = [json.loads(r["data"]) for r in c.execute("SELECT data FROM authors")]
    for a in authors:
        a["followed"] = a["id"] in followed
    return authors
