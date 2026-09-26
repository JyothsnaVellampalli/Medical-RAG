# Phase 3: Chunking layer
Status: done   Date: 2026-09-22, completed 2026-09-23

## What was built
A chunking/ingestion layer (`ChunkingEngine`) that fetches the HF `text-corpus` dataset, cleans null/empty passages, chunks (one row = one chunk, per fixed paragraph chunking), embeds each chunk via Phase 2's `EmbeddingProvider`, and bulk-indexes into Phase 1's Elasticsearch store.

**Full corpus successfully ingested: 40,221 / 40,221 rows (100%).** The background job survived four separate session-restart interruptions (at 5,600 / 17,600 / 19,200 / 37,600 rows, plus one Elasticsearch connection timeout under resource contention) and one Elasticsearch/Docker Desktop restart — every time, already-indexed data survived in the Docker volume and the resumable `ingest()` correctly picked up where it left off without re-embedding a single already-done row. Final verification: doc count matches exactly, spot-checked documents have correct shape and populated embedding vectors.

## Files created / changed
- `backend/Chunking/__init__.py`
- `backend/Chunking/chunking_engine.py` — `ChunkingEngine` class:
  - `clean_data(rows)` — drops rows with null/empty `passage`
  - `build_chunks(rows)` — maps each row to `{"chunk_id": f"{id}-0", "hf_row_id": id, "text": passage, "chunk_index": 0}`
  - `embed_and_index(chunks)` — embeds a batch's texts, attaches vectors, calls `store.index_data()`
  - `_already_indexed_row_ids()` — scans the index for existing `hf_row_id`s, so...
  - `ingest(batch_size=800)` — is resumable: skips rows already indexed, so re-running after any interruption only processes what's left, without re-embedding already-done work
  - module-level `chunking_engine` singleton
- `backend/Embedding/embedding_provider.py` — added `MAX_SEQ_LENGTH = 512` cap on the model (see decisions below); this is a Phase 2 file touched during Phase 3 integration testing.
- `backend/requirements.txt` — added `datasets==5.0.1`
- `backend/mypy.ini` — added (new): suppresses the missing-stub warning for the untyped `datasets` package only; strict mode stays on for everything else.
- `docs/architecture.md` — dataset schema and ingestion decisions to be added once this phase closes.

## Key decisions and why
- **Dataset config: `text-corpus`/`passages`, not `question-answer-passages`**: `rag-datasets/rag-mini-bioasq` has two HF configs. `text-corpus` (40,221 rows, columns `id` int64 + `passage` string) is the actual document corpus to index — one row = one chunk, matching the roadmap and CLAUDE.md's fixed paragraph-chunking rule. `question-answer-passages` (question/answer/relevant-passage-id triples) is for the future Evaluate page, not indexing.
- **`chunk_id = f"{hf_row_id}-0"`**: forward-compatible with a future multi-chunk-per-row scenario (chunk_index would disambiguate), even though today it's always `-0` since chunking is fixed one-row-one-chunk.
- **Batched processing (default 800 rows/batch, ~50 batches for the full corpus)**: your call, to keep memory bounded and give incremental progress visibility — confirmed via manual timing before committing to a run.
- **`MAX_SEQ_LENGTH = 512` added to `EmbeddingProvider`**: discovered during this phase's integration testing, not Phase 2's smaller-scale tests. A handful of this dataset's passages run up to ~33k characters; without a cap, sentence-transformers' quadratic attention cost on those outliers can dominate a batch's runtime. Capping only gave a modest ~18% speedup on a batch of typical-length passages (median 808 chars) — the real value is bounding the *worst case* for batches that do contain the long outliers.
- **Resumable `ingest()`**: added after the background ingest process was killed by a session restart partway through (a harness limitation — background shell commands don't survive the session ending). `_already_indexed_row_ids()` scans existing `hf_row_id`s and skips them on re-run, so an interruption costs wall-clock time, not embedding compute.

## How to run / test
- No pytest (standing instruction). Verified manually in stages:
  1. Smoke test: 5 real rows + 2 null/whitespace rows → confirmed nulls dropped, correct chunk shape, correct embedding dimension, ES round trip.
  2. Timing test: measured ~2.3–2.8 rows/sec on this CPU-only machine → extrapolated ~4–5 hours for the full 40,221-row corpus. You chose to run the full ingest now rather than a smaller sample or further speed investigation.
  3. Full ingest launched in the background; interrupted once by a session restart at 5,600/40,221 rows (data survived in the Docker volume). Resume logic added and verified (`_already_indexed_row_ids()` correctly found the 5,600 existing rows), then re-launched for the remaining 34,621.
- `mypy backend --strict` — clean (10 source files, with `mypy.ini` scoping the `datasets` stub exception).
- Final: `_count` on `medical-rag-chunks` returns exactly 40,221 (no rows dropped — the dataset had no null/empty passages in practice); spot-checked documents via `_search` show correct `chunk_id`/`hf_row_id`/`text`/`chunk_index` and a populated 512-dim `embedding` vector.

## Known issues / tech debt
- **Background jobs do not survive a session restart** — this hit the ingest job four separate times over the course of this phase (a harness limitation, not a code bug). Resume support made every interruption cheap (lost wall-clock time only, zero re-computation), but it's a pattern worth remembering for Phase 8's evaluation job too, which will also be long-running.
- Docker Desktop does not auto-start and needed manual relaunching after every session restart throughout this phase.
- Total real-world elapsed time to fully ingest the corpus, across all interruptions, was roughly a day of wall-clock time (not continuous compute) — the actual CPU-bound embedding work was closer to the originally-estimated 4-5 hours.

## Notes for next phase
- Phase 4, 5, 6, and 7 were all built and verified against this corpus while it was still partially ingested (they don't depend on corpus completeness for correctness) — this phase closing out now mainly matters for realistic result quality and for Phase 8's evaluation, which the user explicitly wants to wait for full ingestion before running.
- The resumable-background-job pattern proven here (`_already_indexed_row_ids()`-style dedup + a persisted state you can safely re-check on restart) is directly reusable for Phase 8's evaluation job, which will also run for a long time and is vulnerable to the same session-restart interruptions.
