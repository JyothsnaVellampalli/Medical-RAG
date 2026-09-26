"""Retrieval layer. Each method is one retrieval mechanism, all built on top
of DataStore.search_data() (Elasticsearch is the only source of ranked
results). Hybrid methods fuse two Elasticsearch-ranked candidate lists in
Python; ES 8.15.3's native RRF retriever needs a licensed feature this
cluster doesn't have, and its native linear retriever doesn't exist in this
ES version at all, so both hybrid mechanisms fuse manually instead.

retrieve() is the registry: adding a new mechanism means adding a method
below and one line to the `strategies` mapping.
"""

from typing import Any

from DataStore.elastic_search_store import store
from Embedding.embedding_provider import embedding_provider
from logger import get_logger

log = get_logger(__name__)

DEFAULT_SIZE = 10
RRF_K = 60


def _candidate_size(size: int) -> int:
    return max(size * 3, 30)


def _format_hit(source: dict[str, Any], score: float) -> dict[str, Any]:
    return {
        "chunk_id": source["chunk_id"],
        "hf_row_id": source["hf_row_id"],
        "text": source["text"],
        "chunk_index": source["chunk_index"],
        "score": score,
    }


def _min_max_normalize(hits: list[dict[str, Any]]) -> dict[str, float]:
    if not hits:
        return {}
    scores = [hit["_score"] for hit in hits]
    lo, hi = min(scores), max(scores)
    if hi == lo:
        return {hit["_id"]: 1.0 for hit in hits}
    return {hit["_id"]: (hit["_score"] - lo) / (hi - lo) for hit in hits}


def _rrf_scores(hits: list[dict[str, Any]], k: int) -> dict[str, float]:
    return {hit["_id"]: 1.0 / (k + rank) for rank, hit in enumerate(hits, start=1)}


class RetrievalRegistry:
    def _raw_bm25_hits(self, query_text: str, size: int) -> list[dict[str, Any]]:
        result = store.search_data({"query": {"match": {"text": query_text}}}, size=size)
        return list(result["hits"]["hits"])

    def _raw_semantic_hits(self, query_text: str, size: int) -> list[dict[str, Any]]:
        query_vector = embedding_provider.embed_query([query_text])[0]
        result = store.search_data(
            {
                "knn": {
                    "field": "embedding",
                    "query_vector": query_vector,
                    "k": size,
                    "num_candidates": max(size * 10, 50),
                }
            },
            size=size,
        )
        return list(result["hits"]["hits"])

    def bm25_search(self, query_text: str, size: int = DEFAULT_SIZE) -> list[dict[str, Any]]:
        log.info("BM25 search: %r (size=%d)", query_text, size)
        hits = self._raw_bm25_hits(query_text, size)
        return [_format_hit(hit["_source"], hit["_score"]) for hit in hits]

    def semantic_search(self, query_text: str, size: int = DEFAULT_SIZE) -> list[dict[str, Any]]:
        log.info("Semantic search: %r (size=%d)", query_text, size)
        hits = self._raw_semantic_hits(query_text, size)
        return [_format_hit(hit["_source"], hit["_score"]) for hit in hits]

    def hybrid_weighted_search(
        self, query_text: str, weight: float = 0.5, size: int = DEFAULT_SIZE
    ) -> list[dict[str, Any]]:
        log.info("Hybrid (weighted) search: %r (weight=%.2f, size=%d)", query_text, weight, size)
        candidates = _candidate_size(size)
        bm25_hits = self._raw_bm25_hits(query_text, candidates)
        semantic_hits = self._raw_semantic_hits(query_text, candidates)

        bm25_norm = _min_max_normalize(bm25_hits)
        semantic_norm = _min_max_normalize(semantic_hits)
        sources = {hit["_id"]: hit["_source"] for hit in [*bm25_hits, *semantic_hits]}

        scored = [
            (doc_id, weight * semantic_norm.get(doc_id, 0.0) + (1 - weight) * bm25_norm.get(doc_id, 0.0))
            for doc_id in sources
        ]
        scored.sort(key=lambda item: item[1], reverse=True)
        return [_format_hit(sources[doc_id], score) for doc_id, score in scored[:size]]

    def hybrid_rrf_search(
        self, query_text: str, size: int = DEFAULT_SIZE, k: int = RRF_K
    ) -> list[dict[str, Any]]:
        log.info("Hybrid (RRF) search: %r (k=%d, size=%d)", query_text, k, size)
        candidates = _candidate_size(size)
        bm25_hits = self._raw_bm25_hits(query_text, candidates)
        semantic_hits = self._raw_semantic_hits(query_text, candidates)

        bm25_rrf = _rrf_scores(bm25_hits, k)
        semantic_rrf = _rrf_scores(semantic_hits, k)
        sources = {hit["_id"]: hit["_source"] for hit in [*bm25_hits, *semantic_hits]}

        scored = [(doc_id, bm25_rrf.get(doc_id, 0.0) + semantic_rrf.get(doc_id, 0.0)) for doc_id in sources]
        scored.sort(key=lambda item: item[1], reverse=True)
        return [_format_hit(sources[doc_id], score) for doc_id, score in scored[:size]]

    def retrieve(
        self,
        strategy: str,
        query_text: str,
        size: int = DEFAULT_SIZE,
        weight: float = 0.5,
    ) -> list[dict[str, Any]]:
        strategies = {
            "bm25": lambda: self.bm25_search(query_text, size),
            "semantic": lambda: self.semantic_search(query_text, size),
            "hybrid_weighted": lambda: self.hybrid_weighted_search(query_text, weight, size),
            "hybrid_rrf": lambda: self.hybrid_rrf_search(query_text, size),
        }
        if strategy not in strategies:
            raise ValueError(f"Unknown retrieval strategy: {strategy!r}. Valid: {sorted(strategies)}")
        return strategies[strategy]()


retrieval_registry = RetrievalRegistry()
