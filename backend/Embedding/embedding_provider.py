"""Local embedding layer. Loads the model named in .env via sentence-transformers
and embeds text into vectors sized to settings.embedding_dim.
"""

from sentence_transformers import SentenceTransformer

from config import settings
from logger import get_logger

log = get_logger(__name__)

DOCUMENT_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "

# Caps tokens-per-text fed to the model. Without this, a handful of very long
# passages (this dataset has some up to ~33k chars) dominate CPU batch time
# with quadratic attention cost. 512 tokens covers the vast majority of
# chunks; longer ones are truncated for embedding purposes only (the full
# text is still stored and still searchable via BM25).
MAX_SEQ_LENGTH = 512


class EmbeddingProvider:
    def __init__(self) -> None:
        self.model = SentenceTransformer(
            settings.embedding_model,
            truncate_dim=settings.embedding_dim,
            trust_remote_code=True,
        )
        self.model.max_seq_length = MAX_SEQ_LENGTH
        self._verify_dimension()

    def _verify_dimension(self) -> None:
        probe = self.model.encode(["dimension check"], convert_to_numpy=True)
        actual_dim = probe.shape[1]
        if actual_dim != settings.embedding_dim:
            raise ValueError(
                f"Embedding model '{settings.embedding_model}' produces {actual_dim}-dim "
                f"vectors, but settings.embedding_dim is {settings.embedding_dim}. "
                "Update EMBEDDING_DIM in .env to match, or vectors won't fit the ES index."
            )
        log.info(
            "Embedding model '%s' verified at %d dimensions",
            settings.embedding_model,
            actual_dim,
        )

    def _encode(self, prefixed_texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(prefixed_texts, convert_to_numpy=True)
        return [vector.tolist() for vector in vectors]

    def embed(self, texts: list[str]) -> list[list[float]]:
        log.info("Embedding %d document text(s)", len(texts))
        return self._encode([f"{DOCUMENT_PREFIX}{text}" for text in texts])

    def embed_query(self, texts: list[str]) -> list[list[float]]:
        log.info("Embedding %d query text(s)", len(texts))
        return self._encode([f"{QUERY_PREFIX}{text}" for text in texts])


embedding_provider = EmbeddingProvider()
