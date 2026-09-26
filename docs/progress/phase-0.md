# Phase 0: Project skeleton
Status: done   Date: 2026-09-22

## What was built
A FastAPI backend and a React+TypeScript (Vite) frontend that can talk to each other, plus a docker-compose file for the Elasticsearch container that later phases will use. The backend exposes a temporary `/health` endpoint (to be replaced by the real APIs in Phase 5); the frontend has a landing page that calls it on load and shows a live connection status.

## Files created / changed
- `backend/config.py`: single `Settings` class (pydantic-settings) reading `backend/.env`, with defaults set in code. Holds dataset, embedding (`embedding_model`, `embedding_dim`), Elasticsearch, and CORS config. No embedding API/URL field — Phase 2 embeds locally via `sentence-transformers`.
- `backend/logger.py`: shared `get_logger(name)` helper, INFO/ERROR logging to stdout — every future layer should use this instead of ad-hoc logging.
- `backend/main.py`: FastAPI app, CORS middleware allowing the frontend origin, lifespan startup/shutdown logs.
- `backend/routes.py`: `GET /health` endpoint.
- `backend/requirements.txt`: fastapi, uvicorn, pydantic-settings, python-dotenv.
- `backend/.env` / `backend/.env.example`: moved from repo root; added `ELASTICSEARCH_URL`, `ELASTICSEARCH_INDEX`, `FRONTEND_ORIGIN`.
- `docker-compose.yml`: single-node Elasticsearch 8.15.3, port 9200, security disabled for local dev, named volume `esdata`.
- `frontend/`: scaffolded with Vite (`react-ts` template).
  - `src/api/client.ts`: fetch wrapper; only module in the frontend allowed to call the backend (per CLAUDE.md rule: no business logic / raw fetches in UI components).
  - `src/Pages/Landing/Landing.tsx` + `.css`: landing page, calls `checkHealth()`, shows checking/connected/disconnected status.
  - `src/App.tsx`: `react-router-dom` `BrowserRouter` with the landing route (more routes added in Phase 6).
  - `eslint.config.js`: replaced the Vite template's default `oxlint` with real ESLint (flat config, typescript-eslint + react-hooks + react-refresh) per CLAUDE.md's explicit ESLint requirement.
  - `vite.config.ts`: dev server pinned to port 3000.
  - `.env` / `.env.example`: `VITE_API_BASE_URL=http://localhost:8000`.
- Root `.gitignore`: excludes `.venv`, `__pycache__`, `.mypy_cache`, `node_modules`, `dist`, `**/.env` (but not `.env.example`), `esdata/`.

## Key decisions and why
- **Python 3.14 instead of 3.12**: CLAUDE.md pins 3.12, but only 3.14 is installed on this machine and the user approved proceeding with 3.14 rather than installing 3.12. Flagging here in case a 3.12-only dependency shows up in a later phase.
- **No pytest**: user asked to skip automated backend tests for now and rely on manual verification (run the server, hit the endpoint). The `/health` endpoint itself is scaffolding for this and should be removed once Phase 5's real APIs exist to serve as connectivity checks.
- **.env split per app** (`backend/.env`, `frontend/.env`) instead of one root `.env`, matching `docs/Architecture.md`'s folder diagram. User confirmed this over keeping a single root file.
- **Vite over Create React App**: CRA is deprecated upstream; user approved Vite.
- **Swapped oxlint for ESLint**: the current Vite React-TS template defaults to `oxlint`, but CLAUDE.md explicitly requires ESLint, so it was removed and replaced with a flat ESLint config.
- **No placeholder subfolders** for `DataStore`/`Embedding`/`Chunking`/`Retrieval` (backend) or `CommonComponents`/`Chunk`/`Retrieve`/`Evaluate` pages (frontend) yet — empty dirs aren't tracked by git and add no value until their phase adds real files.
- **No `embedding_api` field**: originally added for an OpenAI-compatible embedding endpoint, but the user updated Phase 2's roadmap goal to embed locally via `sentence-transformers.SentenceTransformer` instead, so the field was removed as dead config.
- **`embedding_dim` sourced from `.env`** (not hardcoded-only as originally read from the CLAUDE.md stack line): the user added `EMBEDDING_DIM` to `.env` when switching to a `nomic-ai/nomic-embed-text-v1.5` embedding model (dim 512, via Matryoshka truncation), so the field is now `.env`-overridable with a `384` code default, consistent with how every other setting behaves.
- **Fixed a `Settings()` crash**: pydantic-settings raises `extra_forbidden` and fails the *entire* settings object if any `.env` key doesn't match a field name (it doesn't silently ignore unknown keys) — this happened when `EMBEDDING_DIM` was added to `.env` before the field existed in code, and looked like ".env values aren't being read" when actually nothing loaded at all. Also removed a leftover debug `print()` in `config.py`. Lesson for future phases: keep `.env` keys and `Settings` field names in exact sync (case-insensitive), or the app won't start.

## How to run / test
- Backend: `cd backend && .venv\Scripts\python -m uvicorn main:app --port 8000` → `GET http://localhost:8000/health` returns `{"status":"ok"}`.
- Frontend: `cd frontend && npm run dev` → served on `http://localhost:3000`.
- Elasticsearch: `docker compose up -d` (Docker Desktop was not running on this machine during Phase 0, so the compose file was syntax-validated with `docker compose config` but the container was not actually started — **please run `docker compose up -d` yourself and confirm `curl http://localhost:9200` responds** before Phase 1 needs it).
- Verified together: both servers started, `curl -H "Origin: http://localhost:3000" http://localhost:8000/health` showed correct CORS headers, and a headless-browser screenshot of `http://localhost:3000` confirmed the landing page renders "Med RAG Lab" with a "Backend: connected" status (no console errors).
- Lint: `cd frontend && npm run lint` — clean.
- Type-check: `cd backend && .venv\Scripts\python -m mypy config.py logger.py routes.py main.py --strict` — clean. `cd frontend && npm run build` (runs `tsc -b`) — clean.

## Known issues / tech debt
- Elasticsearch container not actually verified running (Docker Desktop was off during this phase) — verify before Phase 1.
- Python 3.12 (CLAUDE.md) vs 3.14 (installed) mismatch — watch for compatibility issues with sentence-transformers or the Elasticsearch client in later phases.
- `/health` is temporary; remove once Phase 5 ships real APIs.

## Notes for next phase
- Phase 1 adds `backend/DataStore/elastic_search_store.py` with an `ElasticSearchStore` class (create index / index data / search data), using `settings.elasticsearch_url` and `settings.elasticsearch_index` from `config.py`, and `get_logger(__name__)` from `logger.py` for logging.
- Data model for the index is in `docs/Architecture.md` (`chunk_id`, `hf_row_id`, `text`, `embedding`, `chunk_index`).
- Elasticsearch client library isn't installed yet — add `elasticsearch` to `backend/requirements.txt` in Phase 1.
