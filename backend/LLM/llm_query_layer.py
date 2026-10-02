"""LLM query layer: retrieves context via the Retrieval layer, optionally
reranks it (Reranker.reranker), then asks the selected generation provider
(Ollama by default, or OpenRouter -- see LLM.generation_registry) to answer
using only that context. Citations come from the chunks actually fed into
the prompt -- post-rerank order when reranking is on -- not from the LLM
self-reporting sources, more reliable for a small model.
"""

from typing import Any

from LLM.generation_registry import generation_registry
from logger import get_logger
from Reranker.reranker import reranker
from Retrieval.retrieval_registry import retrieval_registry

log = get_logger(__name__)

CONTEXT_SIZE = 5
DEFAULT_PROVIDER = "ollama"

SYSTEM_PROMPT = (
    "You are a medical question-answering assistant. Answer the user's "
    "question using ONLY the context passages provided below. If the "
    "context does not contain enough information to answer, say so plainly "
    "instead of guessing."
)


def _build_prompt(query_text: str, chunks: list[dict[str, Any]]) -> str:
    context = "\n\n".join(f"[{i + 1}] {chunk['text']}" for i, chunk in enumerate(chunks))
    return f"Context:\n{context}\n\nQuestion: {query_text}\n\nAnswer:"


class LLMQueryLayer:
    def query(
        self,
        search_type: str,
        query_text: str,
        weight: float = 0.5,
        size: int = CONTEXT_SIZE,
        provider: str = DEFAULT_PROVIDER,
        rerank: bool = False,
    ) -> dict[str, Any]:
        chunks = retrieval_registry.retrieve(
            strategy=search_type,
            query_text=query_text,
            weight=weight,
            size=size,
        )

        if rerank:
            chunks = reranker.rerank(query_text, chunks)

        log.info(
            "Generating LLM response for query: %r (context chunks=%d, provider=%s)",
            query_text,
            len(chunks),
            provider,
        )
        response = generation_registry.generate(
            provider=provider,
            prompt=_build_prompt(query_text, chunks),
            system=SYSTEM_PROMPT,
        )
        log.info("Generated LLM response for query: %r (%d chars)", query_text, len(response))

        return {"response": response, "citations": chunks}


llm_query_layer = LLMQueryLayer()
