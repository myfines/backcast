# Backcast team contract

## Goal
Current product: find differing public viewpoints, build source-grounded author avatars, and let a user discuss with an avatar plus an optional fictional AI panel. Read docs/ROOM_HANDOFF.md first. Older forecasting and expert-score routes are legacy. Do not invent author identities, opinions, citations, scores, or sample sizes.

## Ownership
- Backend: `services/`, `tests/`, `docs/openapi.json`, `scripts/export_contract.py`.
- Frontend teammate (Claude): `apps/web/`. The current UI is a prototype, replace it freely.
- Integration boundary: `/api/v1`, `docs/FRONTEND_HANDOFF.md`, `packages/api-client/`.
- Coordinate contract changes through an updated OpenAPI snapshot and tests. Do not quietly rename server fields to match a component.

## Commands
- Backend only: `python -m pip install -r requirements.txt`, then `python -m uvicorn services.api.main:app --reload --port 8000`.
- Tests: `python -m unittest discover -s tests`.
- Contracts: `python scripts/export_contract.py`.
- UI: `npm --prefix apps/web ci`, `npm --prefix apps/web run dev`.
- E2E: `npm --prefix apps/web run test:e2e`. Starts its own 3001/8001 servers and test database.

## Data rules
- v1 accuracy is a ratio in [0,1], not a percentage. null means unavailable; never display null as 0%.
- Categorical hit rate and probabilistic Brier/calibration are separate. Do not infer a probability from tone.
- Do not turn `readiness.level` into a personal-integrity badge. Honor `eligible_for_ranking` and its warnings.
- Different domains and question sets cannot be directly ranked. Comparison returns common events only.
- Built-in examples are attributed editorial summaries, not verified Zhihu histories.
- No access-control bypass or fabricated citations. Unknown historical versions cannot score.
- Preserve source text and audits. Manual resolution requires backend REVIEW_API_TOKEN; never put it in NEXT_PUBLIC variables.

## Scope and safety
- Never commit .env files, credentials, SQLite files, tool caches, or machine-generated logs.
- Keep tests deterministic; no paid APIs in CI. Use mocks at provider boundaries only.
- Pin the frontend to the exported API contract, use relative `/api/v1` through the Next rewrite or explicitly configure a backend origin.
- For large tool output use the installed headroom workflow, keep errors and first 3/last 2, and store reversible caches outside tracked source.
