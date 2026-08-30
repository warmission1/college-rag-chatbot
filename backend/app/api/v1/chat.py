import uuid
import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from pymongo.database import Database
from backend.app.core.database import get_db
from backend.app.core.errors import AppError, ForbiddenError
from backend.app.auth.dependencies import get_current_user
from backend.app.rag.orchestrator import RAGOrchestrator

router = APIRouter(prefix="/chat", tags=["Chat & RAG"])


class CreateConversationRequest(BaseModel):
    title: Optional[str] = "New Conversation"
    language: Optional[str] = "en"


class SendMessageRequest(BaseModel):
    question: str = Field(..., min_length=1)
    collection_ids: Optional[List[str]] = None
    language: Optional[str] = "en"
    stream: Optional[bool] = False


class FeedbackRequest(BaseModel):
    rating: str = Field(..., pattern="^(helpful|not_helpful)$")
    reason: Optional[str] = None


@router.post("/conversations", status_code=status.HTTP_201_CREATED)
def create_conversation(req: CreateConversationRequest, current_user: Dict[str, Any] = Depends(get_current_user), db: Database = Depends(get_db)):
    conv_id = str(uuid.uuid4())
    now = datetime.utcnow()
    conv = {
        "id": conv_id,
        "user_id": current_user["id"],
        "title": req.title or "New Conversation",
        "language": req.language or "en",
        "created_at": now,
        "updated_at": now,
    }
    db.conversations.insert_one(conv)
    return {"id": conv_id, "title": conv["title"], "created_at": now}


@router.get("/conversations")
def list_conversations(current_user: Dict[str, Any] = Depends(get_current_user), db: Database = Depends(get_db)):
    cursor = db.conversations.find(
        {"user_id": current_user["id"]},
        {"id": 1, "title": 1, "language": 1, "created_at": 1, "updated_at": 1}
    ).sort("updated_at", -1)
    
    return [
        {
            "id": c.get("id"),
            "title": c.get("title", "New Chat"),
            "language": c.get("language", "en"),
            "created_at": c.get("created_at"),
            "updated_at": c.get("updated_at"),
            "message_count": 0,
        }
        for c in cursor
    ]


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, current_user: Dict[str, Any] = Depends(get_current_user), db: Database = Depends(get_db)):
    conv = db.conversations.find_one({"id": conversation_id})
    if not conv:
        raise AppError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Conversation not found")
    if conv["user_id"] != current_user["id"]:
        raise ForbiddenError("Cannot access conversation belonging to another user")

    messages_cursor = db.messages.find({"conversation_id": conversation_id}).sort("created_at", 1)
    formatted_msgs = []
    for m in messages_cursor:
        formatted_msgs.append({
            "id": m.get("id"),
            "role": m.get("role"),
            "content": m.get("content"),
            "evidence_status": m.get("evidence_status", "grounded"),
            "sources": m.get("sources", []),
            "created_at": m.get("created_at"),
            "usage": {
                "retrieval_ms": m.get("retrieval_ms", 0),
                "generation_ms": m.get("generation_ms", 0),
                "tokens": m.get("token_usage", 0),
            }
        })

    return {
        "id": conv["id"],
        "title": conv.get("title", "Conversation"),
        "language": conv.get("language", "en"),
        "messages": formatted_msgs,
    }


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, current_user: Dict[str, Any] = Depends(get_current_user), db: Database = Depends(get_db)):
    conv = db.conversations.find_one({"id": conversation_id})
    if not conv:
        raise AppError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Conversation not found")
    if conv["user_id"] != current_user["id"] and current_user.get("role") not in ["admin", "super-admin"]:
        raise ForbiddenError("Cannot delete conversation belonging to another user")

    db.conversations.delete_one({"id": conversation_id})
    db.messages.delete_many({"conversation_id": conversation_id})
    return {"message": "Conversation deleted successfully"}


@router.post("/conversations/{conversation_id}/messages")
def send_message(
    conversation_id: str,
    req: SendMessageRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    conv = db.conversations.find_one({"id": conversation_id})
    if not conv:
        raise AppError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Conversation not found")
    if conv["user_id"] != current_user["id"] and current_user.get("role") not in ["admin", "super-admin"]:
        raise ForbiddenError("Cannot send messages to a conversation belonging to another user")

    orchestrator = RAGOrchestrator(db=db)
    rag_result = orchestrator.execute_rag(
        conversation_id=conversation_id,
        question=req.question,
        user=current_user,
        collection_ids=req.collection_ids,
        language=req.language or "en",
    )

    return {
        "message_id": rag_result.message_id,
        "answer": rag_result.answer,
        "evidence_status": rag_result.evidence_status,
        "sources": rag_result.sources,
        "usage": {
            "retrieval_ms": rag_result.retrieval_ms,
            "generation_ms": rag_result.generation_ms,
            "tokens": rag_result.tokens_used,
        },
    }


@router.get("/messages/{message_id}/sources")
def get_message_sources(message_id: str, current_user: Dict[str, Any] = Depends(get_current_user), db: Database = Depends(get_db)):
    msg = db.messages.find_one({"id": message_id})
    if not msg:
        raise AppError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Message not found")
    return msg.get("sources", [])


@router.post("/messages/{message_id}/feedback")
def submit_feedback(
    message_id: str,
    req: FeedbackRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    feedback_id = str(uuid.uuid4())
    db.feedback.insert_one({
        "id": feedback_id,
        "user_id": current_user["id"],
        "message_id": message_id,
        "rating": req.rating,
        "reason": req.reason,
        "created_at": datetime.utcnow(),
    })
    return {"message": "Feedback submitted successfully"}


@router.get("/stream/{message_id}")
async def stream_message(message_id: str, db: Database = Depends(get_db)):
    msg = db.messages.find_one({"id": message_id})
    if not msg:
        raise AppError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Message not found")

    async def event_generator():
        words = msg.get("content", "").split(" ")
        for w in words:
            yield f"data: {w} \n\n"
            await asyncio.sleep(0.02)
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
