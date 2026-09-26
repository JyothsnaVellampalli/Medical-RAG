"""Ground-truth IR metrics: pure computation, no LLM calls. Compares retrieved
hf_row_ids against a question's known relevant_passage_ids from the HF dataset.
"""

import math


def precision_at_k(retrieved_ids: list[int], relevant_ids: set[int]) -> float:
    if not retrieved_ids:
        return 0.0
    hits = sum(1 for rid in retrieved_ids if rid in relevant_ids)
    return hits / len(retrieved_ids)


def recall_at_k(retrieved_ids: list[int], relevant_ids: set[int]) -> float:
    if not relevant_ids:
        return 0.0
    hits = sum(1 for rid in retrieved_ids if rid in relevant_ids)
    return hits / len(relevant_ids)


def reciprocal_rank(retrieved_ids: list[int], relevant_ids: set[int]) -> float:
    for rank, rid in enumerate(retrieved_ids, start=1):
        if rid in relevant_ids:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved_ids: list[int], relevant_ids: set[int]) -> float:
    if not retrieved_ids or not relevant_ids:
        return 0.0
    dcg = sum(
        (1.0 if rid in relevant_ids else 0.0) / math.log2(rank + 1)
        for rank, rid in enumerate(retrieved_ids, start=1)
    )
    ideal_hits = min(len(retrieved_ids), len(relevant_ids))
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg if idcg > 0 else 0.0


def compute_ir_metrics(retrieved_ids: list[int], relevant_ids: set[int]) -> dict[str, float]:
    return {
        "precision_at_k": precision_at_k(retrieved_ids, relevant_ids),
        "recall_at_k": recall_at_k(retrieved_ids, relevant_ids),
        "mrr": reciprocal_rank(retrieved_ids, relevant_ids),
        "ndcg_at_k": ndcg_at_k(retrieved_ids, relevant_ids),
    }
