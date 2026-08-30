from typing import List, Dict
from backend.app.integrations.embedding_adapter import get_embedding_adapter, BaseEmbeddingAdapter

# In-memory query embedding cache to avoid repeated embedding calls
_QUERY_EMBEDDING_CACHE: Dict[str, List[float]] = {}


class EmbeddingService:
    def __init__(self, adapter: BaseEmbeddingAdapter = None):
        self.adapter = adapter or get_embedding_adapter()

    def embed_chunks(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        return self.adapter.embed_texts(texts)

    def embed_query(self, query: str) -> List[float]:
        cleaned_query = query.strip().lower()
        if cleaned_query in _QUERY_EMBEDDING_CACHE:
            return _QUERY_EMBEDDING_CACHE[cleaned_query]

        embedding = self.adapter.embed_query(query)
        _QUERY_EMBEDDING_CACHE[cleaned_query] = embedding
        return embedding

    @property
    def dimension(self) -> int:
        return self.adapter.dimension
