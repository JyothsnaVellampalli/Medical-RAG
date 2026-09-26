"""Chunking layer: fetches the HF text-corpus dataset, cleans it, chunks it
(chunking is fixed to one row = one chunk, per project convention), embeds
each chunk, and indexes it into Elasticsearch. Processes the corpus in
batches so only one batch of raw rows/embeddings is held in memory at a time.
"""

import math
from typing import Any

from datasets import load_dataset
from elasticsearch.helpers import scan

from config import settings
from DataStore.elastic_search_store import store
from Embedding.embedding_provider import embedding_provider
from logger import get_logger

log = get_logger(__name__)

HF_CONFIG = "text-corpus"
HF_SPLIT = "passages"


class ChunkingEngine:
    def clean_data(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cleaned = [row for row in rows if row.get("passage") and str(row["passage"]).strip()]
        dropped = len(rows) - len(cleaned)
        if dropped:
            log.info("Dropped %d row(s) with null/empty passage", dropped)
        return cleaned

    def build_chunks(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "chunk_id": f"{row['id']}-0",
                "hf_row_id": row["id"],
                "text": row["passage"],
                "chunk_index": 0,
            }
            for row in rows
        ]

    def embed_and_index(self, chunks: list[dict[str, Any]]) -> int:
        if not chunks:
            return 0
        texts = [chunk["text"] for chunk in chunks]
        vectors = embedding_provider.embed(texts)
        for chunk, vector in zip(chunks, vectors):
            chunk["embedding"] = vector
        return store.index_data(chunks)

    def _process_batch(self, raw_rows: list[dict[str, Any]], batch_num: int, num_batches: int) -> int:
        cleaned = self.clean_data(raw_rows)
        chunks = self.build_chunks(cleaned)
        indexed = self.embed_and_index(chunks)
        log.info(
            "Batch %d/%d: %d raw -> %d cleaned -> %d indexed",
            batch_num,
            num_batches,
            len(raw_rows),
            len(cleaned),
            indexed,
        )
        return indexed

    def _already_indexed_row_ids(self) -> set[int]:
        if not store.client.indices.exists(index=store.index_name):
            return set()
        hits = scan(
            store.client,
            index=store.index_name,
            query={"query": {"match_all": {}}, "_source": ["hf_row_id"]},
        )
        return {hit["_source"]["hf_row_id"] for hit in hits}

    def ingest(self, batch_size: int = 800) -> int:
        store.create_index()
        already_indexed = self._already_indexed_row_ids()
        dataset = load_dataset(settings.hugging_face_dataset, HF_CONFIG, split=HF_SPLIT)
        total_rows = len(dataset)
        remaining_rows = total_rows - len(already_indexed)
        num_batches = math.ceil(remaining_rows / batch_size) if remaining_rows > 0 else 0
        if already_indexed:
            log.info(
                "Resuming ingest: %d/%d row(s) already indexed, %d remaining in %d batches of %d",
                len(already_indexed),
                total_rows,
                remaining_rows,
                num_batches,
                batch_size,
            )
        else:
            log.info("Starting ingest: %d rows in %d batches of %d", total_rows, num_batches, batch_size)

        total_indexed = 0
        batch: list[dict[str, Any]] = []
        batch_num = 0
        for row in dataset:
            if row["id"] in already_indexed:
                continue
            batch.append(dict(row))
            if len(batch) >= batch_size:
                batch_num += 1
                total_indexed += self._process_batch(batch, batch_num, num_batches)
                batch = []
        if batch:
            batch_num += 1
            total_indexed += self._process_batch(batch, batch_num, num_batches)

        log.info(
            "Ingest complete: %d newly indexed, %d total in index",
            total_indexed,
            len(already_indexed) + total_indexed,
        )
        return total_indexed


chunking_engine = ChunkingEngine()
