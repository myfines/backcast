import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from services.api.main import app
from services.api.providers import public_url


class APITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(
            os.environ,
            {
                "BACKCAST_DB": os.path.join(self.tmp.name, "test.sqlite3"),
                "OPENAI_API_KEY": "",
                "SEARCH_API_KEY": "",
            },
        )
        self.env.start()
        self.context = TestClient(app)
        self.client = self.context.__enter__()

    def tearDown(self):
        self.context.__exit__(None, None, None)
        self.env.stop()
        self.tmp.cleanup()

    def test_seeded_cases_have_sources_and_no_inflated_scores(self):
        r = self.client.get("/api/dashboard")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data["authors"]), 5)
        self.assertEqual(data["stats"]["effective"], 0)
        self.assertEqual(len({c["domain"] for c in data["claims"]}), 4)
        for c in data["claims"]:
            self.assertTrue(c["source_url"].startswith("https://"))
            self.assertTrue(c["evidence"][0]["url"])

    def test_follow_toggle_is_persistent(self):
        self.assertTrue(self.client.post("/api/authors/kuo/follow").json()["followed"])
        a = self.client.get("/api/dashboard").json()["authors"][0]
        self.assertTrue(a["followed"])
        self.assertFalse(self.client.post("/api/authors/kuo/follow").json()["followed"])

    def test_missing_author(self):
        self.assertEqual(self.client.post("/api/authors/missing/follow").status_code, 404)

    def test_import_rules_no_fabricated_verdict(self):
        r = self.client.post(
            "/api/import",
            json={
                "author": "测试作者",
                "published_at": "2023-01-01",
                "text": "我们预计这款设备将于2024年02月02日上市，供应链正在准备。",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["mode"], "rules")
        c = r.json()["claims"][0]
        self.assertEqual(c["verdict"]["status"], "insufficient")
        self.assertFalse(c["verdict"]["eligible"])
        self.assertEqual(c["deadline"], "2024-02-02")
        data = self.client.get("/api/dashboard").json()
        self.assertEqual(len(data["authors"]), 6)

    def test_missing_config_does_not_claim_verification(self):
        r = self.client.post("/api/claims/vision/verify")
        self.assertEqual(r.status_code, 422)

    def test_review_is_saved(self):
        r = self.client.post(
            "/api/claims/vision/reviews", json={"note": "请核对发布日期与原文上下文。"}
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(self.client.get("/api/claims/vision/reviews").json()), 1)

    def test_empty_import_and_bad_date_rejected(self):
        self.assertEqual(self.client.post("/api/import", json={"text": "短"}).status_code, 422)
        self.assertEqual(
            self.client.post(
                "/api/import",
                json={
                    "text": "预计明年这一产品会正式上市，请留意后续报道。",
                    "published_at": "invalid",
                },
            ).status_code,
            422,
        )

    def test_local_network_rejected(self):
        for url in [
            "http://127.0.0.1",
            "http://[::1]",
            "file:///etc/passwd",
            "http://169.254.169.254",
            "http://user:pass@example.com",
        ]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                public_url(url)

    def test_fabricated_extracted_quote_never_saved(self):
        with patch(
            "services.api.main.providers.extract",
            AsyncMock(side_effect=ValueError("模型抽取原句不在导入正文中")),
        ):
            r = self.client.post(
                "/api/import", json={"text": "这里是公开的原始文章正文，预计产品会在明年上市。"}
            )
        self.assertEqual(r.status_code, 502)
        self.assertEqual(len(self.client.get("/api/dashboard").json()["claims"]), 5)

    def test_missing_review_claim_rejected(self):
        self.assertEqual(
            self.client.post(
                "/api/claims/unknown/reviews", json={"note": "一条有效的纠错说明。"}
            ).status_code,
            404,
        )

    def test_live_pipeline_cites_fetched_timestamped_page(self):
        async def model(system, payload):
            return {
                "status": "correct",
                "reason": "网页正文证明上市日期位于预测窗口内。",
                "citations": [payload["evidence"][0]["id"]],
            }

        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test", "OPENAI_MODEL": "test"}),
            patch(
                "services.api.main.providers.search",
                AsyncMock(
                    return_value=[{"url": "https://example.com/result", "source": "测试边界"}]
                ),
            ),
            patch(
                "services.api.main.providers.fetch_page",
                AsyncMock(
                    return_value={
                        "url": "https://example.com/result",
                        "text": "实际发布日为2024年2月2日。",
                        "detected_date": "2024-02-02",
                    }
                ),
            ),
            patch("services.api.main.providers.llm", side_effect=model),
        ):
            r = self.client.post("/api/claims/vision/verify")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["verdict"]["status"], "correct")
        self.assertFalse(r.json()["verdict"]["eligible"])

    def test_live_pipeline_missing_timestamp_is_insufficient(self):
        async def model(system, payload):
            return {
                "status": "correct",
                "reason": "结果吻合",
                "citations": [payload["evidence"][0]["id"]],
            }

        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test", "OPENAI_MODEL": "test"}),
            patch(
                "services.api.main.providers.search",
                AsyncMock(
                    return_value=[{"url": "https://example.com/result", "source": "测试边界"}]
                ),
            ),
            patch(
                "services.api.main.providers.fetch_page",
                AsyncMock(
                    return_value={
                        "url": "https://example.com/result",
                        "text": "实际发布日为2024年2月2日。",
                        "detected_date": None,
                    }
                ),
            ),
            patch("services.api.main.providers.llm", side_effect=model),
        ):
            r = self.client.post("/api/claims/vision/verify")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["verdict"]["status"], "insufficient")

    def test_live_fabricated_reference_rejected_without_overwriting_record(self):
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test", "OPENAI_MODEL": "test"}),
            patch(
                "services.api.main.providers.search",
                AsyncMock(
                    return_value=[{"url": "https://example.com/result", "source": "测试边界"}]
                ),
            ),
            patch(
                "services.api.main.providers.fetch_page",
                AsyncMock(
                    return_value={
                        "url": "https://example.com/result",
                        "text": "这是一条已抓取的结果。",
                        "detected_date": "2024-02-02",
                    }
                ),
            ),
            patch(
                "services.api.main.providers.llm",
                AsyncMock(return_value={"status": "correct", "citations": ["invented"]}),
            ),
        ):
            r = self.client.post("/api/claims/vision/verify")
        self.assertEqual(r.status_code, 422)
        claim = self.client.get("/api/dashboard").json()["claims"][0]
        self.assertEqual(claim["evidence"][0]["source"], "Apple Newsroom")


if __name__ == "__main__":
    unittest.main()
