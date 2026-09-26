import threading
import time
from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg
from elastic_transport import ConnectionError as ESConnectionError
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from DataStore.elastic_search_store import store
from Evaluation.evaluation_engine import evaluation_engine
from Evaluation.evaluation_store import evaluation_store
from Evaluation.query_evaluation_store import query_evaluation_store
from Evaluation.semantic_metrics import answer_relevancy, faithfulness
from LLM.llm_query_layer import llm_query_layer
from logger import get_logger
from Retrieval.retrieval_registry import retrieval_registry

log = get_logger(__name__)

router = APIRouter()


class ChunkResult(BaseModel):
    chunk_id: str
    hf_row_id: int
    text: str
    chunk_index: int


class RetrieveResult(BaseModel):
    chunk_id: str
    hf_row_id: int
    text: str
    chunk_index: int
    score: float


class RetrieveRequest(BaseModel):
    search_type: str
    query: str
    weight: float | None = None


class QueryRequest(BaseModel):
    search_type: str
    query: str
    weight: float | None = None
    evaluation: bool = False


class QueryResponse(BaseModel):
    response: str
    citations: list[RetrieveResult]
    latency_seconds: float
    evaluation_id: UUID | None = None


class QueryEvaluationStatus(BaseModel):
    state: str
    faithfulness: float | None = None
    answer_relevancy: float | None = None
    error: str | None = None


class EvaluateRequest(BaseModel):
    mechanisms: list[str]
    test_size: int = 100


class EvaluateResponse(BaseModel):
    job_id: UUID
    state: str


class MechanismMetrics(BaseModel):
    retrieval_mechanism: str
    num_questions: int
    avg_precision_at_k: float | None
    avg_recall_at_k: float | None
    avg_mrr: float | None
    avg_ndcg_at_k: float | None
    avg_faithfulness: float | None
    avg_answer_relevancy: float | None
    avg_answer_correctness: float | None
    avg_latency_seconds: float | None
    error_count: int


class EvalJob(BaseModel):
    job_id: UUID
    mechanisms: list[str]
    test_size: int
    state: str
    started_at: datetime
    completed_at: datetime | None
    metrics: list[MechanismMetrics]


class EvalResultDetail(BaseModel):
    hf_qa_id: int
    retrieval_mechanism: str
    question: str
    precision_at_k: float | None
    recall_at_k: float | None
    mrr: float | None
    ndcg_at_k: float | None
    faithfulness: float | None
    answer_relevancy: float | None
    answer_correctness: float | None
    latency_seconds: float | None
    error: str | None


@router.get("/health")
def health() -> dict[str, str]:
    log.info("[API] GET /health - requested")
    log.info("[API] GET /health - ok")
    return {"status": "ok"}


@router.get("/get_chunks", response_model=list[ChunkResult])
def get_chunks() -> list[dict[str, Any]]:
    log.info("[API] GET /get_chunks - requested")
    try:
        result = store.search_data(
            {"query": {"match_all": {}}, "sort": [{"hf_row_id": "asc"}]},
            size=10,
        )
    except ESConnectionError as e:
        log.error("[API] GET /get_chunks - Elasticsearch unavailable: %s", e)
        raise HTTPException(status_code=503, detail="Elasticsearch is unavailable") from e
    chunks = [hit["_source"] for hit in result["hits"]["hits"]]
    log.info("[API] GET /get_chunks - returned %d chunk(s)", len(chunks))
    return chunks


@router.post("/retrieve", response_model=list[RetrieveResult])
def retrieve(payload: RetrieveRequest) -> list[dict[str, Any]]:
    log.info("[API] POST /retrieve - strategy=%s query=%r", payload.search_type, payload.query)
    try:
        results = retrieval_registry.retrieve(
            strategy=payload.search_type,
            query_text=payload.query,
            weight=payload.weight if payload.weight is not None else 0.5,
        )
    except ValueError as e:
        log.error("[API] POST /retrieve - invalid request: %s", e)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ESConnectionError as e:
        log.error("[API] POST /retrieve - Elasticsearch unavailable: %s", e)
        raise HTTPException(status_code=503, detail="Elasticsearch is unavailable") from e
    log.info("[API] POST /retrieve - returned %d result(s)", len(results))
    return results


def _run_query_evaluation(
    evaluation_id: UUID, query_text: str, response_text: str, contexts: list[str]
) -> None:
    log.info("[Eval] evaluation_id=%s - computing faithfulness/answer_relevancy", evaluation_id)
    try:
        score_faithfulness = faithfulness(response_text, contexts)
        score_answer_relevancy = answer_relevancy(query_text, response_text)
        query_evaluation_store.set_done(evaluation_id, score_faithfulness, score_answer_relevancy)
        log.info(
            "[Eval] evaluation_id=%s - done: faithfulness=%.4f answer_relevancy=%.4f",
            evaluation_id,
            score_faithfulness,
            score_answer_relevancy,
        )
    except Exception as e:
        log.error("[Eval] evaluation_id=%s - failed: %s", evaluation_id, e)
        query_evaluation_store.set_error(evaluation_id, f"{type(e).__name__}: {e}")


