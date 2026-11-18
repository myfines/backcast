import tempfile
import unittest
from pathlib import Path

from services.api.edge_collector import collect_dom_history, normalize_snapshot, Checkpoint
from services.api.zhihu import AccessBlocked


def snapshot(id="1"):
    return dict(url=f"https://www.zhihu.com/question/9/answer/{id}", title="市场判断",
                author_url="https://www.zhihu.com/people/example", author_name="示例作者",
                text="订单持续增长，因此我倾向于看好未来的收入。", folded=False,
                published_at="2023-01-01T01:00:00Z", edited_at=None)


class Reader:
    def __init__(self, blocked_at=None):
        self.reads = []
        self.blocked_at = blocked_at

    def open_profile(self, target, kind):
        return dict(name="示例作者", url_token=target)

    def list_items(self):
        return [dict(url=snapshot(str(i))["url"]) for i in (1, 2)]

    def read(self, url, kind):
        self.reads.append(url)
        if len(self.reads) == self.blocked_at:
            raise AccessBlocked("blocked", "访问被拒绝")
        return snapshot(url.rsplit("/", 1)[1])

    def more(self):
        return "end"


class EdgeCollectorTests(unittest.TestCase):
    def test_normalizes_real_dom_dates_without_inventing_edit_time(self):
        doc = normalize_snapshot(snapshot(), "answer", "example")
        self.assertEqual(doc["published_at"], "2023-01-01T01:00:00+00:00")
        self.assertIsNone(doc["edited_at"])
        self.assertEqual(doc["capture_method"], "edge-visible-dom")

    def test_folded_excerpt_is_not_full_text(self):
        with self.assertRaises(ValueError):
            normalize_snapshot({**snapshot(), "folded": True}, "answer", "example")

    def test_author_mismatch_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize_snapshot({**snapshot(), "author_url": "https://www.zhihu.com/people/other"}, "answer", "example")

    def test_current_capture_does_not_prove_original_version(self):
        self.assertFalse(normalize_snapshot(snapshot(), "answer", "example")["original_version_verified"])

    def test_collects_then_resumes_without_redownloading(self):
        with tempfile.TemporaryDirectory() as directory:
            cp = Checkpoint(Path(directory) / "checkpoint.json", "example", ["answer"])
            first = collect_dom_history(Reader(), "example", 5, 2, ["answer"], cp)
            self.assertEqual(len(first["documents"]), 2)
            reader = Reader()
            second = collect_dom_history(reader, "example", 5, 2, ["answer"], cp)
            self.assertEqual(reader.reads, [])
            self.assertEqual(second["coverage"]["cached"], 2)
            self.assertEqual(first["documents"][0]["captured_at"], second["documents"][0]["captured_at"])

    def test_denial_preserves_checkpoint_and_partial_material(self):
        with tempfile.TemporaryDirectory() as directory:
            cp = Checkpoint(Path(directory) / "checkpoint.json", "example", ["answer"])
            reader = Reader(blocked_at=2)
            with self.assertRaises(AccessBlocked) as cm:
                collect_dom_history(reader, "example", 5, 2, ["answer"], cp)
            self.assertEqual(len(cm.exception.partial["documents"]), 1)
            self.assertEqual(len(cp.load()), 1)
            self.assertEqual(len(reader.reads), 2)

    def test_limit_does_not_claim_full_history(self):
        result = collect_dom_history(Reader(), "example", 1, 1, ["answer"])
        self.assertEqual(len(result["documents"]), 1)
        self.assertFalse(result["coverage"]["complete"])

    def test_stalled_loading_does_not_mean_end(self):
        class Stalled(Reader):
            def more(self):
                return "stalled"
        result = collect_dom_history(Stalled(), "example", 5, 2, ["answer"])
        self.assertFalse(result["coverage"]["complete"])
        self.assertTrue(result["coverage"]["warnings"])

    def test_checkpoint_cannot_be_reused_for_other_author(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            Checkpoint(path, "example", ["answer"]).save([normalize_snapshot(snapshot(), "answer", "example")])
            with self.assertRaises(ValueError):
                Checkpoint(path, "other", ["answer"]).load()
