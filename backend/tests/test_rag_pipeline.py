import pytest
from backend.app.core.database import SessionLocal
from backend.app.rag.retriever import Retriever, cosine_similarity
from backend.app.rag.orchestrator import RAGOrchestrator
from backend.app.models.user import User
from backend.app.models.conversation import Conversation


def test_cosine_similarity():
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    v3 = [0.0, 1.0, 0.0]
    
    assert cosine_similarity(v1, v2) == 1.0
    assert cosine_similarity(v1, v3) == 0.0
    assert cosine_similarity([], []) == 0.0


def test_retriever_query():
    db = SessionLocal()
    try:
        retriever = Retriever(db=db)
        passages, has_evidence = retriever.retrieve("What is the admission deadline?", threshold=0.2)
        assert len(passages) > 0
        assert passages[0].document_title is not None
        assert passages[0].similarity > 0.0
    finally:
        db.close()


def test_rag_pipeline_grounded_answer():
    db = SessionLocal()
    try:
        orchestrator = RAGOrchestrator(db=db)
        user = db.query(User).filter(User.role == "super-admin").first()
        conv = Conversation(user_id=user.id, title="Test Pipeline Conv")
        db.add(conv)
        db.commit()
        db.refresh(conv)

        result = orchestrator.execute_rag(
            conversation_id=conv.id,
            question="What is the last date to submit admission application?",
            user=user,
        )
        assert result.evidence_status == "grounded"
        assert len(result.sources) > 0
        assert "[1]" in result.answer or "Answer" in result.answer

        # Test unknown question
        unknown_result = orchestrator.execute_rag(
            conversation_id=conv.id,
            question="What is the weather on Mars tomorrow morning?",
            user=user,
        )
        assert unknown_result.evidence_status == "insufficient_evidence"
        assert len(unknown_result.sources) == 0

        # Cleanup
        db.delete(conv)
        db.commit()
    finally:
        db.close()
