"""Elasticsearch data store layer. Owns the ES connection, index mapping,
and generic index/search operations. Query construction for specific
retrieval mechanisms (BM25, kNN, hybrid, ...) belongs to the Retrieval
layer, not here — this class only executes whatever query it is given.
"""

from typing import Any

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

from config import settings
from logger import get_logger

log = get_logger(__name__)

INDEX_MAPPING = {
    "properties": {
        "chunk_id": {"type": "keyword"},
        "hf_row_id": {"type": "long"},
        "text": {"type": "text"},
        "embedding": {
            "type": "dense_vector",
            "dims": settings.embedding_dim,
            "index": True,
            "similarity": "cosine",
        },
        "chunk_index": {"type": "integer"},
    }
}


class ElasticSearchStore:
    def __init__(self) -> None:
        self.client = Elasticsearch(settings.elasticsearch_url)
        self.index_name = settings.elasticsearch_index

    def create_index(self) -> None:
        if self.client.indices.exists(index=self.index_name):
            log.info("Index '%s' already exists, skipping creation", self.index_name)
            return
        self.client.indices.create(index=self.index_name, mappings=INDEX_MAPPING)
        log.info("Created index '%s'", self.index_name)

    def index_data(self, documents: list[dict[str, Any]]) -> int:
        actions = (
            {
                "_index": self.index_name,
                "_id": doc["chunk_id"],
                "_source": doc,
            }
            for doc in documents
        )
        success_count, errors = bulk(self.client, actions, raise_on_error=False, stats_only=False)
        if isinstance(errors, list) and errors:
            log.error("Failed to index %d document(s): %s", len(errors), errors)
        log.info("Indexed %d document(s) into '%s'", success_count, self.index_name)
        return success_count

    def search_data(self, query: dict[str, Any], size: int = 10) -> dict[str, Any]:
        log.info("Searching index '%s'", self.index_name)
        response = self.client.search(index=self.index_name, size=size, **query)
        return dict(response)


store = ElasticSearchStore()
