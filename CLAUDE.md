## Med RAG Lab
A RAG system over a Hugging Face medical dataset whose purpose is to COMPARE retrieval mechanisms (dense, keyword/FTS, hybrid, grep, ...). Chunking is fixed: paragraph chunking only.


## Stack
Python 3.14, pip + venv, mypy, FastAPI
Embeddings: local model via sentence-transformers (model name in .env, dimension in config)
Database: Elastic search running in my local docker container
UI: React js with typescript, plain CSS, ESLint
Dataset: Hugging Face dataset - rag-datasets/rag-mini-bioasq


## Non-negotiable rules
1. Follow SOLID principles, maintain clean abstraction layers for each functionality.
Example: If a new retrieval mechanism is integrated, I will need to just add a new line in the retrieval registry class that connects the corresponding file that actually handles the retrieval process.
2. No business logics in the UI/. UI calls backend apis only through client.ts
3. Maintain the logs that helps to monitor the flow and also debug if something goes wrong. Log types: Information, Error logs.
4. No secrets in the code. Read secrets from .env from one config.py where the defaults for the env variables will be set.


## Workflow
- Work on one phase at a time. Refer docs/Roadmap.md and work on first unchecked phase.
- Before coding: read the docs listed below for that phase, propose a short plan, WAIT for approval.
- Ask if the requirements is unclear, do not assume.
- Run lint and tests for every phase.
- When the phase's "Done when" is met: STOP, refer docs/progress/template.md and write docs/progress/phase-XX.md, tick that phase in docs/Roadmap.md
- DO NOT start next phase with out asking for it.


## Read on demand (not every session)
- Architecture / DB schema / layers: `docs/architecture.md`
- Past work / debugging context: `docs/progress/`