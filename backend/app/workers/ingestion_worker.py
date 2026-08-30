from datetime import datetime
from pymongo.database import Database
from backend.app.documents.parser import parse_document_from_bytes
from backend.app.rag.chunking import RecursiveStructureChunker
from backend.app.rag.embeddings import EmbeddingService
from backend.app.integrations.storage_adapter import get_storage_adapter
from backend.app.core.logging import logger


class IngestionPipeline:
    def __init__(self, db: Database):
        self.db = db
        self.storage = get_storage_adapter()
        self.chunker = RecursiveStructureChunker()
        self.embedding_service = EmbeddingService()

    def process_document_version(self, job_id: str, version_id: str):
        job = self.db.ingestion_jobs.find_one({"id": job_id})
        version = self.db.document_versions.find_one({"id": version_id})
        if not job or not version:
            logger.error(f"Ingestion job {job_id} or version {version_id} not found.")
            return

        doc = self.db.documents.find_one({"id": version["document_id"]})
        if not doc:
            logger.error(f"Document for version {version_id} not found.")
            return

        try:
            # 1. VALIDATING & FETCHING FROM MONGODB GRIDFS
            self.db.ingestion_jobs.update_one(
                {"id": job_id},
                {"$set": {"status": "PROCESSING", "stage": "VALIDATING", "progress": 10}}
            )

            file_bytes = self.storage.get_file_bytes(version["storage_key"])

            # 2. EXTRACTING IN-MEMORY
            self.db.ingestion_jobs.update_one(
                {"id": job_id},
                {"$set": {"stage": "PROCESSING", "progress": 25}}
            )

            extracted = parse_document_from_bytes(file_bytes, doc.get("file_type", ".txt"))
            self.db.documents.update_one(
                {"id": doc["id"]},
                {"$set": {"page_count": extracted.page_count, "ocr_used": extracted.ocr_used}}
            )

            # 3. CHUNKING
            self.db.ingestion_jobs.update_one(
                {"id": job_id},
                {"$set": {"stage": "CHUNKED", "progress": 60}}
            )

            chunks_output = self.chunker.chunk_document(
                extracted_doc=extracted,
                document_id=doc["id"],
                version=version["version"],
                collection_id=doc["collection_id"],
                doc_metadata={
                    "document_title": doc.get("title", ""),
                    "language": doc.get("language", "en"),
                }
            )

            if not chunks_output:
                raise ValueError("No text passages could be extracted from document.")

            # 4. EMBEDDING
            self.db.ingestion_jobs.update_one(
                {"id": job_id},
                {"$set": {"stage": "EMBEDDING", "progress": 75}}
            )

            chunk_texts = [c.content for c in chunks_output]
            embeddings = self.embedding_service.embed_chunks(chunk_texts)

            # 5. INDEXING IN MONGODB
            self.db.ingestion_jobs.update_one(
                {"id": job_id},
                {"$set": {"stage": "INDEXING", "progress": 90}}
            )

            self.db.document_chunks.delete_many({"document_version_id": version["id"]})

            chunk_docs = []
            for chunk_out, emb in zip(chunks_output, embeddings):
                chunk_docs.append({
                    "id": chunk_out.id,
                    "document_id": doc["id"],
                    "document_version_id": version["id"],
                    "collection_id": doc["collection_id"],
                    "version": version["version"],
                    "content": chunk_out.content,
                    "page_number": chunk_out.page_number,
                    "section_path": chunk_out.section_path,
                    "chunk_index": chunk_out.chunk_index,
                    "token_count": chunk_out.token_count,
                    "metadata": chunk_out.metadata,
                    "embedding": emb,
                    "created_at": datetime.utcnow(),
                })

            if chunk_docs:
                self.db.document_chunks.insert_many(chunk_docs)

            # 6. COMPLETED DRAFT
            self.db.ingestion_jobs.update_one(
                {"id": job_id},
                {"$set": {
                    "status": "COMPLETED",
                    "stage": "DRAFT",
                    "progress": 100,
                    "chunks_created": len(chunk_docs),
                    "finished_at": datetime.utcnow(),
                }}
            )

            logger.info(f"Ingestion job {job_id} successfully created {len(chunk_docs)} chunks for doc '{doc.get('title')}'.")

        except Exception as exc:
            self.db.ingestion_jobs.update_one(
                {"id": job_id},
                {"$set": {
                    "status": "FAILED",
                    "stage": "FAILED",
                    "error_code": "INGESTION_FAILED",
                    "error_message": str(exc),
                    "finished_at": datetime.utcnow(),
                }}
            )
            logger.error(f"Ingestion failed for doc version {version_id}: {exc}", exc_info=True)
