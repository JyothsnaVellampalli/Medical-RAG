# Phase 8: Run Evaluation
Status: done   Date: 2026-09-23, completed 2026-09-26

## What was built
An evaluation layer that, for a chosen set of retrieval mechanisms and a test size, samples questions from the HF QA dataset (fixed seed, for fair comparison across runs), runs the full retrieval→generation pipeline per question, scores each result against ground truth (both IR metrics and embedding-based semantic metrics — no judge LLM), and stores results in a Supabase Postgres store. Wired through `POST /evaluate` (starts a background job), `GET /get_evals` (lists jobs + aggregated per-mechanism metrics), and `GET /get_evals/{job_id}/results` (per-question drill-down). The Evaluate page (a UI shell since Phase 6) is now fully live: config modal, live-polling job list, per-mechanism comparison table, and an expandable per-question detail view (with mechanism + HF QA ID filters, client-side, sticky filter bar) showing every metric and any error, per question.

**The real evaluation run completed successfully**: 30 questions × 4 mechanisms = 120 evaluations, all scored (with some errors recorded — see results below).

## Files created / changed
- `docker-compose.yml`: added `supabase-db` (`pgvector/pgvector:pg17`) and `supabase-rest` (`postgrest/postgrest`) services.
- `backend/.env` / `.env.example`: `SUPABASE_DB_URL`, `RAGAS_JUDGE_MODEL` (unused — kept in case a judge model is reintroduced later), `GEMINI_API_KEY` (also unused, kept per your addition).
- `backend/config.py`: added the above settings, plus `eval_question_answer_split`, `eval_test_split`, `eval_random_seed`.
- `backend/requirements.txt`: added `psycopg[binary]==3.3.6`.
- `backend/Evaluation/`:
  - `evaluation_store.py`: `EvaluationStore` — Postgres schema (`eval_jobs`, `eval_results`) and CRUD, direct `psycopg` connections (no ORM).
  - `ir_metrics.py`: `compute_ir_metrics()` — Precision@k, Recall@k, MRR, nDCG@k from ground-truth `relevant_passage_ids`, no LLM/embeddings needed. Hand-verified against manually computed expected values.
  - `semantic_metrics.py`: `compute_semantic_metrics()` — faithfulness, answer_relevancy, answer_correctness via embedding cosine similarity (see decisions below for why this replaced an LLM-judge approach).
  - `evaluation_engine.py`: `EvaluationEngine` — orchestrates the full test_size × mechanisms loop as a resumable background thread.
