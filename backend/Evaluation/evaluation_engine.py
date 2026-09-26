"""Evaluation engine: orchestrates the full test_size x mechanism evaluation
loop -- retrieval+generation via LLMQueryLayer, IR metrics and semantic
metrics both computed against ground truth (no judge LLM involved anywhere),
latency, and per-question error handling. Runs as a background daemon thread
(not FastAPI's BackgroundTasks, which shares the request threadpool) so it
doesn't block the API server for what can be a very long job.

Resumable like Chunking.ChunkingEngine.ingest(): re-running resume_job(job_id)
skips (question, mechanism) pairs already scored, so a session-restart-killed
job (a real, repeated occurrence in this project) costs wall-clock time only.
"""

import json
import random
import threading
import time
import traceback
from typing import Any
from uuid import UUID, uuid4

from datasets import load_dataset

from config import settings
from Evaluation.evaluation_store import evaluation_store
from Evaluation.ir_metrics import compute_ir_metrics
from Evaluation.semantic_metrics import compute_semantic_metrics
from LLM.llm_query_layer import llm_query_layer
from logger import get_logger

log = get_logger(__name__)


class EvaluationEngine:
    def _load_test_questions(self, test_size: int) -> list[dict[str, Any]]:
        log.info("Loading %d test question(s) (seed=%d)", test_size, settings.eval_random_seed)
        dataset = load_dataset(
            settings.hugging_face_dataset,
            settings.eval_question_answer_split,
            split=settings.eval_test_split,
        )
        rng = random.Random(settings.eval_random_seed)
        indices = sorted(rng.sample(range(len(dataset)), min(test_size, len(dataset))))
        rows = []
        for i in indices:
            row = dict(dataset[i])
            row["relevant_passage_ids"] = set(json.loads(row["relevant_passage_ids"]))
            rows.append(row)
        log.info("Loaded %d test question(s)", len(rows))
        return rows

    def _already_scored(self, job_id: UUID) -> set[tuple[int, str]]:
        results = evaluation_store.get_job_results(job_id)
        return {(r["hf_qa_id"], r["retrieval_mechanism"]) for r in results}

    def _evaluate_one(self, job_id: UUID, mechanism: str, row: dict[str, Any]) -> None:
        start = time.monotonic()
        result_row: dict[str, Any] = {
            "job_id": job_id,
            "hf_qa_id": row["id"],
            "retrieval_mechanism": mechanism,
            "question": row["question"],
            "ground_truth_answer": row["answer"],
            "generated_answer": None,
            "precision_at_k": None,
            "recall_at_k": None,
            "mrr": None,
            "ndcg_at_k": None,
            "faithfulness": None,
            "answer_relevancy": None,
            "answer_correctness": None,
            "latency_seconds": None,
            "error": None,
        }
        log.info("Evaluating hf_qa_id=%s mechanism=%s", row["id"], mechanism)
        try:
            pipeline_result = llm_query_layer.query(search_type=mechanism, query_text=row["question"])
            latency = time.monotonic() - start
            citations = pipeline_result["citations"]
            retrieved_ids = [c["hf_row_id"] for c in citations]
            contexts = [c["text"] for c in citations]
            answer = pipeline_result["response"]

            ir = compute_ir_metrics(retrieved_ids, row["relevant_passage_ids"])
            semantic = compute_semantic_metrics(row["question"], answer, contexts, row["answer"])

            result_row["generated_answer"] = answer
            result_row["latency_seconds"] = latency
            result_row.update(ir)
            result_row.update(semantic)
            log.info(
                "Scored hf_qa_id=%s mechanism=%s precision_at_k=%.3f faithfulness=%.3f "
                "answer_correctness=%.3f latency=%.1fs",
                row["id"],
                mechanism,
                ir["precision_at_k"],
                semantic["faithfulness"],
                semantic["answer_correctness"],
                latency,
            )
        except Exception as e:
            result_row["latency_seconds"] = time.monotonic() - start
            result_row["error"] = f"{type(e).__name__}: {e}"
            log.error("Eval failed for hf_qa_id=%s mechanism=%s: %s", row["id"], mechanism, e)

        evaluation_store.insert_result(result_row)

    def _run(self, job_id: UUID, mechanisms: list[str], test_size: int) -> None:
        try:
            rows = self._load_test_questions(test_size)
            done = self._already_scored(job_id)
            total = len(mechanisms) * len(rows)
            completed = len(done)
            log.info("Eval job %s: %d/%d already done, resuming", job_id, completed, total)

            for mechanism in mechanisms:
                for row in rows:
                    if (row["id"], mechanism) in done:
                        continue
                    self._evaluate_one(job_id, mechanism, row)
                    completed += 1
                    log.info("Eval job %s progress: %d/%d", job_id, completed, total)

            log.info("Eval job %s finished: %d/%d scored -> Done", job_id, completed, total)
            evaluation_store.update_job_state(job_id, "Done", completed=True)
        except Exception:
            log.error("Eval job %s crashed:\n%s", job_id, traceback.format_exc())
            evaluation_store.update_job_state(job_id, "Stopped", completed=True)

    def start_job(self, mechanisms: list[str], test_size: int = 100) -> UUID:
        job_id = uuid4()
        evaluation_store.create_schema()
        evaluation_store.create_job(job_id, mechanisms, test_size)
        thread = threading.Thread(target=self._run, args=(job_id, mechanisms, test_size), daemon=True)
        thread.start()
        log.info("Started eval job %s in background thread", job_id)
        return job_id

    def resume_job(self, job_id: UUID) -> None:
        job = next((j for j in evaluation_store.get_jobs() if j["job_id"] == job_id), None)
        if job is None:
            raise ValueError(f"No such job: {job_id}")
        thread = threading.Thread(
            target=self._run, args=(job_id, job["mechanisms"], job["test_size"]), daemon=True
        )
        thread.start()
        log.info("Resumed eval job %s in background thread", job_id)


evaluation_engine = EvaluationEngine()
