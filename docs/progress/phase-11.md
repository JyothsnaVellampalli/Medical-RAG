# Phase 11: Add Jev as Reranker
Status: done   Date: 2026-10-02

## What was built
A new reranking layer that reorders retrieved chunks by relevance before they're fed to the LLM, using the same `typesafe/jev-1.13` decisions model (and `openrouter_client.decision()` helper) Phase 10 built for judging. The Ask page gained a "Rerank with Jev" checkbox alongside the existing provider and evaluation controls; when checked, `/query`'s `rerank: true` flag triggers one decisions-API call that scores every retrieved chunk's relevance to the question in a single request, then reorders them before the prompt is built. Citations in the response reflect the reranked order, same as the existing "citations are exactly what was fed to the LLM" invariant from Phase 7.

## Files created / changed
- `backend/Reranker/reranker.py` (new) + `__init__.py`: `Reranker.rerank(query_text, chunks)` — one decisions call with one "score" question per chunk (5-level relevance scale, normalized to 0.0-1.0), sorts chunks descending by score.
- `backend/LLM/llm_query_layer.py`: `query()` gained a `rerank: bool = False` parameter; reranks the retrieved chunks (if enabled) before building the prompt, so both the prompt context and the returned citations reflect the new order.
- `backend/routes.py`: `QueryRequest.rerank: bool = False`, passed through to `llm_query_layer.query()`; no new error handling needed since rerank failures raise the same `httpx.HTTPError`/`OpenRouterError` the existing OpenRouter → 503 mapping already catches.
- `frontend/src/api/client.ts`: `QueryRequest.rerank: boolean`.
- `frontend/src/Pages/Ask/Ask.tsx`: "Rerank with Jev" checkbox, included in the submit payload.
- `docs/Architecture.md`: new "Reranker decisions — Phase 11" section.

## Key decisions and why
- **One decisions-API call scores all chunks at once**, not one call per chunk — the decisions API supports multiple named questions per request (already proven in Phase 10's dual faithfulness/relevancy judge questions), so N chunks cost one round-trip instead of N.
- **Reuses the exact same model/helper as judging** (`typesafe/jev-1.13` via `openrouter_client.decision()`) rather than a separate reranking model or a new client — consistent with the project's registry/reuse patterns, and the roadmap explicitly asked for the same model.
- **Rerank failures propagate to 503, no silent fallback** — consistent with how generation/judge failures are already handled; you can change this to a silent-fallback-to-unreranked-order if preferred, but wasn't asked for.
- **Independent of generation provider** — rerank always goes through OpenRouter regardless of whether Ollama or OpenRouter generates the final answer.
- **Scoped to the Ask page only**, matching Phase 10's precedent.
- Interpreted the roadmap's "`/ask` api" as the existing `/query` endpoint (same looseness as earlier phases' imprecise endpoint naming, e.g. Phase 5's "three apis").

## How to run / test
- No pytest (standing instruction). `mypy backend --strict` (25 files) clean; `npm run lint`/`npm run build` clean.
- Live-verified against the real OpenRouter decisions API (not mocked):
  - Standalone: a 3-chunk mixed-relevance test correctly ranked the genuinely relevant passage first (score 4.0/4) and an irrelevant one last (0.0/4).
  - Full `/query` flow: compared citation order for the same real question with `rerank: false` vs `rerank: true` — order visibly changed (5 real chunks reordered, not a no-op), confirmed via backend logs showing distinct, well-separated relevance scores (`[3.28, 2.59, 2.56, 2.54, 1.05]`).
- **Frontend not verified visually in a browser this session** — no browser tool available; lint/build clean and the checkbox mirrors the already-verified evaluation checkbox pattern.

## Known issues / tech debt
- Rerank adds one additional OpenRouter round-trip (~1s observed) on top of retrieval + generation — acceptable given the decisions API's speed, but worth knowing if query latency becomes a concern.
- Same as prior phases: `resume_job()` still has no API route; Docker/WSL2 under sustained load remains a recurring constraint of this machine; `jev-1.13` costs a small real amount per call (~$0.00002, observed), same as the judge usage.
- No automated visual/browser verification of the new Ask page UI this session.

## Notes for next phase
- Phase 12 (Query Expansion) will add a `use_query_expansion` toggle to `/query` and `/evaluate` — the Ask page's config section now has four controls (mechanism, provider, evaluation, rerank); a fifth fits the same row.
