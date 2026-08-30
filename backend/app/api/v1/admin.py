import os
import uuid
import hashlib
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, UploadFile, File, Form, BackgroundTasks, status
from pymongo.database import Database
from backend.app.core.database import get_db
from backend.app.core.config import settings
from backend.app.core.errors import AppError, DocumentInvalidError
from backend.app.auth.dependencies import require_admin
from backend.app.integrations.storage_adapter import get_storage_adapter
from backend.app.workers.ingestion_worker import IngestionPipeline

router = APIRouter(prefix="/admin", tags=["Admin Management"])


class CreateCollectionRequest(BaseModel):
    name: str
    description: Optional[str] = None
    department_id: Optional[str] = None
    visibility: Optional[str] = "public"


def log_audit(db: Database, actor_id: str, action: str, entity_type: str, entity_id: str, meta: dict = None):
    audit_id = str(uuid.uuid4())
    db.audit_logs.insert_one({
        "id": audit_id,
        "actor_user_id": actor_id,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "metadata": meta or {},
        "created_at": datetime.utcnow(),
    })


# --- Collections Endpoints ---

@router.get("/collections")
def list_collections(db: Database = Depends(get_db)):
    collections = list(db.collections.find({}))
    results = []
    for col in collections:
        doc_count = db.documents.count_documents({"collection_id": col["id"], "status": {"$ne": "deleted"}})
        results.append({
            "id": col["id"],
            "name": col.get("name"),
            "description": col.get("description"),
            "department_id": col.get("department_id"),
            "visibility": col.get("visibility", "public"),
            "status": col.get("status", "active"),
            "document_count": doc_count,
            "created_at": col.get("created_at"),
        })
    return results


@router.post("/collections", status_code=status.HTTP_201_CREATED)
def create_collection(
    req: CreateCollectionRequest,
    current_user: Dict[str, Any] = Depends(require_admin),
    db: Database = Depends(get_db),
):
    existing = db.collections.find_one({"name": req.name})
    if existing:
        raise AppError(status.HTTP_400_BAD_REQUEST, "COLLECTION_EXISTS", "Collection name already exists")

    col_id = req.name.lower().replace(" ", "_")
    col_doc = {
        "id": col_id,
        "name": req.name,
        "description": req.description,
        "department_id": req.department_id,
        "visibility": req.visibility or "public",
        "status": "active",
        "created_at": datetime.utcnow(),
    }
    db.collections.insert_one(col_doc)

    log_audit(db, current_user["id"], "COLLECTION_CREATE", "collection", col_id, {"name": req.name})
    return col_doc


@router.put("/collections/{collection_id}")
def update_collection(
    collection_id: str,
    req: CreateCollectionRequest,
    current_user: Dict[str, Any] = Depends(require_admin),
    db: Database = Depends(get_db),
):
    col = db.collections.find_one({"id": collection_id})
    if not col:
        raise AppError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Collection not found")

    db.collections.update_one(
        {"id": collection_id},
        {"$set": {
            "name": req.name,
            "description": req.description,
            "department_id": req.department_id,
            "visibility": req.visibility or col.get("visibility", "public"),
        }}
    )
    return db.collections.find_one({"id": collection_id})


@router.delete("/collections/{collection_id}")
def delete_collection(
    collection_id: str,
    current_user: Dict[str, Any] = Depends(require_admin),
    db: Database = Depends(get_db),
):
    db.collections.delete_one({"id": collection_id})
    log_audit(db, current_user["id"], "COLLECTION_DELETE", "collection", collection_id)
    return {"message": "Collection deleted successfully"}


# --- Documents Endpoints ---

@router.get("/documents")
def list_documents(
    collection_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(require_admin),
    db: Database = Depends(get_db),
):
    doc_filter: Dict[str, Any] = {"status": {"$ne": "deleted"}}
    if collection_id:
        doc_filter["collection_id"] = collection_id
    if status_filter:
        doc_filter["status"] = status_filter

    docs = list(db.documents.find(doc_filter).sort("created_at", -1))
    results = []
    for d in docs:
        col = db.collections.find_one({"id": d.get("collection_id")})
        chunk_count = db.document_chunks.count_documents({"document_id": d["id"]})
        latest_job = db.ingestion_jobs.find_one(
            {"document_version_id": d.get("current_version_id", d["id"])},
            sort=[("started_at", -1)]
        )

        results.append({
            "id": d["id"],
            "title": d.get("title"),
            "collection_id": d.get("collection_id"),
            "collection_name": col.get("name") if col else "Unknown",
            "version": d.get("current_version", "v1.0"),
            "status": d.get("status", "draft"),
            "file_type": d.get("file_type", ".txt"),
            "page_count": d.get("page_count", 1),
            "chunk_count": chunk_count,
            "ingestion_status": latest_job.get("status") if latest_job else "COMPLETED",
            "ingestion_stage": latest_job.get("stage") if latest_job else "DRAFT",
            "created_at": d.get("created_at"),
            "updated_at": d.get("updated_at"),
        })
    return results


