import unittest
from services.api.rules import decide, validate_citations, statistics


class RulesTests(unittest.TestCase):
    def claim(self, **kwargs):
        return dict(
            kind="prediction",
            published_at="2020-01-01",
            deadline="2021-01-01",
            original_version_verified=True,
            **kwargs,
        )

    def test_future_is_pending_even_without_evidence(self):
        c = self.claim()
        c["deadline"] = "2099-01-01"
        self.assertEqual(decide(c, [], now="2026-11-16")["status"], "pending")

    def test_no_evidence_is_insufficient(self):
        self.assertEqual(decide(self.claim(), [])["status"], "insufficient")

    def test_opinion_is_unverifiable(self):
        c = self.claim()
        c["kind"] = "opinion"
        self.assertEqual(decide(c, [])["status"], "unverifiable")

    def test_unknown_original_cannot_score(self):
        c = self.claim()
        c["original_version_verified"] = False
        v = decide(c, [{"id": "e1", "verified": True}], {"status": "correct", "citations": ["e1"]})
        self.assertEqual(v["status"], "correct")
        self.assertFalse(v["eligible"])

    def test_fabricated_citation_rejected(self):
        with self.assertRaises(ValueError):
            validate_citations(["made-up"], [{"id": "real", "verified": True}])

    def test_citation_string_is_not_a_valid_list(self):
        with self.assertRaises(ValueError):
            validate_citations("e", [{"id": "e", "verified": True}])

    def test_unfetched_citation_rejected(self):
        with self.assertRaises(ValueError):
            validate_citations(["real"], [{"id": "real", "verified": False}])

    def test_missing_citation_cannot_decide(self):
        with self.assertRaises(ValueError):
            decide(
                self.claim(),
                [{"id": "real", "verified": True}],
                {"status": "correct", "citations": []},
            )

    def test_late_edit_excludes_score(self):
        c = self.claim(edited_at="2022-01-01")
        v = decide(c, [{"id": "e1", "verified": True}], {"status": "wrong", "citations": ["e1"]})
        self.assertFalse(v["eligible"])

    def test_deadline_cannot_hide_post_event_publication(self):
        c = self.claim(outcome_at="2019-12-31")
        v = decide(c, [{"id": "e", "verified": True}], {"status": "correct", "citations": ["e"]})
        self.assertFalse(v["eligible"])

    def test_unknown_deadline_no_invented_window(self):
        c = self.claim()
        c["deadline"] = None
        self.assertEqual(decide(c, [])["status"], "unverifiable")

    def test_future_evidence_not_usable_as_of_cutoff(self):
        with self.assertRaises(ValueError):
            decide(
                self.claim(),
                [{"id": "e", "verified": True, "published_at": "2030-01-01"}],
                {"status": "correct", "citations": ["e"]},
                now="2026-11-16",
            )

    def test_timezone_ordering(self):
        c = self.claim()
        c["published_at"] = "2021-01-01T01:00:00+08:00"
        c["deadline"] = "2020-12-31T18:00:00Z"
        v = decide(c, [{"id": "e", "verified": True}], {"status": "correct", "citations": ["e"]})
        self.assertTrue(v["eligible"])

    def test_partial_separate_and_empty_denominator(self):
        self.assertIsNone(statistics([{"status": "pending", "eligible": False}])["accuracy"])
        s = statistics(
            [{"status": "partial", "eligible": True}, {"status": "correct", "eligible": True}]
        )
        self.assertEqual(s["accuracy"], 50)
        self.assertEqual(s["partial"], 1)


if __name__ == "__main__":
    unittest.main()