@router.post("/query", response_model=QueryResponse)
def query(payload: QueryRequest) -> dict[str, Any]:
    log.info(
        "[API] POST /query - strategy=%s query=%r evaluation=%s",
        payload.search_type,
        payload.query,
        payload.evaluation,
    )
    start = time.monotonic()
    try:
        result = llm_query_layer.query(
            search_type=payload.search_type,
            query_text=payload.query,
            weight=payload.weight if payload.weight is not None else 0.5,
        )
    except ValueError as e:
        log.error("[API] POST /query - invalid request: %s", e)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ESConnectionError as e:
        log.error("[API] POST /query - Elasticsearch unavailable: %s", e)
        raise HTTPException(status_code=503, detail="Elasticsearch is unavailable") from e
    except ConnectionError as e:
        log.error("[API] POST /query - Ollama unavailable: %s", e)
        raise HTTPException(status_code=503, detail="LLM (Ollama) is unavailable") from e
    result["latency_seconds"] = time.monotonic() - start
    log.info(
        "[API] POST /query - answered with %d citation(s) in %.2fs",
        len(result["citations"]),
        result["latency_seconds"],
    )

    result["evaluation_id"] = None
    if payload.evaluation:
        evaluation_id = query_evaluation_store.create_pending()
        contexts = [c["text"] for c in result["citations"]]
        thread = threading.Thread(
            target=_run_query_evaluation,
            args=(evaluation_id, payload.query, result["response"], contexts),
            daemon=True,
        )
        thread.start()
        result["evaluation_id"] = evaluation_id
        log.info("[API] POST /query - started background evaluation %s", evaluation_id)

    return result


@router.get("/get_query_evaluation/{evaluation_id}", response_model=QueryEvaluationStatus)
def get_query_evaluation(evaluation_id: UUID) -> dict[str, Any]:
    log.info("[API] GET /get_query_evaluation/%s - requested", evaluation_id)
    record = query_evaluation_store.get(evaluation_id)
    if record is None:
        log.error("[API] GET /get_query_evaluation/%s - not found", evaluation_id)
        raise HTTPException(status_code=404, detail="Unknown evaluation_id")
    log.info("[API] GET /get_query_evaluation/%s - state=%s", evaluation_id, record.state)
    return {
        "state": record.state,
        "faithfulness": record.faithfulness,
        "answer_relevancy": record.answer_relevancy,
        "error": record.error,
    }


@router.post("/evaluate", response_model=EvaluateResponse)
def evaluate(payload: EvaluateRequest) -> dict[str, Any]:
    log.info(
        "[API] POST /evaluate - mechanisms=%s test_size=%d", payload.mechanisms, payload.test_size
    )
    valid = {"bm25", "semantic", "hybrid_weighted", "hybrid_rrf"}
    unknown = set(payload.mechanisms) - valid
    if unknown:
        log.error("[API] POST /evaluate - unknown mechanism(s): %s", sorted(unknown))
        raise HTTPException(status_code=400, detail=f"Unknown mechanism(s): {sorted(unknown)}")
    try:
        job_id = evaluation_engine.start_job(payload.mechanisms, payload.test_size)
    except psycopg.OperationalError as e:
        log.error("[API] POST /evaluate - Supabase/Postgres unavailable: %s", e)
        raise HTTPException(status_code=503, detail="Evaluation database is unavailable") from e
    log.info("[API] POST /evaluate - started job %s", job_id)
    return {"job_id": job_id, "state": "Progress"}


@router.get("/get_evals", response_model=list[EvalJob])
def get_evals() -> list[dict[str, Any]]:
    log.info("[API] GET /get_evals - requested")
    try:
        jobs = evaluation_store.get_jobs()
        for job in jobs:
            job["metrics"] = evaluation_store.get_job_metrics(job["job_id"])
    except psycopg.OperationalError as e:
        log.error("[API] GET /get_evals - Supabase/Postgres unavailable: %s", e)
        raise HTTPException(status_code=503, detail="Evaluation database is unavailable") from e
    log.info("[API] GET /get_evals - returned %d job(s)", len(jobs))
    return jobs


@router.get("/get_evals/{job_id}/results", response_model=list[EvalResultDetail])
def get_eval_results(job_id: UUID) -> list[dict[str, Any]]:
    log.info("[API] GET /get_evals/%s/results - requested", job_id)
    try:
        results = evaluation_store.get_job_results(job_id)
    except psycopg.OperationalError as e:
        log.error("[API] GET /get_evals/%s/results - Supabase/Postgres unavailable: %s", job_id, e)
        raise HTTPException(status_code=503, detail="Evaluation database is unavailable") from e
    log.info("[API] GET /get_evals/%s/results - returned %d result(s)", job_id, len(results))
    return results
