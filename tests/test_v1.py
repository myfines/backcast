import os
import tempfile
import unittest
import json
from unittest.mock import patch
from fastapi.testclient import TestClient
from services.api.main import app
from services.api import store


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(
            os.environ,
            {
                "BACKCAST_DB": os.path.join(self.tmp.name, "v1.sqlite3"),
                "OPENAI_API_KEY": "",
                "SEARCH_API_KEY": "",
                "REVIEW_API_TOKEN": "test-review-token",
            },
        )
        self.env.start()
        self.context = TestClient(app)
        self.client = self.context.__enter__()

    def tearDown(self):
        self.context.__exit__(None, None, None)
        self.env.stop()
        self.tmp.cleanup()

    def test_author_list_pagination_scorecard_and_search(self):
        r = self.client.get("/api/v1/authors", params={"domain": "消费科技", "limit": 1})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["total"], 2)
        self.assertEqual(len(d["items"]), 1)
        self.assertIn("scorecard", d["items"][0])
        self.assertIsNone(d["items"][0]["scorecard"]["categorical"]["accuracy"])
        self.assertEqual(
            self.client.get("/api/v1/authors", params={"q": "Gurman"}).json()["total"], 1
        )
        self.assertEqual(
            self.client.get("/api/v1/authors", params={"limit": 1000}).status_code, 422
        )

    def test_detail_claims_report_and_audit(self):
        self.assertEqual(self.client.get("/api/v1/authors/kuo").status_code, 200)
        d = self.client.get("/api/v1/claims", params={"author_id": "kuo"}).json()
        self.assertEqual(d["total"], 1)
        self.assertEqual(self.client.get("/api/v1/claims/vision").json()["id"], "vision")
        self.assertEqual(self.client.get("/api/v1/authors/kuo/report").status_code, 200)
        self.assertGreater(len(self.client.get("/api/v1/claims/vision/audit").json()["items"]), 0)
        self.assertEqual(self.client.get("/api/v1/authors/missing").status_code, 404)

    def test_multiple_articles_append_to_same_author(self):
        author = self.client.post(
            "/api/v1/authors", json={"name": "测试分析师", "domain": "科技", "role": "分析师"}
        ).json()
        for _ in range(2):
            r = self.client.post(
                "/api/v1/import",
                json={
                    "author_id": author["id"],
                    "text": "我们预计这一项目将于2027年12月31日正式完成，请继续观察。",
                    "published_at": "2023-01-01",
                },
            )
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["author_id"], author["id"])
        self.assertEqual(self.client.get("/api/v1/authors").json()["total"], 6)
        self.assertEqual(
            self.client.get("/api/v1/claims", params={"author_id": author["id"]}).json()["total"], 2
        )

    def test_import_unknown_author_never_creates_orphan(self):
        r = self.client.post(
            "/api/v1/import",
            json={
                "author_id": "unknown",
                "text": "我们预计这一项目将于2027年12月31日正式完成，请继续观察。",
            },
        )
        self.assertEqual(r.status_code, 404)

    def resolution(self, **extra):
        d = {
            "status": "correct",
            "citations": ["vision-e"],
            "reason": "核对苹果实际上市日，处于先前报道的上市窗口内。",
            "reviewer": "测试复核员",
            "event_key": "vision-pro-us-launch",
            "outcome_at": "2024-02-02",
            "original_version_confirmed": True,
            "original_snapshot_url": "https://web.archive.org/web/20231226000000/https://example.com/original",
            "original_snapshot_at": "2023-12-26",
        }
        d.update(extra)
        return d

    def test_manual_resolution_requires_token_and_audits(self):
        path = "/api/v1/claims/vision/resolution"
        self.assertEqual(self.client.post(path, json=self.resolution()).status_code, 403)
        r = self.client.post(
            path, json=self.resolution(), headers={"X-Review-Token": "test-review-token"}
        )
        self.assertEqual(r.status_code, 200)
        d = self.client.get("/api/v1/authors/kuo/scorecard").json()
        self.assertEqual(d["categorical"]["n"], 1)
        self.assertFalse(d["readiness"]["eligible_for_ranking"])
        audit = self.client.get("/api/v1/claims/vision/audit").json()["items"]
        self.assertIn("manual_resolution", [a["action"] for a in audit])

    def test_manual_fake_reference_and_late_snapshot_rejected(self):
        path = "/api/v1/claims/vision/resolution"
        headers = {"X-Review-Token": "test-review-token"}
        self.assertEqual(
            self.client.post(
                path, json=self.resolution(citations=["fake"]), headers=headers
            ).status_code,
            422,
        )
        self.assertEqual(
            self.client.post(
                path, json=self.resolution(original_snapshot_at="2025-01-01"), headers=headers
            ).status_code,
            422,
        )

    def test_comparison_refuses_unmatched_or_cross_domain_ranking(self):
        r = self.client.post(
            "/api/v1/compare", json={"author_ids": ["kuo", "gurman"], "domain": "消费科技"}
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["comparable"])
        self.assertEqual(
            self.client.post(
                "/api/v1/compare", json={"author_ids": ["kuo", "unknown"]}
            ).status_code,
            404,
        )

    def test_background_verification_job_persists_failure(self):
        r = self.client.post("/api/v1/claims/vision/verification-jobs")
        self.assertEqual(r.status_code, 202)
        job = self.client.get("/api/v1/jobs/" + r.json()["id"]).json()
        self.assertEqual(job["status"], "failed")
        self.assertIn("配置", job["error"])

    def test_response_contract_is_in_openapi(self):
        d = self.client.get("/openapi.json").json()
        self.assertIn("/api/v1/authors", d["paths"])
        self.assertIn("Scorecard", d["components"]["schemas"])

    def test_report_as_of_never_shows_later_result(self):
        d = self.client.get("/api/v1/authors/kuo/report", params={"as_of": "2023-12-31"}).json()
        self.assertEqual(d["claims"][0]["evidence"], [])
        self.assertEqual(d["claims"][0]["verdict"]["status"], "pending")

    def test_probability_resolution_uses_literal_percentage_and_scores_brier(self):
        with store.db() as c:
            row = c.execute("SELECT data FROM claims WHERE id=?", ("vision",)).fetchone()
            record = json.loads(row["data"])
            record["text"] = "我们预计该产品有80%的概率在2024年02月10日前上市。"
            c.execute(
                "UPDATE claims SET data=? WHERE id=?",
                (json.dumps(record, ensure_ascii=False), "vision"),
            )
        body = self.resolution(
            forecast_format="probabilistic",
            probability=0.8,
            probability_quote="80%",
            binary_outcome=1,
        )
        r = self.client.post(
            "/api/v1/claims/vision/resolution",
            json=body,
            headers={"X-Review-Token": "test-review-token"},
        )
        self.assertEqual(r.status_code, 200)
        card = self.client.get("/api/v1/authors/kuo/scorecard").json()
        self.assertEqual(card["probabilistic"]["brier"], 0.04)
        self.assertEqual(card["categorical"]["n"], 0)
        body["probability"] = 0.9
        self.assertEqual(
            self.client.post(
                "/api/v1/claims/vision/resolution",
                json=body,
                headers={"X-Review-Token": "test-review-token"},
            ).status_code,
            422,
        )

    def test_evidence_origin_annotation_does_not_invent_independence(self):
        r = self.client.patch(
            "/api/v1/evidence/vision-e/metadata",
            json={
                "published_at": "2024-02-02",
                "origin_url": "https://www.apple.com/original",
                "origin_confirmed": True,
                "source_type": "primary",
                "reviewer": "复核员",
                "reason": "核对苹果发布记录，确认其为原始发布机构。",
            },
            headers={"X-Review-Token": "test-review-token"},
        )
        self.assertEqual(r.status_code, 200)
        card = self.client.get("/api/v1/authors/kuo/scorecard").json()
        self.assertEqual(card["evidence_quality"]["confirmed_origins"], 1)
        self.assertEqual(card["evidence_quality"]["confirmed_primary_sources"], 1)


if __name__ == "__main__":
    unittest.main()
