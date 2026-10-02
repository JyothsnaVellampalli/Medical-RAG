"""Reranking layer: reorders retrieved chunks by relevance to the query
using OpenRouter's typesafe/jev-1.13 decisions model (the same model and
API Evaluation.llm_judge_metrics uses for judging -- see architecture.md).

One decisions call scores every retrieved chunk at once (one named "score"
question per chunk), rather than one call per chunk -- the decisions API
supports multiple questions per request, which is both faster and cheaper
than N separate calls.

Chunks' own `score` field (the retrieval mechanism's own ranking score) is
left untouched -- only the list order changes. Citations in the API response
reflect whatever order was actually fed to the LLM, same invariant as
Phase 7's "citations are exactly the chunks in the prompt".
"""

from typing import Any

from config import settings
from logger import get_logger
from openrouter_client import decision

log = get_logger(__name__)

RERANK_TIMEOUT_SECONDS = 60.0

RELEVANCE_CRITERIA = [
    "Not relevant: this passage has nothing to do with the question.",
    "Barely relevant: this passage touches the general topic but doesn't help answer the question.",
    "Partially relevant: this passage is related and partly useful for answering the question.",
    "Mostly relevant: this passage is clearly useful for answering the question, with minor gaps.",
    "Highly relevant: this passage directly and substantially helps answer the question.",
]


class Reranker:
    def rerank(self, query_text: str, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not chunks:
            return chunks

        state = {
            "question": query_text,
            "passages": {f"passage_{i}": c["text"] for i, c in enumerate(chunks)},
        }
        questions = {
            f"relevance_{i}": {
                "type": "score",
                "instructions": f"How relevant is passage_{i} to answering the question?",
                "criteria": RELEVANCE_CRITERIA,
            }
            for i in range(len(chunks))
        }

        log.info(
            "Reranking %d chunk(s) via OpenRouter decisions API (model=%s)",
            len(chunks),
            settings.open_router_judge_model,
        )
        answers = decision(
            model=settings.open_router_judge_model,
            state=state,
            questions=questions,
            timeout=RERANK_TIMEOUT_SECONDS,
        )
        scores = [float(answers[f"relevance_{i}"]["score"]) for i in range(len(chunks))]
        ranked = sorted(zip(chunks, scores), key=lambda pair: pair[1], reverse=True)
        log.info("Reranked chunk order (by relevance score): %s", [round(s, 2) for _, s in ranked])
        return [chunk for chunk, _ in ranked]


reranker = Reranker()
