import unittest
from unittest.mock import patch
from services.api.zhiarchive import collect_zhiarchive, configured_history, ZhiArchiveGateway
from services.api.zhihu import AccessBlocked


class Gateway:
    def __init__(self, denied=False, mismatch=False):
        self.calls = []
        self.denied, self.mismatch = denied, mismatch

    async def call(self, name, arguments):
        self.calls.append((name, arguments))
        if self.denied:
            raise AccessBlocked("blocked", "知乎拒绝访问")
        if name == "list_zhihu_profile_items":
            offset = int(arguments.get("cursor") or 0)
            return dict(people="example", content_type="answer", offset=offset,
                        items=[dict(id=str(offset+1), url=f"https://www.zhihu.com/question/9/answer/{offset+1}",
                                    author="测试作者", author_url="https://www.zhihu.com/people/example",
                                    created_at="2023-01-01T00:00:00Z", updated_at=None)],
                        total=2, has_more=offset == 0, next_cursor="1" if offset == 0 else None)
        return dict(url=arguments["url"], title="市场判断", author="测试作者",
                    author_url="https://www.zhihu.com/people/" + ("other" if self.mismatch else "example"),
                    content="<p>我直觉认为AI需求会推动相关公司的业务增长。</p>",
                    published_at="2023-01-01T00:00:00Z", updated_at="", offset=0,
                    truncated=False, next_offset=None)


class ZhiArchiveTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_pagination_and_detail_not_excerpt(self):
        gateway = Gateway()
        result = await collect_zhiarchive(gateway, "example", max_items=5, max_pages=3, kinds=["answer"])
        self.assertEqual(len(result["documents"]), 2)
        self.assertIn("直觉", result["documents"][0]["text"])
        self.assertEqual(result["documents"][0]["capture_method"], "zhiarchive-mcp")
        self.assertIsNone(result["documents"][0]["edited_at"])
        self.assertTrue(result["coverage"]["complete"])
        self.assertEqual(gateway.calls[2][1]["cursor"], "1")

    async def test_item_budget_is_not_full_history(self):
        result = await collect_zhiarchive(Gateway(), "example", max_items=1, kinds=["answer"])
        self.assertFalse(result["coverage"]["complete"])

    async def test_denial_stops_without_retry(self):
        gateway = Gateway(denied=True)
        with self.assertRaises(AccessBlocked):
            await collect_zhiarchive(gateway, "example", kinds=["answer"])
        self.assertEqual(len(gateway.calls), 1)

    async def test_wrong_author_cannot_be_assigned_to_target(self):
        with self.assertRaises(ValueError):
            await collect_zhiarchive(Gateway(mismatch=True), "example", kinds=["answer"])

    async def test_repeated_cursor_is_not_complete(self):
        class Repeat(Gateway):
            async def call(self, name, arguments):
                result = await super().call(name, arguments)
                if name == "list_zhihu_profile_items":
                    result.update(has_more=True, next_cursor="0")
                return result
        result = await collect_zhiarchive(Repeat(), "example", max_pages=3, kinds=["answer"])
        self.assertFalse(result["coverage"]["complete"])
        self.assertEqual(len(result["documents"]), 1)

    async def test_midway_denial_keeps_prior_documents(self):
        class Midway(Gateway):
            async def call(self, name, arguments):
                if name == "list_zhihu_profile_items" and arguments.get("cursor"):
                    raise AccessBlocked("blocked", "拒绝访问")
                return await super().call(name, arguments)
        with self.assertRaises(AccessBlocked) as cm:
            await collect_zhiarchive(Midway(), "example", kinds=["answer"])
        self.assertEqual(len(cm.exception.partial["documents"]), 1)
        self.assertFalse(cm.exception.partial["coverage"]["complete"])

    async def test_mcp_exception_group_preserves_denial_and_material(self):
        partial = {"documents": [{"text": "已取得正文"}]}
        class Grouped:
            async def __aenter__(self):
                raise ExceptionGroup("mcp shutdown", [AccessBlocked("blocked", "拒绝", partial)])
            async def __aexit__(self, *args):
                pass
        with patch("services.api.zhiarchive.ZhiArchiveGateway", return_value=Grouped()):
            with self.assertRaises(AccessBlocked) as cm:
                await configured_history("example")
        self.assertEqual(cm.exception.code, "blocked")
        self.assertEqual(cm.exception.partial, partial)

    async def test_no_remote_plaintext_token_endpoint(self):
        with self.assertRaises(ValueError):
            ZhiArchiveGateway("http://example.com/mcp/", "secret")

    async def test_body_pagination_is_assembled(self):
        class Split(Gateway):
            async def call(self, name, arguments):
                result = await super().call(name, arguments)
                if name == "read_zhihu_content":
                    if arguments["offset"] == 0:
                        result.update(content="<p>第一段正文。", truncated=True, next_offset=9)
                    else:
                        result.update(content="第二段正文。</p>", offset=9, truncated=False, next_offset=None)
                return result
        result = await collect_zhiarchive(Split(), "example", max_items=1, kinds=["answer"])
        self.assertIn("第一段正文。第二段正文。", result["documents"][0]["text"])

    async def test_list_excerpt_is_never_mistaken_for_full_body(self):
        class NoBody(Gateway):
            async def call(self, name, arguments):
                result = await super().call(name, arguments)
                if name == "list_zhihu_profile_items":
                    result["items"][0]["excerpt"] = "有摘要不代表取得正文。"
                else:
                    result["content"] = ""
                return result
        result = await collect_zhiarchive(NoBody(), "example", kinds=["answer"])
        self.assertEqual(result["documents"], [])
        self.assertFalse(result["coverage"]["complete"])
