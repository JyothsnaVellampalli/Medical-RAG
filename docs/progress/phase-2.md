# Phase 2: Embedding layer
Status: done   Date: 2026-09-22

## What was built
A local embedding layer (`EmbeddingProvider`) that loads the model named in `.env` via `sentence-transformers` and turns text into vectors sized to match Phase 1's Elasticsearch index. No external embedding API is involved — everything runs on-device (CPU, in this environment).

## Files created / changed
- `backend/Embedding/__init__.py`: empty, makes `Embedding` an importable package.
- `backend/Embedding/embedding_provider.py`:
  - `EmbeddingProvider.__init__`: loads `SentenceTransformer(settings.embedding_model, truncate_dim=settings.embedding_dim, trust_remote_code=True)`, then self-checks the output dimension against `settings.embedding_dim` and raises immediately on mismatch.
  - `embed(texts: list[str]) -> list[list[float]]`: batch-first, prefixes every text with `"search_document: "` (Nomic's document-side convention).
  - Module-level `embedding_provider` singleton.
- `backend/requirements.txt`: added `sentence-transformers==5.7.0`, `transformers==4.57.6` (pinned together — see decisions below), `einops==0.8.2`.
- `docs/architecture.md`: fixed a typo (`embeding_provider.py` → `embedding_provider.py`) and added an "Embedding decisions" section.
- System-wide: installed the Microsoft Visual C++ Redistributable (`winget install Microsoft.VCRedist.2015+.x64`) — required for `torch`'s Windows wheel to load at all; you approved the UAC prompt for this.

## Key decisions and why
- **`truncate_dim=settings.embedding_dim`**: `nomic-embed-text-v1.5` natively outputs 768-dim vectors, but `.env` has `EMBEDDING_DIM=512` and Phase 1's index is already built with `dims: 512`. Nomic is a Matryoshka model, so `SentenceTransformer`'s `truncate_dim` param truncates+renormalizes correctly instead of silently producing 768-dim vectors that wouldn't fit the index.
- **`search_document: ` prefix, not `search_query: `**: your call. This provider is used to embed content that gets *stored* (Phase 3's chunks). Flagged for Phase 4: embedding a user's search query at retrieval time should use `"search_query: "` instead — this method as written is document-oriented, not symmetric.
- **Batch-first `embed()`**: your call, since Phase 3 will embed many HF dataset rows at once and `sentence-transformers` batches natively.
- **`sentence-transformers==5.7.0` / `transformers==4.57.6` pin**: hit a real incompatibility — `sentence-transformers>=6.0` requires `transformers>=5.0`, but `transformers>=5.0`'s masking-API refactor removed `get_extended_attention_mask`, which nomic's `trust_remote_code` model file still calls. You chose to downgrade both packages together (over switching to a different embedding model) to keep nomic working. Revisit this pin if the embedding model changes.
- **Dimension self-check at construction**: fail-fast design — if `.env`'s `EMBEDDING_MODEL`/`EMBEDDING_DIM` ever drift out of sync again (same class of bug as Phase 0's config crash), it now surfaces immediately at startup instead of obscurely at ES indexing time in Phase 3.

## How to run / test
- No pytest (standing instruction). Verified manually, twice:
  1. `embedding_provider.embed([...])` on two sample sentences → confirmed 2 vectors, each 512-dim.
  2. Full round trip: embedded 3 real medical sentences, indexed them into Phase 1's `store` (`medical-rag-chunks`), ran a `knn` cosine-similarity search for `"What causes high blood sugar?"` — the diabetes sentence correctly ranked #1 (0.8664), hypertension #2 (0.8507), mitochondria (irrelevant) last (0.7776). Cleaned up afterward; index back to 0 docs.
- `mypy backend --strict` (8 source files) — clean.

## Known issues / tech debt
- First `SentenceTransformer(...)` load downloads the model from Hugging Face and caches it (`~/.cache/huggingface`) — expect a delay (and network access) the first time this runs in a new environment.
- Still carrying over: Python 3.14 vs CLAUDE.md's pinned 3.12; Docker Desktop must be started manually each session.
- CPU-only inference (no GPU detected/configured) — fine for this dataset's scale, but embedding the full HF dataset in Phase 3 will be slower than with a GPU.

## Notes for next phase
- Phase 3 (chunking layer): call `embedding_provider.embed(list_of_chunk_texts)`, zip the vectors onto documents shaped `{"chunk_id", "hf_row_id", "text", "embedding", "chunk_index"}`, and call `store.index_data(documents)`. This exact shape was validated in this phase's round-trip test.
- Phase 4 (retrieval layer): when embedding a user's query for semantic/hybrid search, do **not** reuse `embed()` as-is — it hardcodes the `"search_document: "` prefix. Either add a query-side method/param to `EmbeddingProvider`, or handle the `"search_query: "` prefix at the call site.
- The `medical-rag-chunks` index still has `dims: 512` baked in from Phase 1. If `EMBEDDING_MODEL`/`EMBEDDING_DIM` change again before Phase 3 ingests real data, the index must be dropped and recreated.
