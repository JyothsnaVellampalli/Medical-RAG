"""RAGAS-inspired answer-quality metrics computed via embedding similarity
only -- no judge LLM. Originally these were implemented as LLM-judged
metrics (faithfulness/relevancy/context precision/recall via qwen2.5),
but that approach had two real problems on this machine: the judge model's
memory footprint conflicted with the generator model's (this machine has
only 8GB RAM, Docker's WSL2 VM caps at 3.7GB), and a small enough judge
model to fit reliably misjudged clearly-relevant content in testing.

Since this project evaluates against a QA dataset with known-correct
answers (unlike most RAGAS use cases, which assume no ground truth),
direct embedding comparison against that ground truth is both simpler and
more reliable than asking an LLM to guess. Context precision/recall are not
reimplemented here -- Evaluation.ir_metrics already covers that ground truth
comparison (retrieved hf_row_ids vs relevant_passage_ids) without needing
embeddings or an LLM either.
"""

from Embedding.embedding_provider import embedding_provider
from logger import get_logger

log = get_logger(__name__)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = float(sum(x * y for x, y in zip(a, b)))
    norm_a = float(sum(x * x for x in a)) ** 0.5
    norm_b = float(sum(y * y for y in b)) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def faithfulness(answer: str, contexts: list[str]) -> float:
    """Max cosine similarity between the answer and any single retrieved
    context chunk. Max (not average) so noisy/irrelevant chunks retrieved
    alongside a genuinely relevant one don't unfairly drag this down --
    that's what the IR metrics already measure, not generation faithfulness.
    Mirrors the corpus's own query/document embedding asymmetry: contexts
    were indexed with embed() (document-side), so re-embedding them the same
    way here keeps this comparable to how retrieval itself scores them.
    """
    if not contexts:
        return 0.0
    answer_vec = embedding_provider.embed_query([answer])[0]
    context_vecs = embedding_provider.embed(contexts)
    return max(_cosine_similarity(answer_vec, cv) for cv in context_vecs)


def answer_relevancy(question: str, answer: str) -> float:
    """Cosine similarity between the question and the generated answer --
    does the answer actually address what was asked, or drift off-topic."""
    question_vec = embedding_provider.embed_query([question])[0]
    answer_vec = embedding_provider.embed_query([answer])[0]
    return _cosine_similarity(question_vec, answer_vec)


def answer_correctness(generated_answer: str, ground_truth_answer: str) -> float:
    """Cosine similarity between the generated answer and the dataset's own
    ground-truth answer. This is the metric RAGAS itself can't compute
    (it's designed for the no-ground-truth case) -- direct comparison
    against a known-correct answer is a stronger signal than any proxy."""
    generated_vec = embedding_provider.embed_query([generated_answer])[0]
    ground_truth_vec = embedding_provider.embed_query([ground_truth_answer])[0]
    return _cosine_similarity(generated_vec, ground_truth_vec)


def compute_semantic_metrics(
    question: str, answer: str, contexts: list[str], ground_truth_answer: str
) -> dict[str, float]:
    return {
        "faithfulness": faithfulness(answer, contexts),
        "answer_relevancy": answer_relevancy(question, answer),
        "answer_correctness": answer_correctness(answer, ground_truth_answer),
    }
