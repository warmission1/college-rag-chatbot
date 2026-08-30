import math
import re
import time
from typing import List, Optional, Dict, Any, Tuple
import numpy as np
from pymongo.database import Database
from backend.app.core.config import settings
from backend.app.rag.embeddings import EmbeddingService

_chunk_cache = {
    "timestamp": 0.0,
    "chunks": [],
    "matrix": None,
    "doc_map": {},
}


def invalidate_vector_cache():
    global _chunk_cache
    _chunk_cache["timestamp"] = 0.0
    _chunk_cache["chunks"] = []
    _chunk_cache["matrix"] = None
    _chunk_cache["doc_map"] = {}


class RetrievedChunk:
    def __init__(
        self,
        chunk_id: str,
        document_id: str,
        document_title: str,
        document_version: str,
        collection_id: str,
        content: str,
        page_number: Optional[int],
        section_path: Optional[str],
        similarity: float,
        rerank_score: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.document_title = document_title
        self.document_version = document_version
        self.collection_id = collection_id
        self.content = content
        self.page_number = page_number
        self.section_path = section_path
        self.similarity = similarity
        self.rerank_score = rerank_score
        self.metadata = metadata or {}


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm_a = math.sqrt(sum(a * a for a in vec1))
    norm_b = math.sqrt(sum(b * b for b in vec2))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return max(0.0, min(1.0, dot / (norm_a * norm_b)))


class Retriever:
    def __init__(self, db: Database, embedding_service: Optional[EmbeddingService] = None):
        self.db = db
        self.embedding_service = embedding_service or EmbeddingService()

    def _get_published_chunks_and_matrix(self, allow_drafts: bool = False, collection_ids: Optional[List[str]] = None):
        global _chunk_cache
        now = time.time()
        # Use cached in-memory vector matrix if fresh (TTL 120s) and default filters
        if not allow_drafts and not collection_ids and (now - _chunk_cache["timestamp"] < 120.0) and _chunk_cache["matrix"] is not None:
            return _chunk_cache["chunks"], _chunk_cache["matrix"], _chunk_cache["doc_map"]

        doc_filter: Dict[str, Any] = {}
        if not allow_drafts:
            doc_filter["status"] = "published"
        if collection_ids:
            doc_filter["collection_id"] = {"$in": collection_ids}

        published_docs = list(self.db.documents.find(doc_filter))
        if not published_docs:
            return [], None, {}

        doc_map = {d["id"]: d for d in published_docs}
        allowed_doc_ids = list(doc_map.keys())

        chunk_filter: Dict[str, Any] = {"document_id": {"$in": allowed_doc_ids}}
        chunks = list(self.db.document_chunks.find(chunk_filter))
        if not chunks:
            return [], None, {}

        embeddings = []
        valid_chunks = []
        for c in chunks:
            emb = c.get("embedding")
            if emb:
                embeddings.append(emb)
                valid_chunks.append(c)

        if not embeddings:
            return [], None, {}

        mat = np.array(embeddings, dtype=np.float32)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        normalized_mat = mat / norms

        if not allow_drafts and not collection_ids:
            _chunk_cache["timestamp"] = now
            _chunk_cache["chunks"] = valid_chunks
            _chunk_cache["matrix"] = normalized_mat
            _chunk_cache["doc_map"] = doc_map

        return valid_chunks, normalized_mat, doc_map

    def retrieve(
        self,
        query: str,
        user: Optional[Dict[str, Any]] = None,
        collection_ids: Optional[List[str]] = None,
        top_k: int = settings.RAG_TOP_K,
        context_k: int = settings.RAG_CONTEXT_K,
        threshold: float = settings.RAG_SIMILARITY_THRESHOLD,
        allow_drafts: bool = False,
    ) -> Tuple[List[RetrievedChunk], bool]:
        # 1. Embed query
        query_vec = self.embedding_service.embed_query(query)
        if not query_vec:
            return [], False

        # 2. Fast In-Memory Vector Matrix (0ms DB delay)
        chunks, norm_mat, doc_map = self._get_published_chunks_and_matrix(allow_drafts, collection_ids)
        if not chunks or norm_mat is None:
            return [], False

        # 3. Vectorized NumPy Cosine Similarity (< 1ms)
        q_arr = np.array(query_vec, dtype=np.float32)
        q_norm = np.linalg.norm(q_arr)
        if q_norm > 0:
            q_arr = q_arr / q_norm

        sim_scores = np.dot(norm_mat, q_arr)

        # 4. Score candidates with optional hybrid keyword match
        scored_candidates: List[RetrievedChunk] = []
        query_words = set(re.findall(r"\w+", query.lower()))

        for idx, chunk in enumerate(chunks):
            sim = float(sim_scores[idx])
            content = chunk.get("content", "")

            if settings.HYBRID_SEARCH_ENABLED and query_words:
                content_lower = content.lower()
                matched_words = sum(1 for w in query_words if len(w) > 2 and w in content_lower)
                keyword_score = matched_words / max(1, len(query_words))
                combined_score = 0.7 * sim + 0.3 * keyword_score
            else:
                combined_score = sim

            doc_id = chunk.get("document_id")
            doc = doc_map.get(doc_id, {})

            scored_candidates.append(
                RetrievedChunk(
                    chunk_id=chunk.get("id"),
                    document_id=doc_id,
                    document_title=doc.get("title", "Document"),
                    document_version=chunk.get("version", doc.get("current_version", "v1")),
                    collection_id=chunk.get("collection_id", ""),
                    content=content,
                    page_number=chunk.get("page_number"),
                    section_path=chunk.get("section_path"),
                    similarity=round(combined_score, 4),
                    metadata=chunk.get("metadata", {}),
                )
            )

        # 5. Sort candidates descending
        scored_candidates.sort(key=lambda x: x.similarity, reverse=True)
        top_candidates = scored_candidates[:top_k]

        # 6. Deduplicate
        deduped: List[RetrievedChunk] = []
        seen = set()
        for cand in top_candidates:
            fp = cand.content[:100].strip()
            if fp not in seen:
                seen.add(fp)
                deduped.append(cand)

        # 7. Apply threshold & context budget
        final_passages = deduped[:context_k]
        has_sufficient_evidence = False
        if final_passages and final_passages[0].similarity >= threshold:
            has_sufficient_evidence = True

        return final_passages, has_sufficient_evidence
