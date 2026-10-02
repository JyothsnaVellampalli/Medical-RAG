## Folder structure

docs
    |- Architecture.md
    |- Roadmap.md
    |- UIDesign.md
    |- progress
    |   |- Template.md
    |   |- phase1.md
Frontend
    |- tsconfing
    |- eslint
    |- .env
    |- package.json
    |- src
    |   |- api
    |   |   |- client.ts
        |- CommonComponents
        |   |- Button
        |   |   |- Button.tsx
        |   |   |- Button.css
        |
        |
        |- Pages
        |   |- Chunk
        |   |- Retrieve
        |   |- Evaluate

Backend
    |- main.py
    |- routes.py
    |- config.py
    |- requirements.txt
    |- .env
    |- DataStore
    |   |- elastic_search_store.py
    |- Embedding
    |   |- embedding_provider.py
    |- Chunking
    |   |- chunking_engine.py
    |- Retrieval
    |   |- retrieval_registry.py
    |- LLM
    |   |- llm_query_layer.py
    |- Evaluation
    |   |- evaluation_engine.py
    |   |- evaluation_store.py
    |   |- ir_metrics.py
    |   |- semantic_metrics.py

.gitignore
CLAUDE.md


## Data Model
### Elastic search properties
- chunk_id
- hf_row_id
- text
- embedding
- chunk_index


## Config decisions
- `backend/config.py` is the single `Settings` (pydantic-settings) class. Every field has a code default; `backend/.env` overrides it when present. Unknown keys in `.env` that don't match a field name will crash `Settings()` at import time (pydantic's `extra_forbidden`) rather than being silently ignored — keep `.env` and `config.py` field names in sync.
- No embedding API/URL. Phase 2 embeds locally via `sentence-transformers` (`SentenceTransformer`), so there's no OpenAI-compatible embedding endpoint to configure.
- `EMBEDDING_DIM` (`embedding_dim` in config, default `384`) is read from `.env`, not hardcoded — update it whenever `EMBEDDING_MODEL` changes to a model with a different output dimension.


