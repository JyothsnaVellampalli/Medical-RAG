"""In-memory store for ad-hoc, per-query evaluation results (Ask page).

Separate from EvaluationStore (Supabase Postgres), which persists benchmark
evaluation runs against the HF QA dataset for cross-run comparison. Ask-page
evaluations are one-off and tied to a single response the user is looking at
right now -- there's nothing worth persisting past the session, so a plain
thread-safe dict is enough.
"""

import threading
from dataclasses import dataclass
from typing import Literal
from uuid import UUID, uuid4

QueryEvaluationState = Literal["Progress", "Done", "Error"]


@dataclass
class QueryEvaluationRecord:
    state: QueryEvaluationState = "Progress"
    faithfulness: float | None = None
    answer_relevancy: float | None = None
    error: str | None = None
    # LLM-judge (OpenRouter) scores -- independent of the embedding-based
    # fields above since the two are computed by separate calls that can
    # succeed/fail independently.
    judge_state: QueryEvaluationState = "Progress"
    judge_faithfulness: float | None = None
    judge_answer_relevancy: float | None = None
    judge_error: str | None = None


class QueryEvaluationStore:
    def __init__(self) -> None:
        self._records: dict[UUID, QueryEvaluationRecord] = {}
        self._lock = threading.Lock()

    def create_pending(self) -> UUID:
        evaluation_id = uuid4()
        with self._lock:
            self._records[evaluation_id] = QueryEvaluationRecord()
        return evaluation_id

    def set_done(self, evaluation_id: UUID, faithfulness: float, answer_relevancy: float) -> None:
        with self._lock:
            record = self._records[evaluation_id]
            record.state = "Done"
            record.faithfulness = faithfulness
            record.answer_relevancy = answer_relevancy

    def set_error(self, evaluation_id: UUID, error: str) -> None:
        with self._lock:
            record = self._records[evaluation_id]
            record.state = "Error"
            record.error = error

    def set_judge_done(
        self, evaluation_id: UUID, judge_faithfulness: float, judge_answer_relevancy: float
    ) -> None:
        with self._lock:
            record = self._records[evaluation_id]
            record.judge_state = "Done"
            record.judge_faithfulness = judge_faithfulness
            record.judge_answer_relevancy = judge_answer_relevancy

    def set_judge_error(self, evaluation_id: UUID, error: str) -> None:
        with self._lock:
            record = self._records[evaluation_id]
            record.judge_state = "Error"
            record.judge_error = error

    def get(self, evaluation_id: UUID) -> QueryEvaluationRecord | None:
        with self._lock:
            return self._records.get(evaluation_id)


query_evaluation_store = QueryEvaluationStore()
