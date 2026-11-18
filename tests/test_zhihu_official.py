import os
import unittest
from unittest.mock import patch, AsyncMock

import httpx
from services.api.zhihu_official import OfficialClient, OfficialError, normalize_results
from services.api.zhihu_official import router
from fastapi import FastAPI
from fastapi.testclient import TestClient


class OfficialTests(unittest.IsolatedAsyncioTestCase):
    async def test_bearer_timestamp_and_exact_official_query(self):
        def handler(request):
            self.assertEqual(request.url.host, "developer.zhihu.com")
            self.assertEqual(request.headers["Authorization"], "Bearer test-secret")
            self.assertTrue(request.headers["X-Request-Timestamp"].isdigit())
            self.assertEqual(request.url.params["Query"], "历史判断")
            self.assertEqual(request.url.params["Count"], "3")
            return httpx.Response(200, json={"Code":0,"Data":{"Items":[],"HasMore":False}})
        client = OfficialClient(secret="test-secret", transport=httpx.MockTransport(handler))
        result = await client.search("历史判断", count=3)
        self.assertEqual(result["items"], [])
        self.assertFalse(result["coverage"]["complete_author_history"])

    async def test_application_auth_failure_never_exposes_secret(self):
        def handler(request):
            return httpx.Response(200, json={"Code":20001,"Message":"bad test-secret"})
        with self.assertRaises(OfficialError) as cm:
            await OfficialClient(secret="test-secret", transport=httpx.MockTransport(handler)).quota()
        self.assertNotIn("test-secret", str(cm.exception))
        self.assertEqual(cm.exception.code, "authentication_failed")

    async def test_no_auth_redirect_to_other_host(self):
        urls=[]
        def handler(request):
            urls.append(str(request.url))
            return httpx.Response(302, headers={"Location":"https://example.com/collect"})
        with self.assertRaises(OfficialError):
            await OfficialClient(secret="test-secret", transport=httpx.MockTransport(handler)).quota()
        self.assertEqual(len(urls), 1)

    async def test_summary_and_ambiguous_edit_time_remain_explicit(self):
        result = normalize_results({"Items":[{"Title":"历史观点","AuthorName":"同名作者",
            "Url":"https://zhuanlan.zhihu.com/p/1?utm_source=test","ContentText":"<em>判断</em>片段",
            "EditTime":1700000000}],"HasMore":False}, "zhihu", "历史观点")
        item=result["items"][0]
        self.assertEqual(item["text"], "判断片段")
        self.assertTrue(item["is_excerpt"])
        self.assertIsNone(item["published_at"])
        self.assertIsNone(item["edited_at"])
        self.assertFalse(item["author_identity_verified"])

    async def test_unsupported_scope_fails_before_network(self):
        with self.assertRaises(ValueError):
            await OfficialClient(secret="test-secret").search("历史判断", scope="private")

    async def test_missing_token_has_no_demo_fallback(self):
        with patch.dict(os.environ, {"ZHIHU_ACCESS_SECRET":"", "ZHIHU_CREDENTIAL_FILE":"missing-official-test.env"}):
            with self.assertRaises(OfficialError) as cm:
                await OfficialClient().quota()
        self.assertEqual(cm.exception.code, "not_configured")

    async def test_official_search_is_available_without_generic_search_key(self):
        from services.api import providers
        with patch.dict(os.environ, {"SEARCH_PROVIDER":"zhihu_official", "SEARCH_API_KEY":"", "ZHIHU_ACCESS_SECRET":"test-secret"}), patch(
            "services.api.zhihu_official.OfficialClient.search", AsyncMock(return_value={"items":[{"url":"https://example.com/report", "title":"报告"}]})) as search:
            self.assertTrue(providers.search_configured())
            result = await providers.search("核查收入")
        self.assertEqual(result[0]["source"], "报告")
        search.assert_awaited_once_with("核查收入", scope="web", count=4)

    async def test_routes_keep_secret_server_side_and_validate_before_requests(self):
        app=FastAPI();app.include_router(router)
        with patch.dict(os.environ,{"ZHIHU_ACCESS_SECRET":"test-secret"}), TestClient(app) as client:
            response=client.get("/api/v1/official/status")
            self.assertTrue(response.json()["configured"])
            self.assertNotIn("test-secret",response.text)
            with patch("services.api.zhihu_official.OfficialClient._get", AsyncMock(return_value={"Items":[],"HasMore":False})) as get:
                self.assertEqual(client.post("/api/v1/official/search",json={"query":"历史判断","count":3}).status_code,200)
                get.assert_awaited_once()
            with patch("services.api.zhihu_official.OfficialClient._get", AsyncMock()) as get:
                self.assertEqual(client.post("/api/v1/official/search",json={"query":"历史判断","count":11}).status_code,422)
                get.assert_not_called()
