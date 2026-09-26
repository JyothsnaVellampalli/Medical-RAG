"""LLM query layer: retrieves context via the Retrieval layer, then asks the
local Ollama model to answer using only that context. Citations come from
the retrieval layer's own results (the chunks actually fed into the prompt),
not from the LLM self-reporting sources - more reliable for a small model.
"""

from typing import Any

import ollama

from config import settings
from logger import get_logger
from Retrieval.retrieval_registry import retrieval_registry

log = get_logger(__name__)

CONTEXT_SIZE = 5

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
    def __init__(self) -> None:
        self.client = ollama.Client(host=settings.ollama_url)

    def query(
        self,
        search_type: str,
        query_text: str,
        weight: float = 0.5,
        size: int = CONTEXT_SIZE,
    ) -> dict[str, Any]:
        chunks = retrieval_registry.retrieve(
            strategy=search_type,
            query_text=query_text,
            weight=weight,
            size=size,
        )

        log.info("Generating LLM response for query: %r (context chunks=%d)", query_text, len(chunks))
        result = self.client.generate(
            model=settings.llm_model,
            prompt=_build_prompt(query_text, chunks),
            system=SYSTEM_PROMPT,
            stream=False,
        )
        log.info("Generated LLM response for query: %r (%d chars)", query_text, len(result.response or ""))

        return {"response": result.response, "citations": chunks}


llm_query_layer = LLMQueryLayer()
