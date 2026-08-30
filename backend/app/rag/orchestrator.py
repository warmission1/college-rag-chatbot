import time
import re
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from pymongo.database import Database
from backend.app.core.config import settings
from backend.app.rag.retriever import Retriever, RetrievedChunk
from backend.app.rag.reranker import Reranker
from backend.app.rag.prompts import SYSTEM_GROUNDING_PROMPT, format_context_block
from backend.app.integrations.llm_adapter import get_llm_adapter, BaseLLMAdapter, LLMResponse


class RAGResult:
    def __init__(
        self,
        message_id: str,
        answer: str,
        evidence_status: str,
        sources: List[Dict[str, Any]],
        retrieval_ms: float,
        generation_ms: float,
        tokens_used: int,
    ):
        self.message_id = message_id
        self.answer = answer
        self.evidence_status = evidence_status
        self.sources = sources
        self.retrieval_ms = retrieval_ms
        self.generation_ms = generation_ms
        self.tokens_used = tokens_used


class RAGOrchestrator:
    def __init__(
        self,
        db: Database,
        retriever: Optional[Retriever] = None,
        reranker: Optional[Reranker] = None,
        llm_adapter: Optional[BaseLLMAdapter] = None,
    ):
        self.db = db
        self.retriever = retriever or Retriever(db=db)
        self.reranker = reranker or Reranker(enabled=settings.RERANKER_ENABLED)
        self.llm = llm_adapter or get_llm_adapter()

    def _get_recent_history(self, conversation_id: str, max_messages: int = 8) -> List[Dict[str, str]]:
        cursor = (
            self.db.messages.find({"conversation_id": conversation_id})
            .sort("created_at", -1)
            .limit(max_messages)
        )
        msgs = list(cursor)
        msgs.reverse()
        return [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in msgs]

    def _rewrite_query_if_needed(self, question: str, history: List[Dict[str, str]]) -> str:
        if not history or len(history) < 2:
            return question
        
        short_followup = len(question.split()) <= 5
        has_pronoun = bool(re.search(r"\b(it|this|that|they|them|these|those|fee|dates|rules|deadlines)\b", question.lower()))
        
        if short_followup or has_pronoun:
            prev_user_msgs = [m["content"] for m in history if m["role"] == "user"]
            if prev_user_msgs:
                last_query = prev_user_msgs[-1]
                return f"{last_query} {question}"
        return question

    def execute_rag(
        self,
        conversation_id: str,
        question: str,
        user: Dict[str, Any],
        collection_ids: Optional[List[str]] = None,
        language: str = "en",
    ) -> RAGResult:
        # 1. Fetch history & rewrite query
        history = self._get_recent_history(conversation_id, max_messages=settings.RAG_MAX_HISTORY_MESSAGES)
        search_query = self._rewrite_query_if_needed(question, history)

        # 2. Retrieval
        t_ret_start = time.time()
        passages, has_evidence = self.retriever.retrieve(
            query=search_query,
            user=user,
            collection_ids=collection_ids,
            top_k=settings.RAG_TOP_K,
            context_k=settings.RAG_CONTEXT_K,
            threshold=settings.RAG_SIMILARITY_THRESHOLD,
        )
        
        if passages and settings.RERANKER_ENABLED:
            passages = self.reranker.rerank(search_query, passages)
            
        retrieval_ms = round((time.time() - t_ret_start) * 1000, 2)

        # 3. Save User Message
        user_msg_id = str(uuid.uuid4())
        self.db.messages.insert_one({
            "id": user_msg_id,
            "conversation_id": conversation_id,
            "role": "user",
            "content": question,
            "evidence_status": "user_query",
            "created_at": datetime.utcnow(),
        })

        # 4. Check evidence & Generate answer
        t_gen_start = time.time()
        source_records: List[Dict[str, Any]] = []

        if not has_evidence or not passages:
            answer = (
                "**Answer**:\n"
                "I cannot find sufficient verified information in the official college knowledge base regarding your request.\n\n"
                "**Conditions / Recommended Actions**:\n"
                "- Please check if the question pertains to admissions, academic calendar, hostel, fees, exams, or placements.\n"
                "- If this is an urgent matter, please contact the college administration office directly.\n\n"
                "**Evidence status**:\n"
                "Insufficient evidence"
            )
            evidence_status = "insufficient_evidence"
            tokens_used = 40
        else:
            context_block = format_context_block(passages)
            prompt_content = f"Retrieved evidence:\n{context_block}\n\nUser Question:\n{question}"

            llm_messages = history + [{"role": "user", "content": prompt_content}]
            llm_resp: LLMResponse = self.llm.generate(
                system_prompt=SYSTEM_GROUNDING_PROMPT,
                messages=llm_messages,
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
            )
            answer = llm_resp.content
            evidence_status = llm_resp.evidence_status
            tokens_used = llm_resp.tokens_used

            for idx, p in enumerate(passages, start=1):
                citation_tag = f"[{idx}]"
                source_records.append({
                    "citation": citation_tag,
                    "chunk_id": p.chunk_id,
                    "document_id": p.document_id,
                    "title": p.document_title,
                    "version": p.document_version,
                    "page": p.page_number,
                    "section": p.section_path,
                    "snippet": p.content[:250] + "..." if len(p.content) > 250 else p.content,
                    "similarity": p.similarity,
                })

        generation_ms = round((time.time() - t_gen_start) * 1000, 2)

        # 5. Persist Assistant Message
        assistant_msg_id = str(uuid.uuid4())
        self.db.messages.insert_one({
            "id": assistant_msg_id,
            "conversation_id": conversation_id,
            "role": "assistant",
            "content": answer,
            "evidence_status": evidence_status,
            "token_usage": tokens_used,
            "retrieval_ms": retrieval_ms,
            "generation_ms": generation_ms,
            "sources": source_records,
            "created_at": datetime.utcnow(),
        })

        # Update conversation title and timestamp in single operation
        self.db.conversations.update_one(
            {"id": conversation_id, "title": "New Conversation"},
            {"$set": {"title": question[:45].strip() + ("..." if len(question) > 45 else "")}}
        )
        self.db.conversations.update_one(
            {"id": conversation_id},
            {"$set": {"updated_at": datetime.utcnow()}}
        )

        return RAGResult(
            message_id=assistant_msg_id,
            answer=answer,
            evidence_status=evidence_status,
            sources=source_records,
            retrieval_ms=retrieval_ms,
            generation_ms=generation_ms,
            tokens_used=tokens_used,
        )
