# Phase 5: APIs
Status: done   Date: 2026-09-23

## What was built
Two API endpoints wired on top of the existing layers: `GET /get_chunks` (browse the first 10 indexed chunks) and `POST /retrieve` (run any of the four Phase 4 retrieval mechanisms). No new backend layer — this phase is pure orchestration on top of `DataStore` and `Retrieval`.

## Files created / changed
- `backend/routes.py`:
  - `ChunkResult`, `RetrieveResult`, `RetrieveRequest` — Pydantic models for request/response shapes
  - `GET /get_chunks` — `store.search_data()` with `match_all` + sort by `hf_row_id` ascending, size 10
  - `POST /retrieve` — validates `{search_type, query, weight?}`, calls `retrieval_registry.retrieve()`, maps `ValueError` → `400` and `elastic_transport.ConnectionError` → `503`
- `docs/architecture.md`: added "API decisions" section.

## Key decisions and why
- **No new files/layer**: `routes.py` stays the single API file per `architecture.md`'s listing — this phase is glue code over already-built layers, not new business logic.
- **Roadmap's Phase 5 originally listed 4 APIs** (`/create_index`, `/chunk`, `/get_chunks`, `/retrieve`) but was edited down to 2, with "Done When" left saying "three apis" — read as a stale leftover from the edit (2 APIs, not 3), confirmed as the working assumption rather than blocking on it.
- **`search_type` uses `RetrievalRegistry`'s internal keys** (`bm25`, `semantic`, `hybrid_weighted`, `hybrid_rrf`), not the UI's display labels — Phase 6 maps labels to keys client-side, keeping the API contract stable regardless of UI wording changes.
- **Pydantic response models over raw dicts**: beyond auto-generated OpenAPI docs, `ChunkResult` (no `embedding` field) means FastAPI automatically strips the 512-float embedding vector from `/get_chunks` responses without any manual filtering code.
- **Scoped error handling** (`ValueError` → 400, ES `ConnectionError` → 503) rather than a blanket `except Exception` → 500: both failure modes are ones this project has genuinely hit during development, so they're handled deliberately; anything else stays an unhandled 500 (already logged by uvicorn) so real bugs aren't masked.

## How to run / test
- No pytest (standing instruction). Verified manually against the live, partially-ingested corpus (19,200+/40,221 rows at test time):
  - `GET /get_chunks` → 10 real chunks, sorted by `hf_row_id`, confirmed no `embedding` field in the response.
  - `POST /retrieve` with all four `search_type` values → all returned results; compared BM25 vs. semantic score distributions directly (BM25 in Lucene's ~13-15 range, semantic in cosine's ~0.87-0.90 range, with different rankings past the top result) to confirm the API is genuinely routing to distinct mechanisms, not returning cached/identical data.
  - Invalid `search_type` → confirmed `400` with a clear error message listing valid strategies.
  - Did **not** test the `503` path against the live container, to avoid interrupting the actively-running Phase 3 ingest — verified by code review instead.
- `mypy backend --strict` (12 source files) — clean.

## Known issues / tech debt
- `503` path (ES connection failure) verified by code review only, not a live test — low risk given the exact exception type was confirmed from real `ConnectionError` tracebacks earlier in development.
- Roadmap's Phase 5 "Done When" text says "three apis" while only two are listed — flagged, not corrected (not my file to silently rewrite).

## Notes for next phase
- Phase 6 (UI): dropdown labels (`Lexical(BM25)`, `Semantic`, `Hybrid(RRF)`, `Hybrid(Weighted)`) must map to `search_type` values `bm25`, `semantic`, `hybrid_rrf`, `hybrid_weighted` respectively when calling `/retrieve` from `client.ts`.
- `/retrieve`'s `weight` field is optional (defaults to `0.5` server-side) — only send it when `Hybrid(Weighted)` is selected, per `docs/UIDesign.md`.
- Response fields for the Retrieve page table are exactly `text`, `chunk_index`, `score` (plus `chunk_id`) — no client-side reshaping needed.
