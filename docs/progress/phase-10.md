# Phase 10: Integrate OpenRouter
Status: done   Date: 2026-10-02

## What was built
OpenRouter is now a second, opt-in generation and evaluation provider alongside the existing Ollama/embedding-based setup — nothing existing was removed. The Ask page gained a provider dropdown (Local/Ollama, default; OpenRouter) that controls which backend generates the answer. When evaluation is enabled, the background evaluation thread now runs **two independent metric computations**: the existing embedding-based `faithfulness`/`answer_relevancy` (unchanged from Phase 9), and new LLM-judge scores from OpenRouter's `typesafe/jev-1.13` **decisions model**, prompted with structured "score" questions on a 5-level scale (normalized to 0.0-1.0). Both render in the Ask page's Evaluation panel as separate sub-sections, each with its own Progress/Done/Error state.

**Mid-phase correction**: initially built against `typesafe/jev-router` (a chat-completions-compatible model-routing tool), per the roadmap's naming. After real use surfaced it wasn't actually free (routes to paid models) and was unreliable at $0 account credit, you switched to `typesafe/jev-1.13` — TypeSafe's actual purpose-built decisions model. That model uses a completely different OpenRouter endpoint (`/api/alpha/decisions`, not `/chat/completions`) with a structured request/response schema, discovered by reading OpenRouter's docs and verified live before wiring it in. The judge module was rewritten around it; everything else (generation provider, embedding metrics, UI) was unaffected.

## Files created / changed
- `backend/config.py`: added `open_router_url`, `open_router_generation_model`, `open_router_judge_model` (now `typesafe/jev-1.13`), `open_router_decisions_url` (the existing `open_router_api_key` field is now actually used).
- `backend/.env` / `.env.example`: added the four new OpenRouter settings.
- `backend/requirements.txt`: `httpx` promoted from transitive to an explicit direct dependency.
- `backend/openrouter_client.py` (new, top-level alongside `config.py`): shared `chat_completion()` (for ordinary chat models) and `decision()` (for the decisions API) helpers, plus `OpenRouterError`.
- `backend/LLM/generation_registry.py` (new): `GenerationRegistry` — `ollama_generate()`/`openrouter_generate()`, dispatched via `generate(provider, prompt, system)`, mirroring `RetrievalRegistry`'s exact pattern.
- `backend/LLM/llm_query_layer.py`: no longer owns an `ollama.Client` directly; delegates to `generation_registry`, gained a `provider` parameter.
- `backend/Evaluation/llm_judge_metrics.py` (new, rewritten mid-phase): `judge_metrics()` — calls the decisions API with 5-level "score" questions for faithfulness/answer_relevancy, normalizes to 0.0-1.0.
- `backend/Evaluation/query_evaluation_store.py`: `QueryEvaluationRecord` gained an independent `judge_state`/`judge_faithfulness`/`judge_answer_relevancy`/`judge_error` set of fields, plus `set_judge_done()`/`set_judge_error()`.
- `backend/routes.py`: `QueryRequest.provider`; `QueryEvaluationStatus` judge fields; `/query` passes `provider` through and maps `httpx.HTTPError`/`OpenRouterError` to 503; the background evaluation function now also calls `judge_metrics()` independently of the embedding metrics.
- `frontend/src/api/client.ts`: `GenerationProvider` type; `QueryRequest.provider`; `QueryEvaluationStatus` judge fields.
- `frontend/src/Pages/Ask/Ask.tsx`: provider dropdown; new `EvalSection` component rendering two independent metric sub-sections; refresh button moved to a shared header (one fetch refreshes both).
- `frontend/src/Pages/Ask/Ask.css`: styles for the new eval sub-sections; (also: removed the gradient background from the config section per your separate feedback, now plain page background).
- `docs/Architecture.md`: new "OpenRouter integration decisions — Phase 10" section.

