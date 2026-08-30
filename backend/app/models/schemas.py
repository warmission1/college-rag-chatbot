from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class UserModel(BaseModel):
    id: str
    name: str
    email: str
    hashed_password: str
    role: str = "user"
    department_id: Optional[str] = None
    status: str = "active"
    auth_provider: str = "local"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login_at: Optional[datetime] = None


class CollectionModel(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    department_id: Optional[str] = None
    visibility: str = "public"
    status: str = "active"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentModel(BaseModel):
    id: str
    title: str
    collection_id: str
    owner_id: str
    status: str = "draft"
    current_version: str = "v1.0"
    current_version_id: Optional[str] = None
    checksum: str
    language: str = "en"
    storage_key: str
    file_type: str
    file_size_bytes: int = 0
    page_count: int = 1
    ocr_used: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentChunkModel(BaseModel):
    id: str
    document_id: str
    document_version_id: str
    collection_id: str
    version: str = "v1.0"
    content: str
    page_number: Optional[int] = None
    section_path: Optional[str] = None
    chunk_index: int = 0
    token_count: int = 0
    metadata: Dict[str, Any] = {}
    embedding: List[float] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ConversationModel(BaseModel):
    id: str
    user_id: str
    title: str = "New Conversation"
    language: str = "en"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class MessageModel(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    evidence_status: str = "grounded"
    token_usage: int = 0
    retrieval_ms: float = 0.0
    generation_ms: float = 0.0
    sources: List[Dict[str, Any]] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FeedbackModel(BaseModel):
    id: str
    user_id: str
    message_id: str
    rating: str
    reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AuditLogModel(BaseModel):
    id: str
    actor_user_id: str
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    metadata: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)