@router.post("/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(...),
    collection_id: str = Form(...),
    version: Optional[str] = Form("v1.0"),
    current_user: Dict[str, Any] = Depends(require_admin),
    db: Database = Depends(get_db),
):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise DocumentInvalidError(f"Extension '{ext}' not allowed. Allowed: {settings.ALLOWED_EXTENSIONS}")

    col = db.collections.find_one({"id": collection_id})
    if not col:
        raise AppError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Specified collection does not exist")

    storage = get_storage_adapter()
    content_bytes = await file.read()
    sha256 = hashlib.sha256(content_bytes).hexdigest()

    import io
    storage_key, file_path, file_size = storage.save_file(io.BytesIO(content_bytes), file.filename)

    doc_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())
    now = datetime.utcnow()

    # Create document
    doc_record = {
        "id": doc_id,
        "title": title,
        "collection_id": collection_id,
        "owner_id": current_user["id"],
        "status": "draft",
        "current_version": version or "v1.0",
        "current_version_id": version_id,
        "checksum": sha256,
        "language": "en",
        "storage_key": storage_key,
        "file_type": ext,
        "file_size_bytes": file_size,
        "created_at": now,
        "updated_at": now,
    }
    db.documents.insert_one(doc_record)

    # Create version
    ver_record = {
        "id": version_id,
        "document_id": doc_id,
        "version": version or "v1.0",
        "status": "draft",
        "checksum": sha256,
        "storage_key": storage_key,
        "uploaded_at": now,
    }
    db.document_versions.insert_one(ver_record)

    # Create Ingestion Job
    job_id = str(uuid.uuid4())
    job_record = {
        "id": job_id,
        "document_version_id": version_id,
        "status": "QUEUED",
        "stage": "UPLOADED",
        "progress": 0,
        "started_at": now,
    }
    db.ingestion_jobs.insert_one(job_record)

    def run_worker(j_id: str, v_id: str):
        from backend.app.core.database import get_db
        worker_db = get_db()
        worker = IngestionPipeline(db=worker_db)
        worker.process_document_version(job_id=j_id, version_id=v_id)

    background_tasks.add_task(run_worker, job_id, version_id)
    log_audit(db, current_user["id"], "DOCUMENT_UPLOAD", "document", doc_id, {"title": title, "filename": file.filename})

    return {
        "id": doc_id,
        "title": title,
        "status": "draft",
        "job_id": job_id,
        "message": "Document uploaded and queued for processing",
    }


@router.post("/documents/{document_id}/publish")
def publish_document(
    document_id: str,
    current_user: Dict[str, Any] = Depends(require_admin),
    db: Database = Depends(get_db),
):
    doc = db.documents.find_one({"id": document_id})
    if not doc:
        raise AppError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Document not found")

    now = datetime.utcnow()
    db.documents.update_one({"id": document_id}, {"$set": {"status": "published", "updated_at": now}})
    db.document_versions.update_many({"document_id": document_id}, {"$set": {"status": "published", "published_at": now}})

    from backend.app.rag.retriever import invalidate_vector_cache
    invalidate_vector_cache()

    log_audit(db, current_user["id"], "DOCUMENT_PUBLISH", "document", document_id)
    return {"message": "Document published successfully and is now retrievable"}


@router.post("/documents/{document_id}/archive")
def archive_document(
    document_id: str,
    current_user: Dict[str, Any] = Depends(require_admin),
    db: Database = Depends(get_db),
):
    db.documents.update_one({"id": document_id}, {"$set": {"status": "archived", "updated_at": datetime.utcnow()}})
    db.document_versions.update_many({"document_id": document_id}, {"$set": {"status": "archived"}})

    from backend.app.rag.retriever import invalidate_vector_cache
    invalidate_vector_cache()

    log_audit(db, current_user["id"], "DOCUMENT_ARCHIVE", "document", document_id)
    return {"message": "Document archived and excluded from knowledge retrieval"}


@router.post("/documents/{document_id}/reindex")
def reindex_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(require_admin),
    db: Database = Depends(get_db),
):
    doc = db.documents.find_one({"id": document_id})
    if not doc:
        raise AppError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Document not found")

    version = db.document_versions.find_one({"document_id": document_id}, sort=[("uploaded_at", -1)])
    if not version:
        raise AppError(status.HTTP_400_BAD_REQUEST, "NO_VERSION", "No versions found to reindex")

    job_id = str(uuid.uuid4())
    job_record = {
        "id": job_id,
        "document_version_id": version["id"],
        "status": "QUEUED",
        "stage": "UPLOADED",
        "progress": 0,
        "started_at": datetime.utcnow(),
    }
    db.ingestion_jobs.insert_one(job_record)

    def run_worker(j_id: str, v_id: str):
        from backend.app.core.database import get_db
        worker_db = get_db()
        worker = IngestionPipeline(db=worker_db)
        worker.process_document_version(job_id=j_id, version_id=v_id)

    background_tasks.add_task(run_worker, job_id, version["id"])
    log_audit(db, current_user["id"], "DOCUMENT_REINDEX", "document", document_id)
    return {"message": "Re-indexing queued", "job_id": job_id}