- `backend/Retrieval/retrieval_registry.py`: `_format_hit()` now includes `hf_row_id` (needed by IR metrics; previously only recoverable by parsing `chunk_id`'s string format).
- `backend/routes.py`: `POST /evaluate`, `GET /get_evals`, `GET /get_evals/{job_id}/results`; structured `[API] METHOD /path - ...` logging on every route (request, outcome, errors), per your explicit request for full action visibility.
- `backend/LLM/llm_query_layer.py`: added a completion log line (previously only logged "generating", not "generated").
- `frontend/src/api/client.ts`: `startEvaluation()`, `getEvals()`, `getEvalResults()`, and their types.
- `frontend/src/Pages/Evaluate/Evaluate.tsx` + `.css`: live job list (auto-polls every 15s while any job is `Progress`), per-mechanism metrics comparison table, and an expand/collapse toggle per job revealing a scrollable per-question table (all metrics + error message per row), filterable by mechanism (dropdown) and HF QA ID (number input, exact match) — both filters apply client-side and reset when switching jobs.

## Key decisions and why
- **Dropped the LLM-judge approach entirely, mid-phase**: first attempt used `qwen2.5:7b` as judge for RAGAS-style metrics. Got OOM-killed after ~18.5 minutes — this machine has only 8GB RAM, Docker's WSL2 VM defaults to 3.7GB, and the model's 4.7GB footprint didn't fit. Switched to `qwen2.5:3b` (fits), but it gave a wrong verdict in testing (marked a clearly-relevant passage irrelevant). You then pointed out we already have ground-truth answers for this QA dataset — unlike most RAGAS scenarios — so a judge is unnecessary: `semantic_metrics.py` computes the same conceptual metrics via embedding similarity against ground truth instead.
- **The `ragas` PyPI package itself couldn't install** on this machine — its `scikit-network` dependency has no prebuilt wheel past Python 3.13, and installing the full Visual Studio Build Tools C++ compiler didn't fix it (setuptools' own MSVC detection fails independently). Confirmed dead end before pivoting.
- **Storage: Supabase Postgres, not Elasticsearch**: your call, reusing Docker images you already had. Backend talks to Postgres directly via `psycopg`, not through PostgREST.
- **No Langfuse**: weighed self-hosted (heavy) vs. cloud (sends data out) vs. skip. You chose skip — "we do not need observability in this project" — structured application logging covers it instead.
- **`hf_row_id` added to `RetrieveResult`**: needed so IR metrics can compare retrieved chunks against ground-truth `relevant_passage_ids` without fragile string-parsing.
- **Resumable, background-thread execution**: modeled on `ChunkingEngine.ingest()`. This turned out to be essential, not just precautionary — see below.
- **Fixed random seed for the test sample**: ensures repeated evaluation runs compare against the *same* questions, for fair mechanism-vs-mechanism comparison.
- **Test size 30, not the roadmap's literal "100"**: your explicit choice. Treated the same way as Phase 5's "three apis" text — a specific number in the roadmap that your live direction superseded.
- **Per-question drill-down added after the real run**, per your request, to make individual errors and per-question metric variance inspectable rather than only seeing aggregates.

## The real run: what happened
Kicked off `POST /evaluate` with all four mechanisms at `test_size=30` (120 total evaluations). This surfaced a reliability problem this project hadn't hit before: **Docker's WSL2 VM hung completely four separate times** during the ~2.5-hour run, each time under sustained CPU load from repeated LLM generation calls. Each hang looked the same: Ollama stopped responding (`curl` timeout), then Docker's own control-plane API started returning 500s, and eventually WSL2's own service became unresponsive to `wsl` commands entirely — not just slow, genuinely hung.

Recovery each time was the same sequence: kill the stuck process, `wsl --shutdown`, relaunch Docker Desktop, wait for Elasticsearch/Ollama/Postgres to come back, check exact progress in `eval_results`, then call `evaluation_engine.resume_job(job_id)` (no dedicated API route for this yet — done via a small standalone script). Every single time, zero data was lost — the resumable design worked exactly as intended, picking up from wherever it left off. The job also independently hit 33 individual per-question errors (mostly `hybrid_rrf`, which lost half its questions to a hang) from Ollama's generator process crashing mid-request ("model runner has unexpectedly stopped, this may be due to resource limitations") — these are recorded as permanent error rows rather than auto-retried, since resumability is about not repeating already-attempted work.

### Final results (30 questions per mechanism)

| Mechanism | Precision@k | Recall@k | MRR | nDCG@k | Faithfulness | Relevancy | Correctness | Avg latency | Errors |
|---|---|---|---|---|---|---|---|---|---|
| BM25 | 0.528 | 0.325 | 0.660 | 0.584 | 0.825 | 0.868 | 0.865 | 88.8s | 5 |
| Semantic | 0.504 | 0.275 | 0.678 | 0.545 | 0.864 | 0.869 | 0.874 | 95.7s | 5 |
| Hybrid (RRF) | 0.427 | 0.274 | 0.544 | 0.456 | 0.845 | 0.855 | 0.860 | 64.8s | **15** |
| Hybrid (Weighted) | 0.518 | 0.335 | 0.731 | 0.590 | 0.859 | 0.859 | 0.867 | 86.5s | 8 |

Hybrid (Weighted) leads on retrieval quality (best MRR and nDCG); BM25 is close behind with the fewest errors. Answer-quality metrics (faithfulness/relevancy/correctness) cluster tightly (~0.85-0.87) across all four, suggesting the retrieval mechanism affects *what gets found* far more than it affects the generation step's quality once *some* context is provided. **`hybrid_rrf`'s numbers rest on a smaller, less reliable sample (only 15/30 succeeded)** due to disproportionately colliding with the hang windows — not a reflection of the mechanism itself. A re-run (now that the immediate session is stable) would give a cleaner comparison for that mechanism specifically.

## How to run / test
- No pytest (standing instruction). Verified in stages, smallest to largest, then for real:
  1. `ir_metrics.py` — hand-computed expected values, exact match including edge cases.
  2. Full `EvaluationEngine` pipeline — direct smoke test, 2 questions, completed correctly with full logging.
  3. Full stack via the live UI — 1-question run, confirmed `Progress`→`Done` transition and metrics table rendering.
  4. **The real 120-evaluation run** — completed successfully across four Docker/WSL2 hang-and-recover cycles (see above), final results confirmed via `/get_evals`.
  5. Drill-down UI — verified via headless browser against the real completed job: all 120 per-question rows render correctly, error rows show `—` for unscored metrics and the actual error message in red, zero console errors.
- `mypy backend --strict` (19 source files) — clean throughout.
- `npm run lint` / `npm run build` — clean (one documented ESLint suppression for a `react-hooks/set-state-in-effect` false positive on the standard fetch-on-mount pattern).

## Known issues / tech debt
- **`resume_job()` has no API route** — every recovery this phase was done via a standalone script, not through the API. Worth adding a proper `POST /evaluate/{job_id}/resume` if this project keeps running long jobs on this hardware.
- **Docker/WSL2 hangs under sustained load are a real, recurring constraint of this specific machine** (8GB RAM, default 3.7GB WSL2 VM ceiling) — not fixed, just worked around each time. Any future long-running job (Phase 9's evaluations, larger test sizes) should expect the same pattern and budget recovery time for it.
- `hybrid_rrf`'s current results are based on a partial (15/30) sample due to hang timing — flagged in the results table above; a targeted re-run would clean this up.
- `RAGAS_JUDGE_MODEL` / `GEMINI_API_KEY` config fields are unused dead weight — kept in case a judge-based approach is revisited.

## Notes for next phase
- Phase 9 (Query Expansion) needs to re-run evaluations (10 QA questions per the current roadmap text, hybrid(RRF) only) to compare with/without expansion — the existing `test_size`/`mechanisms` parameterization and fixed-seed sampling extend cleanly; likely wants a `use_query_expansion` flag threaded through `EvaluationEngine`/`LLMQueryLayer`.
- Given the hang pattern above, Phase 9's (much smaller, 10-question) evaluation run should be comparatively quick and less likely to hit this issue — but the resume workflow is proven and ready if needed.
