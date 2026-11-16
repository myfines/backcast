import os, tempfile, unittest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from services.api.main import app
from services.api.zhihu import AccessBlocked


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(
            os.environ,
            {
                "BACKCAST_DB": os.path.join(self.temp.name, "research.sqlite3"),
                "RESEARCH_WORKER_TOKEN": "test-worker",
                "OPENAI_API_KEY": "",
            },
        )
        self.env.start()
        self.ctx = TestClient(app)
        self.client = self.ctx.__enter__()

    def tearDown(self):
        self.ctx.__exit__(None, None, None)
        self.env.stop()
        self.temp.cleanup()

    def material(self):
        return self.client.post(
            "/api/v1/text-audits",
            json={
                "source_url": "https://zhuanlan.zhihu.com/p/123",
                "title": "测试文章",
                "text": "原文指出GPT-3是1750亿参数的自回归语言模型。",
                "goal": "核查技术事实",
            },
        ).json()

    def output(self):
        return {
            "model": "test-model",
            "claims": [
                {
                    "quote": "GPT-3是1750亿参数的自回归语言模型",
                    "statement": "GPT-3有1750亿参数",
                    "kind": "fact",
                    "status": "correct",
                    "reason": "论文支持参数量。",
                    "evidence": [
                        {
                            "url": "https://arxiv.org/abs/2005.14165",
                            "source": "论文",
                            "quote": "175 billion parameters",
                            "published_at": "2020-05-28",
                        }
                    ],
                }
            ],
            "summary": "仅核查该节选。",
            "limitations": ["作者身份未确认"],
        }

    def test_collection_block_is_persisted_not_fake_success(self):
        with patch(
            "services.api.research.collect_history",
            side_effect=AccessBlocked("needs_login", "需要正常登录。"),
        ):
            r = self.client.post(
                "/api/v1/research-jobs", json={"target": "example", "goal": "检查技术判断"}
            )
        self.assertEqual(r.status_code, 202)
        job = self.client.get("/api/v1/research-jobs/" + r.json()["id"]).json()
        self.assertEqual(job["status"], "needs_login")
        self.assertEqual(job["coverage"]["captured"], 0)

    def test_configured_zhiarchive_collector_is_used(self):
        with patch.dict(os.environ, {"ZHIHU_BACKEND": "zhiarchive"}), patch(
            "services.api.zhiarchive.configured_history", AsyncMock(side_effect=AccessBlocked("blocked", "拒绝访问"))
        ) as collector:
            response = self.client.post("/api/v1/research-jobs", json={"target": "example", "goal": "查看历史判断"})
        collector.assert_awaited_once()
        job = self.client.get("/api/v1/research-jobs/" + response.json()["id"]).json()
        self.assertEqual(job["status"], "blocked")
        self.assertEqual(job["coverage"]["captured"], 0)

    def test_material_is_explicitly_not_person_history(self):
        job = self.material()
        self.assertEqual(job["status"], "awaiting_analysis")
        self.assertEqual(job["mode"], "provided_excerpt")
        self.assertFalse(job["coverage"]["complete"])

    def test_excerpt_preserves_edit_time_without_inventing_publication(self):
        body = dict(source_url="https://zhuanlan.zhihu.com/p/123", title="已编辑文章",
                    text="这是公开文章中有待核查的一段原文材料。", goal="核查公开事实",
                    edited_at="2026-11-16T16:17:00+08:00")
        response = self.client.post("/api/v1/text-audits", json=body)
        self.assertEqual(response.status_code, 201)
        doc = response.json()["documents"][0]
        self.assertEqual(doc["edited_at"], body["edited_at"])
        self.assertIsNone(doc["published_at"])
        body["edited_at"] = "not-a-date"
        self.assertEqual(self.client.post("/api/v1/text-audits", json=body).status_code, 422)

    def test_analysis_input_budget_is_disclosed(self):
        job = self.client.post(
            "/api/v1/text-audits",
            json={
                "source_url": "https://zhuanlan.zhihu.com/p/123",
                "title": "长文章",
                "text": "这是公开材料。" * 2000,
                "goal": "核查技术事实",
            },
        ).json()
        data = self.client.get(
            "/api/v1/research-jobs/" + job["id"] + "/input",
            headers={"X-Worker-Token": "test-worker"},
        ).json()
        self.assertLessEqual(len(data["sources"][0]["text"]), 6000)
        self.assertTrue(data["sources"][0]["analysis_excerpt_truncated"])

    def test_worker_requires_auth(self):
        job = self.material()
        r = self.client.post("/api/v1/research-jobs/" + job["id"] + "/analysis", json=self.output())
        self.assertEqual(r.status_code, 403)

    def test_model_cannot_invent_an_author_condition_before_fetch(self):
        job = self.material()
        output = self.output()
        output["claims"][0].update(mode="conditional", condition_quotes=["前提是股价翻倍。"])
        with patch("services.api.research.providers.fetch_page", AsyncMock()) as fetch:
            response = self.client.post("/api/v1/research-jobs/" + job["id"] + "/analysis",
                                        json=output, headers={"X-Worker-Token": "test-worker"})
        self.assertEqual(response.status_code, 422)
        fetch.assert_not_called()

    def test_reasoning_bonus_does_not_mask_a_factual_error(self):
        job = self.material()
        output = self.output()
        output["claims"][0].update(status="wrong", logic=dict(status="coherent",
            reason="模型认为论证自洽；这不证明前提事实正确。", quotes=["原文指出", "1750亿参数的自回归语言模型"]))
        with patch("services.api.research.providers.fetch_page", AsyncMock(return_value=dict(
                url="https://arxiv.org/abs/2005.14165", text="175 billion parameters", detected_date="2020-05-28"))):
            response = self.client.post("/api/v1/research-jobs/" + job["id"] + "/analysis",
                                        json=output, headers={"X-Worker-Token": "test-worker"})
        result = response.json()["result"]
        self.assertEqual(result["facts"]["contradicted"], 1)
        self.assertEqual(result["reasoning"]["bonus_points"], 1)

    def test_unresolved_scenario_is_not_a_failed_prediction(self):
        job = self.material()
        output = self.output()
        output["claims"][0].update(kind="prediction", mode="scenario", status="wrong", evidence=[])
        response = self.client.post("/api/v1/research-jobs/" + job["id"] + "/analysis",
                                    json=output, headers={"X-Worker-Token": "test-worker"})
        result = response.json()["result"]
        self.assertEqual(result["judgments"]["wrong"], 0)
        self.assertEqual(result["judgments"]["unverifiable"], 1)

    def test_quote_validation_before_network(self):
        job = self.material()
        out = self.output()
        out["claims"][0]["quote"] = "原文不存在的句子"
        with patch("services.api.research.providers.fetch_page", AsyncMock()) as fetch:
            r = self.client.post(
                "/api/v1/research-jobs/" + job["id"] + "/analysis",
                json=out,
                headers={"X-Worker-Token": "test-worker"},
            )
        self.assertEqual(r.status_code, 422)
        fetch.assert_not_called()

    def test_real_fetch_quote_grounding_and_fact_report(self):
        job = self.material()
        with patch(
            "services.api.research.providers.fetch_page",
            AsyncMock(
                return_value={
                    "text": "GPT-3 has 175 billion parameters.",
                    "detected_date": "2020-05-28",
                    "url": "https://arxiv.org/abs/2005.14165",
                    "title": "论文",
                }
            ),
        ):
            r = self.client.post(
                "/api/v1/research-jobs/" + job["id"] + "/analysis",
                json=self.output(),
                headers={"X-Worker-Token": "test-worker"},
            )
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["status"], "succeeded")
        self.assertEqual(d["result"]["facts"]["supported"], 1)
        self.assertFalse(d["result"]["can_recommend_person"])
        self.assertEqual(d["result"]["model"], "test-model")

    def test_fabricated_evidence_quote_is_not_accepted(self):
        job = self.material()
        with patch(
            "services.api.research.providers.fetch_page",
            AsyncMock(
                return_value={
                    "text": "unrelated text",
                    "detected_date": "2020-05-28",
                    "url": "https://arxiv.org/abs/2005.14165",
                    "title": "论文",
                }
            ),
        ):
            r = self.client.post(
                "/api/v1/research-jobs/" + job["id"] + "/analysis",
                json=self.output(),
                headers={"X-Worker-Token": "test-worker"},
            )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["result"]["facts"]["supported"], 0)
        self.assertEqual(r.json()["result"]["facts"]["insufficient"], 1)

    def test_failed_evidence_is_not_retried_for_another_claim(self):
        job = self.material()
        out = self.output()
        out["claims"].append(dict(out["claims"][0]))
        with patch(
            "services.api.research.providers.fetch_page",
            AsyncMock(side_effect=ValueError("blocked")),
        ) as fetch:
            r = self.client.post(
                "/api/v1/research-jobs/" + job["id"] + "/analysis",
                json=out,
                headers={"X-Worker-Token": "test-worker"},
            )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(fetch.await_count, 1)

    def test_completed_analysis_cannot_be_overwritten(self):
        job = self.material()
        with patch(
            "services.api.research.providers.fetch_page",
            AsyncMock(
                return_value={
                    "text": "175 billion parameters",
                    "detected_date": "2020-05-28",
                    "url": "https://arxiv.org/abs/2005.14165",
                }
            ),
        ):
            self.client.post(
                "/api/v1/research-jobs/" + job["id"] + "/analysis",
                json=self.output(),
                headers={"X-Worker-Token": "test-worker"},
            )
        r = self.client.post(
            "/api/v1/research-jobs/" + job["id"] + "/analysis",
            json=self.output(),
            headers={"X-Worker-Token": "test-worker"},
        )
        self.assertEqual(r.status_code, 409)

    def test_real_collector_flow_with_mocked_transport_only(self):
        class Reader:
            def call(self, op, target, offset=0, limit=10):
                if op == "profile":
                    return {"name": "测试答主", "url_token": target}
                return {
                    "data": [
                        {
                            "id": "100",
                            "content": "原文指出GPT-3是1750亿参数的自回归语言模型。",
                            "author": {"url_token": target},
                            "question": {"id": "9"},
                            "created_time": 1609459200,
                        }
                    ],
                    "paging": {"is_end": True},
                }

        with patch("services.api.research.LibraryTransport", return_value=Reader()):
            r = self.client.post(
                "/api/v1/research-jobs",
                json={"target": "example", "goal": "检查技术判断", "kinds": ["answer"]},
            )
        job = self.client.get("/api/v1/research-jobs/" + r.json()["id"]).json()
        self.assertEqual(job["status"], "awaiting_analysis")
        self.assertEqual(job["coverage"]["captured"], 1)
        payload = self.client.get(
            "/api/v1/research-jobs/" + job["id"] + "/input",
            headers={"X-Worker-Token": "test-worker"},
        ).json()
        self.assertIn("GPT-3", payload["sources"][0]["text"])


if __name__ == "__main__":
    unittest.main()
