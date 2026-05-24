"""Milvus vector store with hybrid search support."""

from __future__ import annotations

from kb_studio.core.doc_processor.chunker import Chunk
from kb_studio.core.vector_store import SearchResult


class MilvusStore:
    """Manages a Milvus collection for storing document chunks with vectors."""

    def __init__(
        self,
        collection_name: str = "agent_docs",
        dimension: int = 1024,
        uri: str = "",
        host: str = "localhost",
        port: int = 19530,
        use_lite: bool = True,
        lite_path: str = "./data/vectordb",
    ):
        self.collection_name = collection_name
        self.dimension = dimension
        self._connected = False
        self._use_lite = use_lite
        self._lite_path = lite_path if lite_path.endswith(".db") else f"{lite_path.rstrip('/')}/milvus.db"
        self._host = host
        self._port = port
        self._uri = uri
        self._collection = None

    def connect(self):
        if self._connected:
            return
        if self._use_lite:
            import os
            os.makedirs(os.path.dirname(self._lite_path), exist_ok=True)
            from pymilvus import MilvusClient
            self._lite_client = MilvusClient(uri=self._lite_path)
        else:
            from pymilvus import connections
            connections.connect(host=self._host, port=self._port)
        self._connected = True

    def create_collection(self):
        self.connect()
        if self._use_lite:
            from pymilvus import CollectionSchema, FieldSchema, DataType
            fields = [
                FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, is_primary=True, max_length=256),
                FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=512),
                FieldSchema(name="heading_path", dtype=DataType.VARCHAR, max_length=1024),
                FieldSchema(name="metadata_json", dtype=DataType.VARCHAR, max_length=4096),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dimension),
            ]
            schema = CollectionSchema(fields=fields)
            if self._lite_client.has_collection(self.collection_name):
                self._lite_client.drop_collection(self.collection_name)
            self._lite_client.create_collection(
                collection_name=self.collection_name,
                schema=schema,
            )
        else:
            from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, utility
            if utility.has_collection(self.collection_name):
                self._collection = Collection(self.collection_name)
                return
            fields = [
                FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, is_primary=True, max_length=256),
                FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=512),
                FieldSchema(name="heading_path", dtype=DataType.VARCHAR, max_length=1024),
                FieldSchema(name="metadata_json", dtype=DataType.VARCHAR, max_length=4096),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dimension),
            ]
            schema = CollectionSchema(fields=fields, description="Agent document chunks")
            self._collection = Collection(self.collection_name, schema)
            self._collection.create_index(
                field_name="embedding",
                index_params={
                    "metric_type": "COSINE",
                    "index_type": "HNSW",
                    "params": {"M": 16, "efConstruction": 200},
                },
            )

    def insert_chunks(self, chunks: list[Chunk], embeddings: list[list[float]]):
        self.connect()
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")

        import json
        data = []
        for chunk, emb in zip(chunks, embeddings):
            data.append({
                "chunk_id": chunk.chunk_id,
                "content": chunk.content,
                "source": chunk.source,
                "heading_path": " > ".join(chunk.heading_path) if chunk.heading_path else "",
                "metadata_json": json.dumps(chunk.metadata, ensure_ascii=False),
                "embedding": emb,
            })

        if self._use_lite:
            self._lite_client.insert(collection_name=self.collection_name, data=data)
        else:
            self._collection.insert(data)
            self._collection.flush()

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        output_fields: list[str] | None = None,
    ) -> list[SearchResult]:
        self.connect()
        if output_fields is None:
            output_fields = ["chunk_id", "content", "source", "heading_path", "metadata_json"]

        if self._use_lite:
            results = self._lite_client.search(
                collection_name=self.collection_name,
                data=[query_embedding],
                limit=top_k,
                output_fields=output_fields,
                search_params={"metric_type": "COSINE"},
            )
            return self._parse_lite_results(results)
        else:
            self._collection.load()
            results = self._collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param={"metric_type": "COSINE", "params": {"ef": 128}},
                limit=top_k,
                output_fields=output_fields,
            )
            return self._parse_results(results)

    def _parse_lite_results(self, results) -> list[SearchResult]:
        import json
        parsed = []
        for hits in results:
            for hit in hits:
                entity = hit.get("entity", {})
                parsed.append(SearchResult(
                    chunk_id=hit.get("id", ""),
                    content=entity.get("content", ""),
                    score=hit.get("distance", 0.0),
                    source=entity.get("source", ""),
                    heading_path=entity.get("heading_path", "").split(" > "),
                    metadata=json.loads(entity.get("metadata_json", "{}")),
                ))
        return parsed

    def _parse_results(self, results) -> list[SearchResult]:
        import json
        parsed = []
        for hits in results:
            for hit in hits:
                entity = hit.entity
                parsed.append(SearchResult(
                    chunk_id=hit.id,
                    content=entity.get("content"),
                    score=hit.distance,
                    source=entity.get("source"),
                    heading_path=entity.get("heading_path", "").split(" > "),
                    metadata=json.loads(entity.get("metadata_json", "{}")),
                ))
        return parsed

    def delete_by_source(self, source: str):
        self.connect()
        if self._use_lite:
            self._lite_client.delete(
                collection_name=self.collection_name,
                filter=f'source == "{source}"',
            )
        else:
            self._collection.delete(f'source == "{source}"')

    def get_collection_stats(self) -> dict:
        self.connect()
        if self._use_lite:
            stats = self._lite_client.get_collection_stats(self.collection_name)
            return {"row_count": stats.get("row_count", 0)}
        else:
            self._collection.flush()
            return {"row_count": self._collection.num_entities}
