# Phase 4: Retrieval layer
Status: done   Date: 2026-09-22

## What was built
A retrieval layer (`RetrievalRegistry`) exposing four retrieval mechanisms over Elasticsearch — BM25 (lexical), semantic (cosine kNN), hybrid with a configurable weight, and hybrid via Reciprocal Rank Fusion — plus a `retrieve(strategy, ...)` dispatch method that acts as the registry itself. Built and verified against the real, partially-ingested corpus from Phase 3 (which was still growing in the background while this phase was built — the retrieval layer doesn't depend on the corpus being complete).

## Files created / changed
- `backend/Retrieval/__init__.py`
- `backend/Retrieval/retrieval_registry.py`:
  - `bm25_search(query_text, size)` — ES `match` query on `text`
  - `semantic_search(query_text, size)` — embeds the query, ES `knn` query on `embedding`
  - `hybrid_weighted_search(query_text, weight, size)` — min-max normalized weighted fusion of BM25 + kNN candidates
  - `hybrid_rrf_search(query_text, size, k=60)` — Reciprocal Rank Fusion of the same two candidate lists
  - `retrieve(strategy, query_text, size, weight)` — the registry: dispatches by strategy name via an internal mapping
  - Every method returns `{"chunk_id", "text", "chunk_index", "score"}` per hit
  - module-level `retrieval_registry` singleton
- `backend/Embedding/embedding_provider.py`: added `embed_query()` (prefixes `"search_query: "`) alongside the existing `embed()` (`"search_document: "`), sharing a new private `_encode()` helper. This was flagged as needed back in Phase 2's progress doc.
- `docs/architecture.md`: added "Dataset decisions" (moved/consolidated from Phase 3) and "Retrieval decisions" sections.

## Key decisions and why
- **Single class, one method per mechanism** (not one file per mechanism): matches every other layer in this codebase (`DataStore`, `Embedding`, `Chunking`) and `docs/architecture.md`'s file listing. Confirmed with you before implementing, since CLAUDE.md's rule 1 illustrative example could be read either way.
- **No native ES hybrid retrievers, fusion done in Python**: investigated ES 8.15.3's `retriever` DSL directly against the running cluster. Its `rrf` retriever exists but requires a licensed feature (`security_exception`, "current license is non-compliant") — this cluster runs Basic, and a 30-day trial license can only be started once per cluster ever, so activating it wasn't a free or repeatable option. Its `linear` weighted retriever returned `unknown retriever [linear]` — doesn't exist in this ES version at all. So both hybrid methods fetch BM25 and kNN candidates from Elasticsearch (the only source of relevance ranking) and fuse them in Python — a standard, license-independent, version-independent approach.
- **RRF `k=60`**: the default constant from the original Reciprocal Rank Fusion paper, and also Elasticsearch's own default for its (unavailable-to-us) native RRF retriever — kept for consistency with the standard.
- **Candidate pool = `max(size × 3, 30)`**: fetches enough of each ranking for the fusion step to have real signal, rather than fusing only the final top-`size` from each side.
- **Uniform result shape** (`chunk_id`, `text`, `chunk_index`, `score`): matches `docs/UIDesign.md`'s Retrieve page table columns, so Phase 5's API and Phase 6's UI need no per-strategy special-casing.

## How to run / test
- No pytest (standing instruction). Verified manually against the real, live corpus (13,600+ rows at test time, still growing): ran all four strategies with the query "What causes diabetes and high blood sugar?" —
  - BM25 and semantic returned meaningfully different top results (lexical match vs. conceptual similarity).
  - Weighted hybrid's math checked out exactly: `weight=0.9` produced a top score of `0.9000` matching semantic's #1 result; `weight=0.1` produced `0.9000` matching BM25's #1 result — confirms the normalization/fusion formula is correct, not just plausible-looking.
  - RRF produced a sensible blended ranking.
  - An unknown strategy name correctly raised `ValueError` with the list of valid strategies.
- `mypy backend --strict` (12 source files) — clean.

## Known issues / tech debt
- Result quality (not correctness) will improve once Phase 3's full 40,221-row ingest finishes — this phase was verified against a partial, growing corpus by design.
- No caching of query embeddings — each `semantic_search`/hybrid call re-embeds the query text. Not a problem at this scale; would matter under load.

## Notes for next phase
- Phase 5 (APIs): `/retrieve` should accept `{search_type, query, weight?}` and call `retrieval_registry.retrieve(strategy=search_type, query_text=query, weight=weight or 0.5)` — the registry's signature already matches what the roadmap describes for that endpoint's payload.
- `retrieve()` raises `ValueError` for an unknown strategy — Phase 5's API layer should catch this and turn it into a 400, not a 500.
