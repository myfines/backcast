import unittest
from datetime import date, timedelta
from services.api.scorecard import build_scorecard, compare_forecasters, wilson_interval


def claim(id="c1", status="correct", **extra):
    result = dict(
        id=id,
        author_id="a",
        kind="prediction",
        domain="科技",
        event_key=id,
        published_at="2023-01-01",
        deadline="2024-01-01",
        outcome_at="2024-01-01",
        source_url="https://example.com/original",
        original_version_verified=True,
        evidence=[
            {
                "id": id + "e",
                "url": "https://example.org/data",
                "published_at": "2024-01-02",
                "verified": True,
            }
        ],
        verdict={"status": status, "citations": [id + "e"], "eligible": True},
    )
    result.update(extra)
    return result


class ScorecardTests(unittest.TestCase):
    def test_no_samples_no_invented_score(self):
        s = build_scorecard([])
        self.assertIsNone(s["categorical"]["accuracy"])
        self.assertIsNone(s["probabilistic"]["brier"])
        self.assertEqual(s["readiness"]["level"], "insufficient")

    def test_one_success_is_not_perfect_expert(self):
        s = build_scorecard([claim()])
        self.assertEqual(s["categorical"]["accuracy"], 1)
        self.assertLess(s["categorical"]["wilson_95"][0], 0.21)
        self.assertFalse(s["readiness"]["eligible_for_ranking"])

    def test_partial_is_not_full_success(self):
        s = build_scorecard([claim(), claim("c2", "partial")])
        self.assertEqual(s["categorical"]["accuracy"], 0.5)
        self.assertEqual(s["categorical"]["partial"], 1)

    def test_duplicate_event_does_not_inflate_sample(self):
        s = build_scorecard([claim(), claim("c2", event_key="c1")])
        self.assertEqual(s["coverage"]["independent_events"], 1)
        self.assertEqual(s["categorical"]["n"], 1)

    def test_first_prediction_selected_not_best_later_revision(self):
        s = build_scorecard(
            [
                claim("later", event_key="x", published_at="2023-02-01"),
                claim("first", "wrong", event_key="x"),
            ]
        )
        self.assertEqual(s["categorical"]["accuracy"], 0)

    def test_no_event_key_cannot_establish_independent_events(self):
        s = build_scorecard([claim(event_key=None)])
        self.assertEqual(s["coverage"]["independent_events"], 0)
        self.assertEqual(s["categorical"]["n"], 0)

    def test_unknown_version_never_scored_despite_stale_flag(self):
        s = build_scorecard([claim(original_version_verified=False)])
        self.assertEqual(s["categorical"]["n"], 0)

    def test_post_event_statement_not_a_prediction(self):
        s = build_scorecard([claim(published_at="2024-01-02", deadline="2024-12-31")])
        self.assertEqual(s["categorical"]["n"], 0)

    def test_as_of_excludes_future_outcome_and_evidence(self):
        self.assertEqual(build_scorecard([claim()], as_of="2023-12-01")["categorical"]["n"], 0)
        c = claim()
        c["evidence"][0]["published_at"] = "2030-01-01"
        self.assertEqual(build_scorecard([c], as_of="2026-11-16")["categorical"]["n"], 0)

    def test_fabricated_citation_never_scores(self):
        c = claim()
        c["verdict"]["citations"] = ["fake"]
        self.assertEqual(build_scorecard([c])["categorical"]["n"], 0)

    def test_explicit_probability_brier_and_neutral_baseline(self):
        c = claim(forecast_format="probabilistic", probability=0.8, binary_outcome=1)
        s = build_scorecard([c])
        self.assertAlmostEqual(s["probabilistic"]["brier"], 0.04)
        self.assertAlmostEqual(s["probabilistic"]["skill_vs_50pct"], 0.84)
        self.assertEqual(s["categorical"]["n"], 0)

    def test_no_probability_inference_from_language(self):
        c = claim(text="我非常确信会发生。")
        self.assertEqual(build_scorecard([c])["probabilistic"]["n"], 0)

    def test_invalid_probability_is_not_silently_clamped(self):
        for p in [-0.1, 1.1, float("nan"), True]:
            with self.subTest(p=p):
                self.assertEqual(
                    build_scorecard(
                        [claim(forecast_format="probabilistic", probability=p, binary_outcome=1)]
                    )["probabilistic"]["n"],
                    0,
                )

    def test_calibration_bins_are_actual_observations(self):
        s = build_scorecard(
            [
                claim(forecast_format="probabilistic", probability=0.8, binary_outcome=1),
                claim("c2", forecast_format="probabilistic", probability=0.8, binary_outcome=0),
            ]
        )
        b = next(b for b in s["probabilistic"]["calibration"] if b["n"])
        self.assertEqual(b["n"], 2)
        self.assertEqual(b["observed_frequency"], 0.5)

    def test_reprints_are_one_confirmed_origin(self):
        c = claim()
        c["evidence"] = [
            {
                "id": "e" + str(i),
                "url": f"https://news{i}.example/a",
                "published_at": "2024-01-02",
                "verified": True,
                "origin_url": "https://agency.example/release",
                "origin_confirmed": True,
                "source_type": "secondary",
            }
            for i in range(3)
        ]
        s = build_scorecard([c])
        self.assertEqual(s["evidence_quality"]["confirmed_origins"], 1)

    def test_unknown_origins_not_counted_independent(self):
        self.assertEqual(build_scorecard([claim()])["evidence_quality"]["confirmed_origins"], 0)

    def test_comparison_only_shared_questions(self):
        a = [
            claim(
                "one",
                event_key="shared",
                forecast_format="probabilistic",
                probability=0.8,
                binary_outcome=1,
            ),
            claim("extra"),
        ]
        b = [
            claim(
                "two",
                event_key="shared",
                forecast_format="probabilistic",
                probability=0.6,
                binary_outcome=1,
            )
        ]
        c = compare_forecasters({"a": a, "b": b}, domain="科技")
        self.assertEqual(c["paired_events"], 1)
        self.assertFalse(c["comparable"])
        self.assertEqual(c["authors"][0]["paired_brier"], 0.04)

    def test_conflicting_outcomes_excluded_from_comparison(self):
        a = claim(forecast_format="probabilistic", probability=0.8, binary_outcome=1)
        b = claim(
            "b", event_key="c1", forecast_format="probabilistic", probability=0.6, binary_outcome=0
        )
        c = compare_forecasters({"a": [a], "b": [b]}, domain="科技")
        self.assertEqual(c["paired_events"], 0)
        self.assertEqual(c["conflicting_events"], ["c1"])

    def test_missing_domain_refuses_ranking(self):
        self.assertFalse(compare_forecasters({"a": [claim()], "b": [claim()]})["comparable"])

    def test_wilson_empty(self):
        self.assertIsNone(wilson_interval(0, 0))

    def test_sampling_window_cannot_certify_other_dates(self):
        items = [
            claim(str(i), published_at=(date(2023, 1, 1) + timedelta(days=i * 10)).isoformat())
            for i in range(20)
        ]
        wrong = {
            "method": "complete_window",
            "complete": True,
            "domain": "科技",
            "start": "2019-01-01",
            "end": "2020-01-01",
        }
        self.assertFalse(
            build_scorecard(items, sampling_protocol=wrong)["readiness"]["eligible_for_ranking"]
        )

    def test_sampling_and_pending_reviews_control_ranking(self):
        items = [
            claim(str(i), published_at=(date(2023, 1, 1) + timedelta(days=i * 10)).isoformat())
            for i in range(20)
        ]
        protocol = {
            "method": "complete_window",
            "complete": True,
            "domain": "科技",
            "start": "2023-01-01",
            "end": "2023-12-31",
        }
        self.assertTrue(
            build_scorecard(items, sampling_protocol=protocol)["readiness"]["eligible_for_ranking"]
        )
        self.assertFalse(
            build_scorecard(items, sampling_protocol=protocol, pending_reviews=1)["readiness"][
                "eligible_for_ranking"
            ]
        )


if __name__ == "__main__":
    unittest.main()
