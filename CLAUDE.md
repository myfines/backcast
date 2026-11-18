# Frontend handoff

Read `AGENTS.md` and `docs/ROOM_HANDOFF.md` first. The product has pivoted to author-avatar discussions; the older frontend handoff describes legacy functionality.
Your main workspace is `apps/web/`; the backend owner maintains `services/`.
Use `/api/v1` and `docs/openapi.json` as the source of truth.
The first frontend is disposable. Build: state a viewpoint → pick an author avatar → discuss → invite a fictional AI panel → inspect source quotes.
Do not generate fake scores, records or credentials to make a card look complete.
Do not edit scoring rules to fit the UI. Ask for an API change with an example request/response instead.
