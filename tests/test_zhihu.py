import unittest
from services.api.zhihu import collect_history, normalize_target, normalize_document, AccessBlocked


class FakeTransport:
    def __init__(self, blocked=False, repeat=False):
        self.blocked = blocked
        self.repeat = repeat
        self.calls = []

    def call(self, op, target, offset=0, limit=10):
        self.calls.append((op, target, offset))
        if self.blocked:
            raise AccessBlocked("needs_login", "需要正常登录。")
        if op == "profile":
            return {"name": "测试答主", "url_token": target, "answer_count": 3, "articles_count": 0}
        if op == "articles":
            return {"data": [], "paging": {"is_end": True, "totals": 0}}
        if offset == 0 or self.repeat:
            return {
                "data": [
                    {
                        "id": "1",
                        "type": "answer",
                        "content": "<p>公开的技术判断正文。</p>",
                        "created_time": 1609459200,
                        "author": {"url_token": target},
                        "question": {"id": "9", "title": "技术问题"},
                    }
                ],
                "paging": {"is_end": False, "totals": 2},
            }
        return {
            "data": [
                {
                    "id": "2",
                    "type": "answer",
                    "content": "<p>第二段公开正文。</p>",
                    "created_time": 1640995200,
                    "author": {"url_token": target},
                    "question": {"id": "9", "title": "技术问题"},
                }
            ],
            "paging": {"is_end": True, "totals": 2},
        }


class ZhihuTests(unittest.TestCase):
    def test_target_parsing(self):
        self.assertEqual(
            normalize_target("https://www.zhihu.com/people/example/answers"), "example"
        )
        self.assertEqual(normalize_target("example"), "example")
        for value in [
            "https://evil.example/people/a",
            "../secret",
            "https://www.zhihu.com/question/1",
            "https://www.zhihu.com@evil.example/people/a",
        ]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_target(value)

    def test_pagination_and_actual_dates(self):
        result = collect_history(FakeTransport(), "example", max_items=5, max_pages=3)
        self.assertEqual(len(result["documents"]), 2)
        self.assertEqual(result["documents"][0]["published_at"], "2021-01-01T00:00:00+00:00")
        self.assertIsNone(result["documents"][0]["edited_at"])
        self.assertTrue(result["coverage"]["reached_end"]["answer"])

    def test_budget_is_not_full_history(self):
        r = collect_history(FakeTransport(), "example", max_items=1, max_pages=1, kinds=["answer"])
        self.assertFalse(r["coverage"]["complete"])
        self.assertEqual(len(r["documents"]), 1)

    def test_repeated_page_stops_and_does_not_inflate(self):
        t = FakeTransport(repeat=True)
        r = collect_history(t, "example", max_items=5, max_pages=3, kinds=["answer"])
        self.assertEqual(len(r["documents"]), 1)
        self.assertFalse(r["coverage"]["complete"])
        self.assertLessEqual(len(t.calls), 3)

    def test_access_denial_stops_without_retry(self):
        t = FakeTransport(blocked=True)
        with self.assertRaises(AccessBlocked):
            collect_history(t, "example")
        self.assertEqual(len(t.calls), 1)

    def test_wrong_author_rejected(self):
        with self.assertRaises(ValueError):
            normalize_document(
                {"id": 1, "author": {"url_token": "other"}, "content": "原文"}, "answer", "example"
            )

    def test_midway_block_preserves_collected_material(self):
        class Midway(FakeTransport):
            def call(self, op, target, offset=0, limit=10):
                if op == "answers" and offset:
                    raise AccessBlocked("blocked", "访问被拒绝。")
                return super().call(op, target, offset, limit)

        with self.assertRaises(AccessBlocked) as caught:
            collect_history(Midway(), "example", max_items=5, kinds=["answer"])
        self.assertEqual(len(caught.exception.partial["documents"]), 1)
        self.assertFalse(caught.exception.partial["coverage"]["complete"])

    def test_html_is_text_not_executable(self):
        d = normalize_document(
            {"id": 1, "content": "<p>真实原文</p><script>fake()</script>", "question": {"id": 9}},
            "answer",
            "example",
        )
        self.assertNotIn("fake", d["text"])
        self.assertIn("真实原文", d["text"])


if __name__ == "__main__":
    unittest.main()
