# Phase 1: Data store layer
Status: done   Date: 2026-09-22

## What was built
A thin Elasticsearch wrapper (`ElasticSearchStore`) that owns the ES connection, the index mapping, and three generic operations: create the index, bulk-index documents, and run a search query. It intentionally does not know about BM25/semantic/hybrid query construction — that's Phase 4's `RetrievalRegistry` job. This keeps the layering clean: Phase 4 builds a query dict, `search_data()` just executes it against the configured index and hands back the raw ES response.

## Files created / changed
- `backend/DataStore/__init__.py`: empty, makes `DataStore` an importable package.
- `backend/DataStore/elastic_search_store.py`:
  - `INDEX_MAPPING`: `chunk_id` (keyword), `hf_row_id` (long — confirmed int64 from the HF dataset), `text` (text, for BM25), `embedding` (`dense_vector`, `dims=settings.embedding_dim`, `similarity="cosine"`, for Phase 4's semantic search), `chunk_index` (integer).
  - `ElasticSearchStore.create_index()`: idempotent — checks `indices.exists` first, logs and no-ops if already there.
  - `ElasticSearchStore.index_data(documents)`: bulk-indexes via `elasticsearch.helpers.bulk`, using each doc's `chunk_id` as the ES `_id` (so re-runs upsert instead of duplicating).
  - `ElasticSearchStore.search_data(query, size=10)`: passes `query` through as kwargs to `es.search()` (e.g. `{"query": {...}}` → `search(query={...})`), returns the raw response dict.
  - Module-level `store = ElasticSearchStore()` singleton, same pattern as `config.py`'s `settings`.
- `backend/requirements.txt`: added `elasticsearch==8.15.1` (pinned to match the 8.15.3 server in `docker-compose.yml` — the unpinned install resolved to a v9 client, which sends incompatible version headers to an 8.x server, so pinned explicitly).

## Key decisions and why
- **`search_data` takes a raw query dict, not a method per search type**: keeps `DataStore` a generic executor. Adding a new retrieval mechanism in Phase 4 means adding a method to `RetrievalRegistry` that builds a query dict — `DataStore` doesn't change, matching the SOLID/registry pattern CLAUDE.md calls out.
- **`chunk_id` used as the ES document `_id`**: makes `index_data` naturally idempotent (re-indexing the same chunk overwrites rather than duplicates), which Phase 3's re-runnable ingestion will depend on.
- **Elasticsearch client pinned to 8.15.1**: must track the server's major.minor version — an unpinned `pip install elasticsearch` resolved to v9, which is not wire-compatible with the v8.15.3 server running in Docker.
- **`hf_row_id` typed `long`**: confirmed with the user that the Hugging Face dataset's row id is int64, not a string.

## How to run / test
- Elasticsearch: `docker compose up -d` (already running for this phase; verified `curl http://localhost:9200/_cluster/health` → `"status":"green"`).
- No pytest (per standing instruction — see memory). Verified manually with a throwaway script (not committed): `store.create_index()` → `store.index_data([dummy_doc])` → refresh → `store.search_data({"query": {"match": {"text": "diabetes"}}})` → confirmed exactly 1 hit with the expected `chunk_id` → deleted the dummy doc.
- Confirmed mapping via `curl http://localhost:9200/medical-rag-chunks/_mapping` matches the data model, with `embedding.dims: 512` correctly picked up from `.env`'s current `EMBEDDING_DIM`.
- `curl http://localhost:9200/medical-rag-chunks/_count` → `0` after cleanup — index exists and is empty, ready for Phase 3's real ingestion.
- `mypy . --strict` (from `backend/`) — clean, 6 source files.

## Known issues / tech debt
- None new. Still carrying over from Phase 0: Python 3.14 vs CLAUDE.md's pinned 3.12; Docker Desktop needs to be started manually each session (it was running for this phase, unlike Phase 0).

## Notes for next phase
- Phase 2 (embedding layer) needs `SentenceTransformer(settings.embedding_model)` — no embedding API/URL exists in config (see `docs/architecture.md`'s Config decisions).
- Phase 3 (chunking layer) will build documents shaped like `{"chunk_id", "hf_row_id", "text", "embedding", "chunk_index"}` and call `store.index_data(documents)` — the dummy doc in this phase's verification used exactly that shape, so it's a working reference.
- `store.search_data()` expects `query` to be a dict whose keys are valid `es.search()` kwargs (e.g. `query`, `knn`, `sort`) — don't include `index` or `size` in it, those are the method's own params.
- The Elasticsearch index currently lives with `settings.embedding_dim=512` (from `.env`, since the model was switched to `nomic-ai/nomic-embed-text-v1.5`). If `EMBEDDING_MODEL`/`EMBEDDING_DIM` changes again before Phase 3 ingests real data, the index must be dropped and recreated (dims are fixed at index-creation time in Elasticsearch).
