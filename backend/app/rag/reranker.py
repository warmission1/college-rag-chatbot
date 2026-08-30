from typing import List
from backend.app.rag.retriever import RetrievedChunk


class Reranker:
    def __init__(self, enabled: bool = False):
        self.enabled = enabled

    def rerank(self, query: str, candidates: List[RetrievedChunk]) -> List[RetrievedChunk]:
        if not self.enabled or not candidates:
            return candidates

        # Lightweight cross-encoder scoring simulation based on exact n-gram matching
        query_terms = query.lower().split()
        for cand in candidates:
            content_lower = cand.content.lower()
            term_matches = sum(1 for term in query_terms if term in content_lower)
            density_bonus = (term_matches / max(1, len(query_terms))) * 0.2
            cand.rerank_score = round(min(1.0, cand.similarity + density_bonus), 4)

        candidates.sort(key=lambda x: (x.rerank_score or x.similarity), reverse=True)
        return candidates
