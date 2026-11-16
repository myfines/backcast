# How we assess a forecaster's track record

Research date: 2026-11-16. This implementation distinguishes forecasting performance, evidence quality and data coverage. It does **not** assign moral integrity, general expertise, or social popularity a numeric score.

## Sources inspected

| Project / source | License checked | What it actually does | Backcast adaptation |
| --- | --- | --- | --- |
| [Metaculus](https://github.com/Metaculus/metaculus), [`scoring/score_math.py`](https://github.com/Metaculus/metaculus/blob/main/scoring/score_math.py) | BSD-2-Clause, copyright 2024 Metaculus | Current baseline scoring code includes logarithmic relative scores and time-dependent forecast processing. It is **not simply a Brier leaderboard**. | Keep scoring reproducible, respect chronology and version changes. We do not claim to reproduce Metaculus scores. |
| [Metaculus forecasting-tools](https://github.com/Metaculus/forecasting-tools), [`binary_report.py`](https://github.com/Metaculus/forecasting-tools/blob/main/forecasting_tools/data_models/binary_report.py) | MIT | Validates probabilities; its inspected BinaryReport uses expected baseline / log scoring against community predictions. | Explicit probability validation. We do not use an absent community probability as a fabricated baseline. |
| [ForecastBench](https://github.com/forecastingresearch/forecastbench), [leaderboard methodology](https://www.forecastbench.org/leaderboards/) | MIT | Forecast evaluation with difficulty adjustment to address different question sets. | MVP compares the intersection of manually matched events. No claim of implementing its fixed-effects difficulty adjustment. |
| [rsc-harness credibility rubric](https://github.com/ericrisco/rsc-harness/blob/main/skills/research-ops/references/credibility-rubric.md) | MIT, copyright 2026 Eric Risco | SIFT, lateral reading, provenance and independent corroboration. Several articles quoting the same upstream press release are one origin. | Explicit `origin_url`, `origin_confirmed`, `source_type`; no automatic independence claim based on distinct domains. Method adaptation; upstream MIT notice included in `third_party/`. |
| [fluencer-predict-track](https://github.com/wzj998/fluencer-predict-track) | MIT | Extracts historical predictions; checks last edit time, external evidence and unresolved samples. | Existing extraction / chronology / evidence pipeline, extended to scored author records. |
| [forecast-scaffold](https://github.com/edisonymy/forecast-scaffold), `core.py` and `LICENSE` | PolyForm Noncommercial 1.0.0 at inspection time | Brier and calibration over a forecast journal. Its repository metadata alone does not identify a permissive license. | Inspected for comparison; **not vendored, copied, or depended upon**, so the public MIT codebase does not inherit a noncommercial restriction. |

## Implemented metrics

1. **Exact categorical success.** Correct / (correct + wrong + partial), with partial counts separate. A 95% Wilson interval makes single-hit records visibly uncertain. This is a descriptive exact-success metric, not an expert certification.
2. **Brier for explicit probabilities.** Mean `(p - outcome)^2`, with lower values better. A probability must be expressed in the original text as a percentage and confirmed by a reviewer. We do not convert “certain”, “likely” or a categorical statement into a guessed probability.
3. **Neutral baseline.** `skill_vs_50pct = 1 - Brier / 0.25`. This is only a constant-50% reference, not a base rate, market forecast or difficulty-adjusted skill estimate. Negative skill is allowed.
4. **Calibration.** Five bins with actual counts, mean probabilities and observed frequencies. Small-N bins are shown as observations, accompanied by a warning, not a stable ability estimate.
5. **Coverage.** Unique event keys, time span, active months, duplicate records and confirmed collection protocol. Records from one author are deduplicated by event, taking the earliest statement rather than the best later revision.
6. **Traceability.** Dated documents, verified original-version proportion, explicitly confirmed origins, and confirmed primary sources. Unknown is not promoted to trustworthy.

## Eligibility

The scorecard recomputes every gate from claim data; a stale `verdict.eligible=true` cannot bypass them. Predictions require a deadline, publication before the event and deadline, an original version confirmed with an earlier snapshot, valid fetched citations, and dated evidence available by `as_of`. Retrospective factual claims do not count as forecasts. Facts and opinions remain in the archive.

The default display policy requires at least 20 scored events, a 180-day span and 3 active publication months before marking sample volume sufficient. Ranking additionally requires a reviewer-confirmed complete collection window and no pending corrections. These are **MVP product thresholds, not statistically established expert-selection standards**. The policy is returned by the API.

Comparison requires an explicit domain, at least 10 shared probabilistic events with matching outcomes/deadlines, and each participant's coverage eligibility. Conflicting outcomes are excluded and disclosed. Shared events help with question-set selection, but do not establish that remaining events are statistically independent or fully difficulty-matched.

## Human review and audit

Reviewers may annotate original snapshot URLs/times, explicit probabilities, outcome times, evidence provenance and event identity. These are recorded as **reviewer assertions**, not automatically authenticated archives. Review endpoints require a backend-only token. Before/after objects and reviewer names are append-only audit records. Original imported source text remains unchanged.

`as_of` creates an outcome/evidence-limited view using current records; it is not a time-travel replay of the old database, old reviews or old page versions. Limitations travel with the scorecard.

## Deliberately absent

No universal “trustworthiness 87/100”, no reputation-from-followers, no inferred probability, no cross-domain leaderboard, and no claim that one wrong prediction proves incompetence or dishonesty.
