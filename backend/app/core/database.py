import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from pymongo import MongoClient
from pymongo.database import Database
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.auth.security import get_password_hash
from backend.app.rag.chunking import RecursiveStructureChunker
from backend.app.rag.embeddings import EmbeddingService
from backend.app.documents.parser import parse_text_bytes

_mongo_client: Optional[MongoClient] = None
_mongo_db: Optional[Database] = None


class MockCursor:
    def __init__(self, docs: List[Dict[str, Any]]):
        self._docs = docs

    def sort(self, key_or_list, direction=1):
        if isinstance(key_or_list, list):
            k, d = key_or_list[0]
            rev = d == -1
        else:
            k = key_or_list
            rev = direction == -1
        self._docs.sort(key=lambda x: x.get(k, ""), reverse=rev)
        return self

    def limit(self, n: int):
        self._docs = self._docs[:n]
        return self

    def __iter__(self):
        return iter(self._docs)

    def __len__(self):
        return len(self._docs)


class InMemoryCollection:
    def __init__(self, name: str):
        self.name = name
        self._docs: List[Dict[str, Any]] = []

    def create_index(self, key, unique=False):
        pass

    def _matches(self, doc: Dict[str, Any], filter_dict: Dict[str, Any]) -> bool:
        for k, v in filter_dict.items():
            if isinstance(v, dict):
                if "$in" in v:
                    if doc.get(k) not in v["$in"]:
                        return False
                elif "$ne" in v:
                    if doc.get(k) == v["$ne"]:
                        return False
                elif "$lt" in v:
                    if doc.get(k) is None or doc.get(k) >= v["$lt"]:
                        return False
            else:
                if doc.get(k) != v:
                    return False
        return True

    def find_one(self, filter_dict: Dict[str, Any] = None, sort=None) -> Optional[Dict[str, Any]]:
        filter_dict = filter_dict or {}
        matches = [d for d in self._docs if self._matches(d, filter_dict)]
        if sort and matches:
            k, d = sort[0]
            matches.sort(key=lambda x: x.get(k, ""), reverse=(d == -1))
        return dict(matches[0]) if matches else None

    def find(self, filter_dict: Dict[str, Any] = None) -> MockCursor:
        filter_dict = filter_dict or {}
        matches = [dict(d) for d in self._docs if self._matches(d, filter_dict)]
        return MockCursor(matches)

    def count_documents(self, filter_dict: Dict[str, Any] = None) -> int:
        filter_dict = filter_dict or {}
        return sum(1 for d in self._docs if self._matches(d, filter_dict))

    def insert_one(self, doc: Dict[str, Any]):
        d = dict(doc)
        if "id" not in d and "_id" not in d:
            d["id"] = str(uuid.uuid4())
        self._docs.append(d)
        return d

    def insert_many(self, docs: List[Dict[str, Any]]):
        for d in docs:
            self.insert_one(d)

    def update_one(self, filter_dict: Dict[str, Any], update_dict: Dict[str, Any]):
        set_vals = update_dict.get("$set", {})
        for doc in self._docs:
            if self._matches(doc, filter_dict):
                doc.update(set_vals)
                break

    def update_many(self, filter_dict: Dict[str, Any], update_dict: Dict[str, Any]):
        set_vals = update_dict.get("$set", {})
        for doc in self._docs:
            if self._matches(doc, filter_dict):
                doc.update(set_vals)

    def delete_one(self, filter_dict: Dict[str, Any]):
        for i, doc in enumerate(self._docs):
            if self._matches(doc, filter_dict):
                del self._docs[i]
                break

    def delete_many(self, filter_dict: Dict[str, Any]):
        self._docs = [d for d in self._docs if not self._matches(d, filter_dict)]