## Embedding decisions
- `Embedding/embedding_provider.py`'s `EmbeddingProvider` loads `SentenceTransformer(settings.embedding_model, truncate_dim=settings.embedding_dim, trust_remote_code=True)`. `truncate_dim` matters for Matryoshka models like `nomic-embed-text-v1.5` (native 768-dim, truncated to `EMBEDDING_DIM`'s configured 512) — without it the model's raw output dimension won't match the ES index's `dims`. `trust_remote_code=True` is required for nomic's custom model code to load at all.
- On construction, `EmbeddingProvider` embeds a throwaway string and checks the output length against `settings.embedding_dim`, raising immediately if they don't match — a deliberate fail-fast so a `.env` model/dim mismatch breaks at startup, not obscurely at ES indexing time.
- `embed(texts: list[str]) -> list[list[float]]` is batch-first (always takes/returns a list, even for one item) and prefixes every text with `"search_document: "` — Nomic's asymmetric convention for text meant to be *stored* and searched against. **When Phase 4 (retrieval) embeds the user's query at search time, it must use `"search_query: "` instead**, not this same method as-is — this provider is document-embedding-oriented, not general-purpose.
- Pinned dependency versions (see `requirements.txt`): `sentence-transformers==5.7.0`, `transformers==4.57.6`. `sentence-transformers>=6.0` requires `transformers>=5.0`, but `transformers>=5.0` removed `get_extended_attention_mask`, which nomic's remote-code model still depends on — so both packages are held to versions from before that break. Revisit this pin if the embedding model ever changes away from nomic.
- Also required: `einops` (nomic's remote code imports it directly) and the Microsoft Visual C++ Redistributable installed system-wide (torch's Windows wheel needs it; installed via `winget install Microsoft.VCRedist.2015+.x64`).
- `EmbeddingProvider` has two encode entry points sharing a private `_encode()`: `embed()` (prefixes `"search_document: "`, used by the Chunking layer for content being stored) and `embed_query()` (prefixes `"search_query: "`, used by the Retrieval layer for the user's search text). Nomic's asymmetric convention — never use `embed()` for query text or vice versa.


## Dataset decisions
- `rag-datasets/rag-mini-bioasq` has two HF configs. `text-corpus`/`passages` split (40,221 rows, columns `id` int64 + `passage` string) is the actual document corpus that gets chunked and indexed — one row = one chunk. `question-answer-passages`/`test` split (question/answer/relevant-passage-id triples) is reserved for the future Evaluate page, not indexed.
- `Chunking/chunking_engine.py`'s `ChunkingEngine.ingest()` is resumable: it scans the index for already-present `hf_row_id`s and skips them, so re-running after an interruption only processes what's left rather than re-embedding everything. This matters in practice — background ingestion does not survive this session ending (a harness limitation), and Docker Desktop does not auto-start, so both have needed manual recovery during development.
- `EmbeddingProvider`'s `MAX_SEQ_LENGTH = 512` cap (added during Chunking integration) exists because this dataset has passages up to ~33k characters, and uncapped attention cost on those outliers was making some ingest batches dramatically slower than typical ones.


## Retrieval decisions
- `Retrieval/retrieval_registry.py`'s `RetrievalRegistry` is a single class, one method per mechanism (`bm25_search`, `semantic_search`, `hybrid_weighted_search`, `hybrid_rrf_search`), consistent with every other layer in this codebase (`DataStore`, `Embedding`, `Chunking` are each one file/one class). `retrieve(strategy, query_text, size, weight)` is the registry itself: its internal `{name: method}` mapping is what CLAUDE.md's rule 1 means by "add a new line in the retrieval registry" — a 5th mechanism means one new method plus one new dict entry, nothing else changes.
- **No native ES hybrid retrievers**: ES 8.15.3 (this project's version) parses the `retriever` DSL, but its `rrf` retriever requires a licensed feature this cluster's Basic license doesn't include (a 30-day trial would unlock it, but a trial can only be started once per cluster, ever, and then it's gone), and the `linear` weighted retriever doesn't exist in this ES version at all. Both `hybrid_weighted_search` and `hybrid_rrf_search` therefore fetch BM25 and kNN candidate lists from Elasticsearch separately (still the only source of ranking/relevance) and fuse them in Python:
  - Weighted: min-max normalize each candidate list's scores to `[0,1]`, combine as `weight × semantic + (1-weight) × bm25`.
  - RRF: standard `1/(k + rank)` per list, `k=60` (the original RRF paper's default), summed across lists.
  - Both fetch `max(size × 3, 30)` candidates per underlying method before fusing, to give the fusion step enough of each ranking to work with.
- Every retrieval method returns the same shape per hit — `{"chunk_id", "text", "chunk_index", "score"}` — matching `docs/UIDesign.md`'s Retrieve page table columns exactly, so Phase 5's API and Phase 6's UI don't need per-strategy result handling.


## API decisions
- `backend/routes.py` stays a single file (no per-feature router modules) — matches `architecture.md`'s listing and the project's established one-file-per-layer pattern.
- `GET /get_chunks` sorts by `hf_row_id` ascending so "first 10" is deterministic; `match_all` with no sort returns ES's internal order, which isn't guaranteed stable.
- `POST /retrieve`'s `search_type` values are `RetrievalRegistry`'s own strategy keys (`bm25`, `semantic`, `hybrid_weighted`, `hybrid_rrf`), not the UI's display labels (`Lexical(BM25)`, etc.) — Phase 6's frontend maps dropdown labels to these keys when building the request.
- Both endpoints use Pydantic response models (`ChunkResult`, `RetrieveResult`), which also has the side effect of stripping the large `embedding` vector out of `/get_chunks` responses automatically (FastAPI only serializes declared fields).
- Error mapping, informed by real failures hit during development: `ValueError` (unknown `search_type`) → `400`; `elastic_transport.ConnectionError` (ES unreachable) → `503`. Both logged via `logger.py`. Anything else is left to propagate as FastAPI's normal `500` rather than being masked by a blanket `except Exception`.


## UI decisions
- `CommonComponents/`: `Button`, `Dropdown` (wraps a native `<select>` for free keyboard accessibility rather than a hand-rolled div dropdown), `Loader`, `Navbar`, `Table` (generic, columns-driven, reused by both Chunk and Retrieve pages), `Modal` (Escape-to-close, used by Evaluate's config popup), `CollapsiblePanel` (built for Ask's future citations panel, not yet wired to real data).
- `Pages/`: `Landing` (Phase 0, kept as Home), `Chunk`, `Retrieve`, `Ask`, `Evaluate` — routed via a shared `Layout` (`Navbar` + `<Outlet />`) in `App.tsx` so every page gets the navbar.
- `Retrieve` page's weight slider shows both the semantic weight and its computed complement (`1 - weight`) as BM25's weight, rather than two independently-editable inputs — guarantees they always sum to 1, matching `hybrid_weighted_search`'s single-weight signature.
- `search_type` values sent to `/retrieve` are `RetrievalRegistry`'s keys (`bm25`, `semantic`, `hybrid_rrf`, `hybrid_weighted`); the dropdown maps its display labels (`Lexical(BM25)`, etc.) to these client-side.
- `client.ts` only wraps endpoints that actually exist — grew from `checkHealth`/`getChunks`/`retrieve` (Phase 6) to also include `askQuery` (Phase 7) and `startEvaluation`/`getEvals` (Phase 8) as each landed. Ask and Evaluate were originally UI shells with "not yet available" notices; both are now fully wired.


## LLM decisions
- `LLM/llm_query_layer.py`'s `LLMQueryLayer` runs locally via Ollama (`ollama/ollama` Docker image, `llama3.2:3b`). `docker-compose.yml` only starts the container — the model itself is pulled once, manually: `docker exec med-rag-ollama ollama pull llama3.2:3b` (~2GB).
- **Citations come from the retrieval layer, not the LLM**: `query()` retrieves the top 5 chunks first, then asks the model to answer using only that context — the response's `citations` are exactly the chunks that were put in the prompt, not something the LLM is asked to self-report. More reliable than trusting a 3B model to accurately cite its own sources in structured form.
- **Lazy failure, not fail-fast at startup** (unlike `EmbeddingProvider`): `LLMQueryLayer.__init__` doesn't check Ollama's reachability — Ollama may not be running yet when the backend starts, and `/health`, `/get_chunks`, `/retrieve` shouldn't break because of it. Ollama's Python client raises a plain builtin `ConnectionError` (not an `ollama`-specific exception) when unreachable — `routes.py`'s `/query` maps that to `503`, alongside `elastic_transport.ConnectionError` for ES.
- **CPU-only generation is genuinely slow, especially under contention**: a warm request with 5 context chunks took ~20s in isolation; while competing with the Phase 3 background ingest for CPU, the same kind of request took several minutes. This is expected on this hardware, not a bug — cold model load alone (first request only) was ~108s.
- `frontend/.env`'s `VITE_LLM_MODEL` mirrors `LLM_MODEL` for the Ask page's subheading — same pattern as `VITE_API_BASE_URL`, avoids a new API just to expose one static config string.


## Evaluation decisions
- **Storage: Supabase Postgres, not Elasticsearch** — your call, using Docker images you already had (`pgvector/pgvector:pg17` + `postgrest/postgrest`). `docker-compose.yml`'s `supabase-db`/`supabase-rest` services; `backend/Evaluation/evaluation_store.py` talks to Postgres directly via `psycopg` (not through PostgREST's REST API — our own FastAPI backend is already the API layer the frontend talks to). Two tables: `eval_jobs` (one row per run: mechanisms, test_size, state, timestamps) and `eval_results` (one row per question × mechanism, including the HF QA id, per the roadmap's explicit requirement to store it).
- **No judge LLM anywhere in evaluation** — this went through two iterations. First attempt used `qwen2.5:7b` as an LLM judge for RAGAS-style metrics; that got OOM-killed (this machine has 8GB RAM total, Docker's WSL2 VM defaults to 3.7GB, and the 4.7GB model didn't fit). Switched to `qwen2.5:3b`, which fit but gave an unreliable verdict in testing (marked a clearly-relevant passage as irrelevant for `context_precision`, even with a clarified prompt — a genuine small-model capability limit, not a bug). Since this project evaluates against a QA dataset with **known-correct answers** — unlike most RAGAS use cases, which assume no ground truth — you decided to drop the judge model entirely: `Evaluation/semantic_metrics.py` computes faithfulness/answer_relevancy/answer_correctness via embedding cosine similarity (reusing `EmbeddingProvider`, already proven reliable) instead of asking a model to guess. This is both more robust for this specific dataset and eliminates the OOM risk completely — the only LLM call anywhere in evaluation is the answer generation itself (`llm_query_layer.query()`, same as the Ask page).
- **The `ragas` PyPI package could not be installed** on this machine at all (separate from the judge-model issue above) — its `scikit-network` dependency has no prebuilt wheel for Python 3.14 on Windows, and installing the full Visual Studio Build Tools C++ compiler didn't fix it (setuptools' own MSVC auto-detection fails independently of the shell environment). `semantic_metrics.py`'s docstring and `[[project-ragas-scikit-network]]`-style memory record this so it isn't re-attempted without checking first.
- **No Langfuse** — the roadmap's original Phase 8 spec asked for it. Weighed self-hosted (needs Postgres + ClickHouse + Redis + blob storage — a lot more on top of what's already running) vs. cloud (sends trace data to a third party) vs. skip. You chose skip: "We do not need observability in this project." Structured application logging (see below) covers the debugging/progress-visibility need instead.
- **Explicit, structured logging on every API route** (`[API] METHOD /path - ...` prefix), added per your explicit request: every frontend-triggered backend action should be visible in the logs for debugging, progress-checking, and error handling — not just "request received" but also the outcome (result count / job id / error) on the way out. This extends the pattern `DataStore`/`Retrieval`/`LLM` already had from earlier phases.
- **Resumable by the same pattern as `ChunkingEngine.ingest()`**: `EvaluationEngine._already_scored()` checks existing `(hf_qa_id, mechanism)` result rows before re-running, so `resume_job(job_id)` (not yet wired to an API, but available) picks up where an interrupted run left off. Directly motivated by how many times session restarts killed the Phase 3 ingest — an evaluation run is just as long-running and just as vulnerable.
- **Background execution via a plain `threading.Thread`**, not FastAPI's `BackgroundTasks` — same reasoning as `ChunkingEngine`: a run this long shouldn't share the request threadpool with `/retrieve`/`/query` traffic.
- **Test set: fixed random seed** (`settings.eval_random_seed`, default 42), not re-randomized per run — so repeated runs (different mechanisms, different days) evaluate the *same* question sample, making mechanism-vs-mechanism comparison fair. Sampled from `question-answer-passages`/`test` (4,719 rows, ground-truth `answer` + `relevant_passage_ids`).
- **IR metrics (`ir_metrics.py`) need no embeddings or LLM at all** — Precision@k/Recall@k/MRR/nDCG computed directly from `relevant_passage_ids` (ground truth) vs. retrieved `hf_row_id`s. This is why `RetrievalRegistry._format_hit()` was extended to include `hf_row_id` (previously only `chunk_id`, from which the row id could only be recovered by fragile string-parsing).
- **`GET /get_evals/{job_id}/results`**: per-question drill-down, added after the real evaluation run, so individual errors and per-question metric variance are inspectable in the UI rather than only visible as job-level averages (an average can look fine while hiding, e.g., one mechanism losing half its questions to infrastructure errors — which is exactly what happened during the real run; see `docs/progress/phase-8.md`).
- **Per-question filters (mechanism dropdown + HF QA ID number input) filter client-side**, not via new API query params — all of a job's results are already fetched in one call (at most ~a few hundred rows for this project's scale), so filtering in the browser is instant and avoids a second round-trip per filter change. The filter bar is `position: sticky` within the scrollable results container so it stays visible while scrolling through up to 120+ rows.
- **This machine's Docker/WSL2 VM hangs completely under sustained load** (not just slow — Ollama stops responding, then Docker's control-plane API, then `wsl` commands themselves) — hit four times during the real 120-evaluation run alone. Root cause is the same 8GB-RAM/3.7GB-WSL2-ceiling constraint noted elsewhere, now confirmed to also manifest as instability under *sustained* load, not just peak memory. Recovery is always `wsl --shutdown` + relaunch Docker Desktop + resume the job — the resumable design (see above) is what makes this survivable rather than catastrophic. Budget for this on any future long-running job on this hardware.


