# Phase 7: Integrate LLM
Status: done   Date: 2026-09-23

## What was built
A local LLM query layer (`LLMQueryLayer`) running Ollama's `llama3.2:3b` in Docker: on a user query, it first retrieves context via the existing `RetrievalRegistry`, then asks the model to answer using only that context, returning `{"response": ..., "citations": [...]}`. Wired through a new `POST /query` API and a fully live Ask page (search box, generated answer, collapsible citations panel — the layout and component were already built in Phase 6, just not wired to real data until now).

## Files created / changed
- `docker-compose.yml`: added an `ollama` service (`ollama/ollama:latest`, port 11434, named volume `ollamadata`). You already had the image pulled locally.
- `backend/.env` / `.env.example`: added `OLLAMA_URL`, `LLM_MODEL=llama3.2:3b`.
- `backend/config.py`: added `ollama_url`, `llm_model` settings.
- `backend/requirements.txt`: added `ollama==0.6.2` (official Python client).
- `backend/LLM/__init__.py`, `backend/LLM/llm_query_layer.py`: `LLMQueryLayer.query(search_type, query_text, weight, size=5)` — retrieves top 5 chunks, builds a grounding prompt, calls Ollama, returns response + citations. Module-level `llm_query_layer` singleton.
- `backend/routes.py`: `POST /query`, reusing `RetrieveRequest`'s shape; new `QueryResponse` model; error mapping extended to cover Ollama's `ConnectionError` (503) alongside ES's.
- `frontend/.env` / `.env.example`: added `VITE_LLM_MODEL=llama3.2:3b`.
- `frontend/src/api/client.ts`: added `askQuery()` + `QueryResponse` type.
- `frontend/src/Pages/Ask/Ask.tsx` + `.css`: fully wired — loading state, generated answer, citations rendered inside the `CollapsiblePanel` built in Phase 6, LLM name pulled from `VITE_LLM_MODEL` for the subheading.
- `docs/architecture.md`: added `LLM/` to the folder diagram and an "LLM decisions" section.

## Key decisions and why
- **`llama3.2:3b`**: your choice, balancing CPU-only response speed against answer quality, from three options I presented.
- **Citations sourced from retrieval, not the LLM**: the query layer already knows exactly which chunks it fed into the prompt, so it cites those directly instead of asking the model to self-report — avoids relying on a small model's structured-output reliability for something that's simple to compute deterministically.
- **No strategy dropdown on the Ask page**: UI Design's Ask spec doesn't describe one (unlike Retrieve), so `search_type` defaults to `hybrid_rrf` server-side without a UI control — matches the spec literally.
- **Lazy failure for `LLMQueryLayer`**: doesn't check Ollama connectivity at import time (unlike `EmbeddingProvider`'s fail-fast dimension check), since Ollama might not be running yet when the backend starts and the other endpoints shouldn't be held hostage to that.
- **`VITE_LLM_MODEL` mirrors the backend config** rather than adding a new API — same reasoning as `VITE_API_BASE_URL` in Phase 0.

## How to run / test
- No pytest (standing instruction). Verified in stages:
  1. Ollama container started, model pulled (2.0GB), confirmed reachable via `docker exec med-rag-ollama ollama list`.
  2. Raw generation sanity check via `curl /api/generate` — cold start took ~119s (108s of that was one-time model load into memory), warm requests are much faster (~20s for 45 tokens).
  3. `LLMQueryLayer.query()` tested directly (throwaway script) against the live corpus with `hybrid_rrf` retrieval: produced a correctly-grounded answer (explicitly noted when the context didn't fully answer the question, rather than hallucinating) with exactly the 5 retrieved chunks as citations.
  4. `POST /query` tested via the Ask page in a real browser — confirmed the LLM subheading correctly shows `llama3.2:3b` from env, and confirmed (via backend logs) that submitting a query correctly triggers retrieval → embedding → generation in the right order. **The final rendered answer wasn't screenshotted in this run** — the request was still generating when CPU contention with the concurrently-running Phase 3 ingest made it far slower than the isolated tests above, and you explicitly said not to block on waiting for it. Given step 3 already proved the exact same code path produces a correct end-to-end result, and step 4 proved the API/UI wiring correctly invokes that path, this was accepted as sufficient verification.
- `mypy backend --strict` (14 source files) — clean.
- `npm run lint`, `npm run build` — clean.

## Known issues / tech debt
- CPU-only LLM generation is slow, more so when competing with the Phase 3 ingest for CPU — expected on this hardware, not a bug, but worth knowing before assuming a hung request is broken.
- Ask page's rendered-answer screenshot wasn't captured this run (see above) — functionally verified via the direct layer test and live request logs instead.
- No conversation history / follow-up questions — each `/query` call is a single independent turn.

## Notes for next phase
- Phase 8 (Evaluation) will likely want to call `LLMQueryLayer.query()` or `RetrievalRegistry.retrieve()` per test question, across multiple retrieval mechanisms, so it can compare them — both already return the exact shapes needed.
- The `evaluate_page`'s config modal (built in Phase 6) already collects `testDataSize` and `selectedMechanisms` in a shape that maps directly onto whatever `evaluate` API payload Phase 8 defines.
