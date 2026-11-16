# Open-source attribution

## Research and workflow inspiration

- [wzj998/fluencer-predict-track](https://github.com/wzj998/fluencer-predict-track), MIT. Consulted README and core SKILL.md at tree `67195680fb4f25f1f24263ce63f2bf70dc456f41`. Inspired prediction extraction, edit-time checks, external evidence and exclusion of unresolved predictions. No source code copied into this implementation.
- [multimodal-ai-lab/DEFAME](https://github.com/multimodal-ai-lab/DEFAME), Apache-2.0. Consulted README for staged fact-checking and retrieval interfaces. No code copied.
- [assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher), Apache-2.0. Consulted README for retrieval planning and cited research. No code copied.
- [deepset-ai/haystack](https://github.com/deepset-ai/haystack), Apache-2.0. Architecture reference only, not a runtime dependency.

## Additional backend methodology references (2026-11-16)

- [Metaculus/metaculus](https://github.com/Metaculus/metaculus), BSD-2-Clause. Inspected current logarithmic baseline scoring; no code copied and no claim of score compatibility.
- [Metaculus/forecasting-tools](https://github.com/Metaculus/forecasting-tools), MIT. Inspected probability validation and BinaryReport log/baseline scoring; no code copied.
- [forecastingresearch/forecastbench](https://github.com/forecastingresearch/forecastbench), MIT. Adapted the evaluation principle of controlling question sets through matched-event comparisons; did not port its difficulty-adjustment code.
- [ericrisco/rsc-harness](https://github.com/ericrisco/rsc-harness), MIT. Adapted provenance / lateral-reading / shared-origin principles from its credibility rubric. Full upstream notice: `third_party/rsc-harness.LICENSE`.
- [edisonymy/forecast-scaffold](https://github.com/edisonymy/forecast-scaffold), inspected current PolyForm Noncommercial 1.0.0 license. Considered but **not copied or used as a dependency**. Brier/Wilson formulae in our implementation are standard independently implemented mathematics.
- [openapi-typescript](https://github.com/openapi-ts/openapi-typescript), MIT, development-only schema generator. The checked-in API type definitions were generated from our own OpenAPI schema.

Detailed methods, limits and attribution are recorded in `docs/OPEN_SOURCE_RESEARCH.md`.

## Runtime dependency notices

Next.js (MIT), React (MIT), Tailwind CSS (MIT), Apache ECharts (Apache-2.0), Lucide (ISC), FastAPI (MIT), Uvicorn (BSD-3-Clause), HTTPX (BSD-3-Clause), Trafilatura (Apache-2.0), python-dotenv (BSD-3-Clause), Playwright (Apache-2.0, development).

Upstream license files are distributed with installed packages. Dependency versions are pinned by the npm lockfile and requirements.txt.

## Editorial case sources

All case summaries are original paraphrases, attributed with direct URLs in `services/api/seed.py` and the evidence interface. They are not full article reproductions, archive attestations, or verified Zhihu account histories. Source publishers retain rights to their materials. The IEA report states CC BY 4.0. No person or organization endorses this application.
