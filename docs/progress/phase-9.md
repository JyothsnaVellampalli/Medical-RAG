# Phase 9: Run evaluation on querying in `ask` page
Status: done   Date: 2026-09-26

## What was built
`/query` now accepts an `evaluation: bool` field. When `true`, after retrieval + LLM generation complete, the route computes `faithfulness` and `answer_relevancy` (embedding-based, no LLM judge — reusing `Evaluation/semantic_metrics.py` from Phase 8) against the generated response and retrieved contexts, and returns them alongside `response`/`citations`. Only these two metrics are available here — ad-hoc Ask-page questions have no ground-truth answer or `relevant_passage_ids`, so the other three evaluation-page metrics (precision/recall/MRR/nDCG, answer_correctness) don't apply.

The Ask page UI gained a full-width, gradient-background config section (above the search box) with a retrieval-mechanism dropdown, a conditional weight slider (only for `hybrid_weighted`, mirroring `Retrieve.tsx`), and an evaluation checkbox. Submitting sends `{search_type, query, weight?, evaluation}` to `/query`; the response's evaluation (if present) renders in a second collapsible panel next to citations.

## Files created / changed
- `backend/routes.py`: `QueryRequest` (replaces bare `RetrieveRequest` for `/query`, adds `evaluation: bool = False`), `QueryEvaluation`, updated `QueryResponse` to include `evaluation: QueryEvaluation | None`. `/query` handler computes evaluation conditionally after generation, with full `[API]`-prefixed info logging of the request, outcome, and evaluation scores.
- `frontend/src/api/client.ts`: added `QueryRequest`, `QueryEvaluation` types; `QueryResponse` now includes `evaluation`; `askQuery()` signature updated to take `QueryRequest`.
- `frontend/src/Pages/Ask/Ask.tsx`: added mechanism `Dropdown`, conditional weight slider, evaluation checkbox, gradient config section; wired submit to the new payload shape; added a second `CollapsiblePanel` for evaluation results.
- `frontend/src/Pages/Ask/Ask.css`: new `.ask-page__config` (full-bleed gradient section using `--color-primary`/`--color-primary-hover`), `.ask-page__config-row`, `.ask-page__weight`, `.ask-page__eval-toggle`, `.ask-page__eval-list`.
- `docs/Architecture.md`: new "Ask-page (per-query) evaluation decisions — Phase 9" section.

## Key decisions and why
- **Evaluation logic added at the route level, not inside `LLMQueryLayer`**: keeps that layer single-responsibility (retrieval + generation only), matching how the Evaluate page's evaluation logic also lives outside the retrieval/LLM layers.
- **Only 2 of 5 metrics**: precision/recall/MRR/nDCG need `relevant_passage_ids`; answer_correctness needs a ground-truth answer. Neither exists for a free-form Ask-page question, so only faithfulness/answer_relevancy (which only need the query, response, and retrieved contexts) are computed.
- **`evaluation` defaults to `false` and is opt-in via checkbox**: it adds two extra embedding calls of latency, unnecessary for most queries.

## How to run / test
- No pytest (standing instruction). Verified via `mypy backend --strict` (clean, 19 files), `npm run lint` (clean), `npm run build` (clean).
- Direct backend verification: `POST /query` with `evaluation: true` against a running stack (Elasticsearch, Ollama, embedding model) — confirmed correct JSON shape (`response`, `citations`, `evaluation: {faithfulness, answer_relevancy}`) and full request-to-response logging in the backend log, twice, with different queries.
- Frontend: `mypy`-equivalent (`tsc -b`) and ESLint both clean; code directly mirrors `Retrieve.tsx`'s already-verified dropdown/weight-slider pattern. **Not verified visually in a browser this session** — no browser/Playwright tool was available. Recommend a quick manual look at the Ask page (mechanism dropdown, weight slider show/hide, evaluation checkbox, both collapsible panels) before considering this fully done.

## Known issues / tech debt
- Same as Phase 8: `resume_job()` still has no API route; Docker/WSL2 hangs under sustained load remain a recurring constraint of this machine.
- No automated visual/browser verification of the new Ask page UI this session (see above).

## Notes for next phase
- Phase 10 (Query Expansion) will add a `use_query_expansion` toggle to both `/query` and `/evaluate` — the Ask page's new gradient config section is a natural place to add that toggle alongside the existing mechanism dropdown/weight/evaluation controls.