class InMemoryMongoDb:
    def __init__(self):
        self.users = InMemoryCollection("users")
        self.collections = InMemoryCollection("collections")
        self.documents = InMemoryCollection("documents")
        self.document_versions = InMemoryCollection("document_versions")
        self.document_chunks = InMemoryCollection("document_chunks")
        self.conversations = InMemoryCollection("conversations")
        self.messages = InMemoryCollection("messages")
        self.feedback = InMemoryCollection("feedback")
        self.ingestion_jobs = InMemoryCollection("ingestion_jobs")
        self.audit_logs = InMemoryCollection("audit_logs")
        self.fs_files = InMemoryCollection("fs.files")
        self.fs_chunks = InMemoryCollection("fs.chunks")
        self.seed_in_memory_data()

    def command(self, cmd: str):
        return {"ok": 1}

    def seed_in_memory_data(self):
        # 1. Default Users
        if self.users.count_documents({}) == 0:
            self.users.insert_one({
                "id": "admin-demo-id",
                "name": "System Administrator",
                "email": "admin@college.edu",
                "hashed_password": get_password_hash("admin123"),
                "role": "super-admin",
                "status": "active",
                "created_at": datetime.utcnow(),
            })
            self.users.insert_one({
                "id": "student-demo-id",
                "name": "Rahul Sharma",
                "email": "student@college.edu",
                "hashed_password": get_password_hash("student123"),
                "role": "user",
                "status": "active",
                "created_at": datetime.utcnow(),
            })

        # 2. Default Collections
        cols = [
            ("admissions", "Admissions & Enrollment", "Application guidelines, eligibility, cutoffs, and deadlines."),
            ("hostel", "Hostel & Campus Life", "Hostel allotment, room rules, curfew hours, and mess charges."),
            ("academics", "Academics & Calendar", "Academic calendar, holidays, attendance criteria, and course schedules."),
            ("finance", "Fees & Scholarships", "Tuition fees, payment schedules, late fines, and scholarships."),
            ("examinations", "Examinations & Grading", "10-point GPA scale, internal assessment weightage, and exam regulations."),
        ]
        if self.collections.count_documents({}) == 0:
            for cid, cname, desc in cols:
                self.collections.insert_one({
                    "id": cid,
                    "name": cname,
                    "description": desc,
                    "visibility": "public",
                    "status": "active",
                    "created_at": datetime.utcnow(),
                })

        # 3. Default Sample Documents & Chunks
        if self.documents.count_documents({}) == 0:
            sample_docs = [
                ("Admissions Policy 2026-27", "admissions", "sample_data/admissions_policy_2026.txt", "v1.0"),
                ("Hostel Handbook 2026-27", "hostel", "sample_data/hostel_handbook_2026.txt", "v2.0"),
                ("CSE & Department Fee Schedule 2026-27", "finance", "sample_data/cse_fee_structure_2026.txt", "v1.0"),
                ("Examination Regulations 2026-27", "examinations", "sample_data/exam_regulations_2026.txt", "v1.0"),
                ("Official Academic Calendar 2026-27", "academics", "sample_data/academic_calendar_2026_27.txt", "v1.0"),
            ]
            from backend.app.integrations.embedding_adapter import MockEmbeddingAdapter
            chunker = RecursiveStructureChunker()
            embedder = EmbeddingService(adapter=MockEmbeddingAdapter(dim=settings.EMBEDDING_DIMENSIONS))

            import os
            for title, cid, path, ver in sample_docs:
                if os.path.exists(path):
                    with open(path, "rb") as f:
                        b = f.read()
                    doc_id = str(uuid.uuid4())
                    ver_id = str(uuid.uuid4())
                    self.documents.insert_one({
                        "id": doc_id,
                        "title": title,
                        "collection_id": cid,
                        "owner_id": "admin-demo-id",
                        "status": "published",
                        "current_version": ver,
                        "current_version_id": ver_id,
                        "checksum": "checksum",
                        "language": "en",
                        "storage_key": "in_memory",
                        "file_type": ".txt",
                        "file_size_bytes": len(b),
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                    })
                    self.document_versions.insert_one({
                        "id": ver_id,
                        "document_id": doc_id,
                        "version": ver,
                        "status": "published",
                        "checksum": "checksum",
                        "storage_key": "in_memory",
                        "uploaded_at": datetime.utcnow(),
                        "published_at": datetime.utcnow(),
                    })
                    extracted = parse_text_bytes(b)
                    chunks = chunker.chunk_document(
                        extracted_doc=extracted,
                        document_id=doc_id,
                        version=ver,
                        collection_id=cid,
                        doc_metadata={"document_title": title, "language": "en"}
                    )
                    texts = [c.content for c in chunks]
                    embs = embedder.embed_chunks(texts)
                    for c_out, emb in zip(chunks, embs):
                        self.document_chunks.insert_one({
                            "id": c_out.id,
                            "document_id": doc_id,
                            "document_version_id": ver_id,
                            "collection_id": cid,
                            "version": ver,
                            "content": c_out.content,
                            "page_number": c_out.page_number,
                            "section_path": c_out.section_path,
                            "chunk_index": c_out.chunk_index,
                            "token_count": c_out.token_count,
                            "metadata": c_out.metadata,
                            "embedding": emb,
                            "created_at": datetime.utcnow(),
                        })


_in_memory_db = InMemoryMongoDb()


def get_db():
    global _mongo_client, _mongo_db
    uri = settings.MONGODB_URI.strip()
    if uri:
        if _mongo_db is None:
            try:
                _mongo_client = MongoClient(uri, serverSelectionTimeoutMS=5000)
                _mongo_client.admin.command("ping")
                db_name = settings.MONGODB_DB_NAME.strip() or "college_rag"
                _mongo_db = _mongo_client[db_name]
                return _mongo_db
            except Exception as exc:
                logger.warning(f"Could not connect to external MongoDB: {exc}. Using zero-friction in-memory test store.")
                return _in_memory_db
        return _mongo_db
    
    # Return In-Memory Database for instant testing without setup!
    return _in_memory_db


def init_db():
    """Initializes in-memory seed data or MongoDB database indexes."""
    _in_memory_db.seed_in_memory_data()
    
    uri = settings.MONGODB_URI.strip()
    if uri:
        try:
            db = get_db()
            db.users.create_index("email", unique=True)
            db.collections.create_index("id", unique=True)
            db.documents.create_index("id", unique=True)
            db.document_chunks.create_index("id", unique=True)
            db.document_chunks.create_index("document_id")
            db.document_chunks.create_index("document_version_id")
            db.document_chunks.create_index("collection_id")
            db.conversations.create_index("user_id")
            db.messages.create_index("conversation_id")
            db.ingestion_jobs.create_index("id", unique=True)
            db.audit_logs.create_index("created_at")
            logger.info("MongoDB cloud connection established.")
        except Exception as exc:
            logger.info("Using instant in-memory test database (Zero setup required).")
    else:
        logger.info("Instant in-memory testing mode active. Ready to use immediately!")