## Ask-page (per-query) evaluation decisions — Phase 9
- **Only faithfulness and answer_relevancy, not the full 5-metric set**: ad-hoc Ask-page questions have no ground-truth answer or `relevant_passage_ids` (unlike the Evaluate page's HF QA dataset), so `precision_at_k`/`recall_at_k`/`mrr`/`ndcg_at_k`/`answer_correctness` — everything that needs a known-correct answer or known-relevant passages — cannot be computed here. `faithfulness(response, contexts)` and `answer_relevancy(query, response)` from `Evaluation/semantic_metrics.py` need only the response, the retrieved contexts, and the query itself, all of which exist for any ad-hoc question.
- **Evaluation logic lives in `routes.py`, not `LLMQueryLayer`**: `/query` calls `faithfulness()`/`answer_relevancy()` directly, conditionally on `payload.evaluation`, after `llm_query_layer.query()` returns. Keeps `LLMQueryLayer` single-responsibility (retrieval + generation only) — evaluation is a cross-cutting concern the route layer applies on top, the same way the Evaluate page's `EvaluationEngine` is a separate orchestrator rather than logic bolted onto `LLMQueryLayer`.
- **`QueryRequest.evaluation` defaults to `False`**: evaluation adds real latency (two extra embedding calls) for something most Ask-page queries don't need — it's opt-in via the UI checkbox, not automatic.
- **UI**: `Ask.tsx` gained a full-width, gradient-background config section (`--color-primary` → `--color-primary-hover`, matching the app's existing palette) above the search box, holding the mechanism dropdown, the conditional weight slider (shown only for `hybrid_weighted`, same pattern as `Retrieve.tsx`), and the evaluation checkbox. Results render in a second `CollapsiblePanel` next to citations, only when `evaluation` came back non-null. (The gradient background was later removed per your feedback — the config section now uses the plain page background.)


## OpenRouter integration decisions — Phase 10
- **Additive, not a replacement**: Ollama stays the default generation provider everywhere; OpenRouter is a second, opt-in provider selectable per-query from the Ask page's new provider dropdown (`ollama` default, `openrouter` selectable). Nothing that used Ollama before was removed.
- **Generation provider abstraction mirrors `RetrievalRegistry`'s exact pattern** (per CLAUDE.md's own SOLID example): `LLM/generation_registry.py`'s `GenerationRegistry.generate(provider, prompt, system)` dispatches to `ollama_generate()` or `openrouter_generate()` via a one-line-per-provider mapping dict. `LLM/llm_query_layer.py` no longer owns an `ollama.Client` directly — it delegates to the registry and gained a `provider` parameter (default `"ollama"`).
- **Model IDs corrected from the roadmap's originals, verified live against OpenRouter's actual catalog**: `nvidia/nemotron-3-ultra:free` (as written) doesn't exist, but `nvidia/nemotron-3-ultra-550b-a55b:free` does and works — the roadmap's instinct ("ultra") was right, just missing the full slug.
- **Judge model switched from `typesafe/jev-router` to `typesafe/jev-1.13`, and the judge integration rewritten around it** (second iteration, same day). `jev-router` is OpenRouter's model-*routing* tool (picks which underlying chat model handles a request, e.g. observed routing to `openai/gpt-6-luna`) — it worked via the ordinary `/chat/completions` endpoint but wasn't purpose-built for scoring and wasn't actually free (routes to paid models at a small real cost, ~$0.000026/call; the dev OpenRouter account's $0 credit balance made this path flaky — intermittent 402/503). `jev-1.13` is TypeSafe's actual **decisions model**: a different OpenRouter product entirely, called via `POST /api/alpha/decisions` (not `/chat/completions`) with a structured `{model, state, questions}` request rather than chat messages, returning typed `score`/`choice`/`noul` answers rather than free text. It cannot be called via `/chat/completions` at all (confirmed live: 400 "is a decisions model... use /api/alpha/decisions instead"). Your choice, and a better fit than `jev-router`: cheaper per call (~$0.0000226, no routing to a second paid model), and needs no natural-language generation or free-text JSON parsing for the eval use case — the API returns a typed numeric score directly.
- **`llm_judge_metrics.py`'s "score" questions use a 5-level ordered scale** (`FAITHFULNESS_CRITERIA`/`ANSWER_RELEVANCY_CRITERIA`, each a list of 5 criterion descriptions, indices 0-4), normalized by `score / 4` to a 0.0-1.0 float matching `semantic_metrics.py`'s scale. The decisions API's `score` field is already a continuous, probability-weighted position along the levels (e.g. `3.99` out of 4), not just a discrete index — verified live against a real question/context/answer triple (faithfulness scored 4/4, relevancy 3.99/4 for a fully-correct answer).
- **OpenRouter can return HTTP 200 with an error object in the response body** instead of a proper HTTP error status (observed live on `/chat/completions`: `{"error": {"message": "Upstream error from Nvidia: Service temporarily overloaded", "code": 503}}` with status 200) — `httpx`'s `raise_for_status()` can't catch this. `openrouter_client.py`'s helpers check the body explicitly and raise `OpenRouterError` when present; `routes.py` maps that (alongside `httpx.HTTPError`) to the same `503 "LLM (OpenRouter) is unavailable"` response Ollama's `ConnectionError` gets.
- **Shared `openrouter_client.py` (top-level, alongside `config.py`/`logger.py`)**, with two helpers: `chat_completion()` (used by `generation_registry.py` for the ordinary chat-completions models) and `decision()` (used by `llm_judge_metrics.py` for the decisions API) — different endpoints and request/response shapes, but both centralize the same auth header and 200-with-error-body handling.
- **LLM-judge metrics added *alongside*, not replacing, the embedding-based ones** — per your explicit instruction. `llm_judge_metrics.py`'s `judge_metrics()` is called from `routes.py`'s background evaluation thread *after* the existing embedding-based `faithfulness()`/`answer_relevancy()` calls, independently. `QueryEvaluationRecord` (in `query_evaluation_store.py`) gained a fully independent `judge_state`/`judge_faithfulness`/`judge_answer_relevancy`/`judge_error` set of fields alongside the original `state`/`faithfulness`/`answer_relevancy`/`error` — two separate state machines, because the two computations can succeed/fail independently. Both metric sets confirmed working together live, end-to-end through the real `/query` → background-thread → `/get_query_evaluation` flow.
- **Scoped to the Ask page only**, not the Evaluate (benchmark) page — the roadmap's Done-When criteria only mention the Ask page using OpenRouter models; the Evaluate page's benchmark runs keep their existing embedding-only metrics and Ollama-only generation untouched.
- **UI**: Ask page's Evaluation panel now shows two independent sub-sections ("Semantic (embedding-based)" and "LLM Judge (jev-router)"), each with its own Done/Progress/Error rendering, sharing one refresh button (one `GET /get_query_evaluation/{id}` call refreshes both).


