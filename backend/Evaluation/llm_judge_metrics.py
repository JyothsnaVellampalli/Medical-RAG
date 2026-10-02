"""LLM-judge-based answer-quality metrics via OpenRouter's typesafe/jev-1.13
"decisions" model -- a structured scoring/classification model (not a chat
model), prompted with a "score" question per metric on an ordered 0..N scale
and normalized to 0.0-1.0 to match semantic_metrics.py's scale.

Added alongside (not replacing) semantic_metrics.py's embedding-based
faithfulness/answer_relevancy: this project's earlier decision to drop a
judge model entirely (see architecture.md) was driven by local hardware
limits -- an 8GB-RAM machine OOMing on a local judge model. OpenRouter moves
judging off this machine entirely, so that constraint no longer applies here;
the embedding-based metrics stay as-is since they're already proven reliable.

jev-1.13 (unlike typesafe/jev-router, tried first -- see architecture.md) is
purpose-built for exactly this kind of structured scoring task: it costs
less than a routed chat completion and needs no natural-language generation
or JSON-parsing of free text, since the decisions API returns a typed score
directly. Verified live against a real question/context/answer triple.
"""

from typing import Any

from config import settings
from logger import get_logger
from openrouter_client import decision

log = get_logger(__name__)

JUDGE_TIMEOUT_SECONDS = 60.0

FAITHFULNESS_CRITERIA = [
    "Completely unsupported: the answer contradicts or has no basis in the context passages.",
    "Mostly unsupported: the answer includes significant claims not found in the context passages.",
    "Partially supported: the answer mixes claims supported by the context with some that are not.",
    "Mostly supported: the answer is largely grounded in the context with minor unsupported details.",
    "Fully supported: every claim in the answer is directly supported by the context passages.",
]

ANSWER_RELEVANCY_CRITERIA = [
    "Not relevant: the answer does not address the question at all.",
    "Barely relevant: the answer touches the topic but mostly misses the question.",
    "Partially relevant: the answer addresses part of the question.",
    "Mostly relevant: the answer addresses the question with minor gaps.",
    "Fully relevant: the answer directly and completely addresses the question asked.",
]


def _normalized_score(answers: dict[str, Any], question_id: str, num_levels: int) -> float:
    raw_score = float(answers[question_id]["score"])
    return raw_score / (num_levels - 1)


def judge_metrics(question: str, answer: str, contexts: list[str]) -> dict[str, float]:
    state = {
        "question": question,
        "context_passages": contexts,
        "generated_answer": answer,
    }
    questions = {
        "faithfulness": {
            "type": "score",
            "instructions": (
                "How faithful is the generated answer to the context passages -- "
                "does it only state things supported by them?"
            ),
            "criteria": FAITHFULNESS_CRITERIA,
        },
        "answer_relevancy": {
            "type": "score",
            "instructions": "How relevant is the generated answer to the question asked?",
            "criteria": ANSWER_RELEVANCY_CRITERIA,
        },
    }

    log.info("[Judge] scoring via OpenRouter decisions API (model=%s)", settings.open_router_judge_model)
    answers = decision(
        model=settings.open_router_judge_model,
        state=state,
        questions=questions,
        timeout=JUDGE_TIMEOUT_SECONDS,
    )
    return {
        "judge_faithfulness": _normalized_score(answers, "faithfulness", len(FAITHFULNESS_CRITERIA)),
        "judge_answer_relevancy": _normalized_score(
            answers, "answer_relevancy", len(ANSWER_RELEVANCY_CRITERIA)
        ),
    }
