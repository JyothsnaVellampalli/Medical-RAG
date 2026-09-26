"""Evaluation persistence layer, backed by the Supabase Postgres container
(separate from Elasticsearch, which only stores the retrievable corpus).
Owns the schema and generic CRUD for evaluation jobs and per-question results.
"""

from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from config import settings
from logger import get_logger

log = get_logger(__name__)

CREATE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS eval_jobs (
    job_id UUID PRIMARY KEY,
    mechanisms TEXT[] NOT NULL,
    test_size INTEGER NOT NULL,
    state TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS eval_results (
    id SERIAL PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES eval_jobs(job_id),
    hf_qa_id INTEGER NOT NULL,
    retrieval_mechanism TEXT NOT NULL,
    question TEXT NOT NULL,
    ground_truth_answer TEXT NOT NULL,
    generated_answer TEXT,
    precision_at_k DOUBLE PRECISION,
    recall_at_k DOUBLE PRECISION,
    mrr DOUBLE PRECISION,
    ndcg_at_k DOUBLE PRECISION,
    faithfulness DOUBLE PRECISION,
    answer_relevancy DOUBLE PRECISION,
    answer_correctness DOUBLE PRECISION,
    latency_seconds DOUBLE PRECISION,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


class EvaluationStore:
    def _connect(self) -> psycopg.Connection[Any]:
        return psycopg.connect(settings.supabase_db_url, row_factory=dict_row)

    def create_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(CREATE_SCHEMA_SQL)
        log.info("Evaluation schema ensured (eval_jobs, eval_results)")

    def create_job(self, job_id: UUID, mechanisms: list[str], test_size: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO eval_jobs (job_id, mechanisms, test_size, state) "
                "VALUES (%s, %s, %s, 'Progress')",
                (job_id, mechanisms, test_size),
            )
        log.info("Created eval job %s (mechanisms=%s, test_size=%d)", job_id, mechanisms, test_size)

    def update_job_state(self, job_id: UUID, state: str, completed: bool = False) -> None:
        with self._connect() as conn:
            if completed:
                conn.execute(
                    "UPDATE eval_jobs SET state = %s, completed_at = now() WHERE job_id = %s",
                    (state, job_id),
                )
            else:
                conn.execute(
                    "UPDATE eval_jobs SET state = %s WHERE job_id = %s",
                    (state, job_id),
                )
        log.info("Eval job %s -> %s", job_id, state)

    def insert_result(self, row: dict[str, Any]) -> None:
        columns = list(row.keys())
        placeholders = ", ".join(["%s"] * len(columns))
        column_list = ", ".join(columns)
        with self._connect() as conn:
            conn.execute(
                f"INSERT INTO eval_results ({column_list}) VALUES ({placeholders})",
                [row[c] for c in columns],
            )
        log.info(
            "Recorded eval result: job=%s hf_qa_id=%s mechanism=%s error=%s",
            row.get("job_id"),
            row.get("hf_qa_id"),
            row.get("retrieval_mechanism"),
            row.get("error"),
        )

    def get_jobs(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT job_id, mechanisms, test_size, state, started_at, completed_at "
                "FROM eval_jobs ORDER BY started_at DESC"
            ).fetchall()
        return list(rows)

    def get_job_metrics(self, job_id: UUID) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    retrieval_mechanism,
                    count(*) AS num_questions,
                    avg(precision_at_k) AS avg_precision_at_k,
                    avg(recall_at_k) AS avg_recall_at_k,
                    avg(mrr) AS avg_mrr,
                    avg(ndcg_at_k) AS avg_ndcg_at_k,
                    avg(faithfulness) AS avg_faithfulness,
                    avg(answer_relevancy) AS avg_answer_relevancy,
                    avg(answer_correctness) AS avg_answer_correctness,
                    avg(latency_seconds) AS avg_latency_seconds,
                    count(*) FILTER (WHERE error IS NOT NULL) AS error_count
                FROM eval_results
                WHERE job_id = %s
                GROUP BY retrieval_mechanism
                """,
                (job_id,),
            ).fetchall()
        return list(rows)

    def get_job_results(self, job_id: UUID) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM eval_results WHERE job_id = %s ORDER BY id", (job_id,)
            ).fetchall()
        return list(rows)


evaluation_store = EvaluationStore()