## Key decisions and why
- **Verified model IDs and API shapes live, twice, before building against them** — the roadmap's `nvidia/nemotron-3-ultra:free` doesn't exist as written, but `nvidia/nemotron-3-ultra-550b-a55b:free` does (full slug) and works. `typesafe/jev-router` turned out to be a model-*routing* tool (routes to an underlying chat model), not a purpose-built judge; after switching to `typesafe/jev-1.13`, discovered via direct API testing that it's a different OpenRouter product (the decisions API, not chat completions) and built the integration around its real schema rather than guessing.
- **Additive only**: Ollama is still the default provider everywhere; OpenRouter is purely opt-in via the new dropdown. The embedding-based evaluation metrics are untouched; judge metrics are a second, independent set alongside them, confirmed by your explicit "add alongside, don't replace" instruction.
- **Generation provider abstraction mirrors `RetrievalRegistry`'s established pattern** exactly, per CLAUDE.md's own SOLID example — adding a third provider later means one method + one registry-dict line.
- **Two independent state machines for Ask-page evaluation** (`state`/`judge_state`), not one combined flag — the embedding metrics and judge metrics are computed by separate calls that can succeed or fail independently; confirmed in real testing (embedding metrics succeeded while the judge call failed on account credit, before the `jev-1.13` switch).
- **Shared `openrouter_client.py`** with two helpers (`chat_completion()`, `decision()`) instead of duplicating OpenRouter auth/error-handling in each caller.
- **OpenRouter's "HTTP 200 with an error object in the body" failure mode** (observed live on `/chat/completions`: a transient "Service temporarily overloaded" from Nvidia came back as status 200) is checked explicitly in both client helpers and raised as `OpenRouterError` — `raise_for_status()` alone would have silently let a `KeyError` crash the request, which is exactly what happened on the first real generation test before this fix.
- **Scoped to the Ask page only**, not the Evaluate (benchmark) page — the roadmap's Done-When criteria only mention the Ask page; the benchmark page's existing Ollama-only generation and embedding-only metrics are untouched.

## How to run / test
- No pytest (standing instruction). `mypy backend --strict` (23 files) clean; `npm run lint`/`npm run build` clean.
- Live-verified against the real OpenRouter API (not mocked):
  - Generation: a real `/query` call with `provider: "openrouter"` returned a correct answer + 5 citations in 30.4s (vs. Ollama's typical 60s–several-minutes on this machine).
  - Ollama regression: re-ran the same kind of query with `provider: "ollama"` after the refactor — confirmed identical behavior through the new `generation_registry` wrapper (took ~35 min end-to-end under this session's heavy concurrent load, consistent with this machine's known constraints, not a regression).
  - Evaluation (final, working state): a real evaluated query returned `state: "Done"` with embedding-based scores (`faithfulness=0.866`, `answer_relevancy=0.765`) **and** `judge_state: "Done"` with real decisions-API scores (`judge_faithfulness=0.7875`, `judge_answer_relevancy=0.935`) — both metric sets populated correctly end-to-end through the real `/query` → background thread → `/get_query_evaluation` flow, confirmed via backend logs.
- **Frontend not verified visually in a browser this session** — no browser tool available. Lint/build are clean and the code mirrors already-verified patterns (`Dropdown` usage, `CollapsiblePanel`), but a manual look at the Ask page's new provider dropdown and two-section Evaluation panel is recommended.

## Known issues / tech debt
- `jev-1.13` costs a small real amount per call (~$0.0000226, observed) — not literally free despite living under a mostly-free-tier provider. Negligible for testing/validation volume (your own call), but worth knowing if usage ever scales up.
- Same as prior phases: `resume_job()` still has no API route; Docker/WSL2 under sustained load remains a recurring constraint of this machine.
- No automated visual/browser verification of the new Ask page UI this session.

## Notes for next phase
- Phase 11 (Query Expansion) will add a `use_query_expansion` toggle to `/query` and `/evaluate` — the Ask page's config section now has three controls (mechanism, provider, evaluation); a fourth (query expansion) fits the same row.
- If you want OpenRouter extended to the Evaluate (benchmark) page too, that was explicitly out of scope here per the roadmap's literal Done-When wording — flag it and I'll scope that as its own piece of work.
