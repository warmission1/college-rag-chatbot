import abc
import hashlib
import math
import re
from typing import List, Optional, Dict, Any
import httpx
from backend.app.core.config import settings
from backend.app.core.errors import InternalError

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "aren't",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by",
    "can", "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't", "doing",
    "don't", "down", "during", "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here", "here's", "hers",
    "herself", "him", "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm", "i've", "if", "in",
    "into", "is", "isn't", "it", "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our",
    "ours", "ourselves", "out", "over", "own", "same", "shan't", "she", "she'd", "she'll", "she's",
    "should", "shouldn't", "so", "some", "such", "than", "that", "that's", "the", "their", "theirs",
    "them", "themselves", "then", "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasn't",
    "we", "we'd", "we'll", "we're", "we've", "were", "weren't", "what", "what's", "when", "when's",
    "where", "where's", "which", "while", "who", "who's", "whom", "why", "why's", "with", "won't",
    "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours", "yourself",
    "yourselves"
}


class BaseEmbeddingAdapter(abc.ABC):
    @abc.abstractmethod
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        pass

    @abc.abstractmethod
    def embed_query(self, query: str) -> List[float]:
        pass

    @property
    @abc.abstractmethod
    def dimension(self) -> int:
        pass


class MockEmbeddingAdapter(BaseEmbeddingAdapter):
    """Deterministic TF-IDF & subword n-gram embedding."""
    def __init__(self, dim: int = 384):
        self._dim = dim

    @property
    def dimension(self) -> int:
        return self._dim

    def _tokenize(self, text: str) -> List[str]:
        words = re.findall(r"\b[a-zA-Z0-9_\-\$]+\b", text.lower())
        return [w for w in words if w not in STOPWORDS and len(w) > 1]

    def _text_to_vector(self, text: str) -> List[float]:
        tokens = self._tokenize(text)
        vec = [0.0] * self._dim
        
        if not tokens:
            return vec

        tf = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1

        for token, count in tf.items():
            weight = 1.0 + math.log(count)
            h = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
            idx = h % self._dim
            vec[idx] += weight * 2.0

            if len(token) >= 3:
                for n in range(3, min(6, len(token) + 1)):
                    for i in range(len(token) - n + 1):
                        ngram = token[i:i+n]
                        nh = int(hashlib.md5(ngram.encode("utf-8")).hexdigest(), 16)
                        nidx = nh % self._dim
                        vec[nidx] += 0.5

        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [self._text_to_vector(t) for t in texts]

    def embed_query(self, query: str) -> List[float]:
        return self._text_to_vector(query)


class OpenAIEmbeddingAdapter(BaseEmbeddingAdapter):
    def __init__(self, api_key: str, model: str = "text-embedding-3-small", dim: int = 1536):
        self.api_key = api_key
        self.model = model or "text-embedding-3-small"
        self._dim = dim

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not self.api_key:
            raise InternalError("EMBEDDING_API_KEY is not configured in .env")
        url = "https://api.openai.com/v1/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"input": texts, "model": self.model}
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise InternalError(f"OpenAI Embedding API error: {resp.text}")
            data = resp.json()
            return [item["embedding"] for item in data["data"]]

    def embed_query(self, query: str) -> List[float]:
        return self.embed_texts([query])[0]


_gemini_embed_client: Optional[httpx.Client] = None


def _get_embed_client() -> httpx.Client:
    global _gemini_embed_client
    if _gemini_embed_client is None or _gemini_embed_client.is_closed:
        _gemini_embed_client = httpx.Client(
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20, keepalive_expiry=120.0)
        )
    return _gemini_embed_client


class GeminiEmbeddingAdapter(BaseEmbeddingAdapter):
    def __init__(self, api_key: str, model: str = "models/text-embedding-004", dim: int = 768):
        self.api_key = api_key
        self.model = model or "models/text-embedding-004"
        self._dim = dim

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not self.api_key:
            raise InternalError("EMBEDDING_API_KEY is not configured in .env")
        model_name = self.model if self.model.startswith("models/") else f"models/{self.model}"
        url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:batchEmbedContents?key={self.api_key}"
        requests = [{"model": model_name, "content": {"parts": [{"text": t}]}} for t in texts]
        client = _get_embed_client()
        try:
            resp = client.post(url, json={"requests": requests})
        except Exception:
            # Recreate client on connection drop
            global _gemini_embed_client
            _gemini_embed_client = None
            client = _get_embed_client()
            resp = client.post(url, json={"requests": requests})

        if resp.status_code != 200:
            raise InternalError(f"Gemini Embedding API error: {resp.text}")
        data = resp.json()
        return [emb["values"] for emb in data.get("embeddings", [])]

    def embed_query(self, query: str) -> List[float]:
        return self.embed_texts([query])[0]


def get_embedding_adapter() -> BaseEmbeddingAdapter:
    provider = settings.EMBEDDING_PROVIDER.lower()
    if provider == "openai" and settings.EMBEDDING_API_KEY:
        return OpenAIEmbeddingAdapter(
            api_key=settings.EMBEDDING_API_KEY,
            model=settings.EMBEDDING_MODEL,
            dim=settings.EMBEDDING_DIMENSIONS,
        )
    elif provider == "gemini" and settings.EMBEDDING_API_KEY:
        return GeminiEmbeddingAdapter(
            api_key=settings.EMBEDDING_API_KEY,
            model=settings.EMBEDDING_MODEL,
            dim=settings.EMBEDDING_DIMENSIONS,
        )
    return MockEmbeddingAdapter(dim=settings.EMBEDDING_DIMENSIONS)