## Reranker decisions — Phase 11
- **New `Reranker/` layer** (new top-level folder, matching the one-folder-per-layer convention `DataStore`/`Embedding`/`Retrieval`/`LLM`/`Evaluation` already established) — `reranker.py`'s `Reranker.rerank(query_text, chunks)` sits between retrieval and generation in `LLMQueryLayer.query()`, called only when `rerank=True`.
- **Reuses `typesafe/jev-1.13`'s decisions API** (same model and `openrouter_client.decision()` helper Phase 10 built for judging) rather than a separate reranking model — one decisions call scores *all* retrieved chunks' relevance at once (one named `"score"` question per chunk, e.g. `relevance_0`..`relevance_4`), not one call per chunk. Verified live: scores spread meaningfully (e.g. `[3.28, 2.59, 2.56, 2.54, 1.05]` for 5 real chunks), and reordering a real 5-chunk BM25 result set visibly changed citation order.
- **Only the list order changes, not the chunks' own `score` field** — that field is each retrieval mechanism's own ranking score (BM25/cosine/etc.), left untouched; reranking is a pure reorder on top of it.
- **Citations reflect post-rerank order when reranking is on** — consistent with Phase 7's existing invariant that citations are exactly what was fed to the LLM, not something the LLM self-reports.
- **Rerank failures propagate as 503**, reusing the exact same `httpx.HTTPError`/`OpenRouterError` → `"LLM (OpenRouter) is unavailable"` mapping `routes.py` already has for generation/judging — no new error-handling branch, and no silent fallback to unreranked order.
- **Independent of generation provider**: reranking always calls OpenRouter's decisions API regardless of whether `provider` is `ollama` or `openrouter` for the generation step itself — the two are orthogonal toggles.
- **Scoped to the Ask page only**, matching Phase 10's precedent — the roadmap's Done-When criteria don't mention the Evaluate (benchmark) page.
