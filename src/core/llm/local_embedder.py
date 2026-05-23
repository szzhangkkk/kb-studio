"""Local embedding using sentence-transformers. No API key needed."""

from __future__ import annotations


class LocalEmbedder:
    """Embedding using local sentence-transformers model.

    Downloads the model once on first use, then runs entirely offline.
    """

    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5"):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            print(f"  Loading local embedding model: {self.model_name}...")
            self._model = SentenceTransformer(self.model_name)
            print(f"  Model loaded. Dimension: {self._model.get_embedding_dimension()}")

    def embed(self, text: str) -> list[float]:
        self._load_model()
        return self._model.encode(text, normalize_embeddings=True).tolist()

    def embed_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        self._load_model()
        embeddings = self._model.encode(texts, batch_size=batch_size, normalize_embeddings=True)
        return embeddings.tolist()

    @property
    def dimension(self) -> int:
        self._load_model()
        return self._model.get_embedding_dimension()