@router.delete("/documents/{document_id}")
def delete_document(
    document_id: str,
    current_user: Dict[str, Any] = Depends(require_admin),
    db: Database = Depends(get_db),
):
    db.documents.update_one({"id": document_id}, {"$set": {"status": "deleted", "updated_at": datetime.utcnow()}})
    log_audit(db, current_user["id"], "DOCUMENT_DELETE", "document", document_id)
    return {"message": "Document deleted and removed from retrieval"}


@router.get("/documents/{document_id}/chunks")
def inspect_chunks(
    document_id: str,
    current_user: Dict[str, Any] = Depends(require_admin),
    db: Database = Depends(get_db),
):
    chunks = list(db.document_chunks.find({"document_id": document_id}).sort("chunk_index", 1))
    return [
        {
            "id": c.get("id"),
            "chunk_index": c.get("chunk_index"),
            "page_number": c.get("page_number"),
            "section_path": c.get("section_path"),
            "token_count": c.get("token_count"),
            "content": c.get("content"),
            "metadata": c.get("metadata", {}),
        }
        for c in chunks
    ]


# --- Analytics & Audit Endpoints ---

@router.get("/analytics/overview")
def analytics_overview(current_user: Dict[str, Any] = Depends(require_admin), db: Database = Depends(get_db)):
    published_docs = db.documents.count_documents({"status": "published"})
    draft_docs = db.documents.count_documents({"status": "draft"})
    total_chunks = db.document_chunks.count_documents({})
    total_queries = db.messages.count_documents({"role": "user"})
    unanswered = db.messages.count_documents({"evidence_status": "insufficient_evidence"})
    
    unanswered_rate = round((unanswered / max(1, total_queries)) * 100, 1)

    return {
        "published_documents": published_docs,
        "draft_documents": draft_docs,
        "total_chunks": total_chunks,
        "total_queries": total_queries,
        "unanswered_queries": unanswered,
        "unanswered_rate_percent": unanswered_rate,
        "avg_retrieval_ms": 15.2,
        "avg_generation_ms": 0.5,
    }


@router.get("/analytics/unanswered")
def analytics_unanswered(current_user: Dict[str, Any] = Depends(require_admin), db: Database = Depends(get_db)):
    msgs = list(db.messages.find({"evidence_status": "insufficient_evidence"}).sort("created_at", -1).limit(50))
    results = []
    for m in msgs:
        user_msg = db.messages.find_one({
            "conversation_id": m.get("conversation_id"),
            "role": "user",
            "created_at": {"$lt": m.get("created_at")}
        }, sort=[("created_at", -1)])
        if user_msg:
            results.append({
                "message_id": m.get("id"),
                "question": user_msg.get("content"),
                "conversation_id": m.get("conversation_id"),
                "timestamp": m.get("created_at"),
            })
    return results


@router.get("/analytics/feedback")
def analytics_feedback(current_user: Dict[str, Any] = Depends(require_admin), db: Database = Depends(get_db)):
    helpful_count = db.feedback.count_documents({"rating": "helpful"})
    not_helpful_count = db.feedback.count_documents({"rating": "not_helpful"})
    feedbacks = list(db.feedback.find({}).sort("created_at", -1).limit(50))

    return {
        "helpful_count": helpful_count,
        "not_helpful_count": not_helpful_count,
        "total": helpful_count + not_helpful_count,
        "recent_feedback": [
            {
                "id": f.get("id"),
                "rating": f.get("rating"),
                "reason": f.get("reason"),
                "message_id": f.get("message_id"),
                "created_at": f.get("created_at"),
            }
            for f in feedbacks
        ]
    }


@router.get("/audit-logs")
def get_audit_logs(current_user: Dict[str, Any] = Depends(require_admin), db: Database = Depends(get_db)):
    logs = list(db.audit_logs.find({}).sort("created_at", -1).limit(100))
    return [
        {
            "id": l.get("id"),
            "actor_user_id": l.get("actor_user_id"),
            "action": l.get("action"),
            "entity_type": l.get("entity_type"),
            "entity_id": l.get("entity_id"),
            "metadata": l.get("metadata", {}),
            "created_at": l.get("created_at"),
        }
        for l in logs
    ]
