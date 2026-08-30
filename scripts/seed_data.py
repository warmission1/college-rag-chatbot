import os
import sys
import uuid
import hashlib
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.core.database import get_db, init_db
from backend.app.auth.security import get_password_hash
from backend.app.integrations.storage_adapter import get_storage_adapter
from backend.app.workers.ingestion_worker import IngestionPipeline


def seed_database():
    print("Connecting to MongoDB database...")
    init_db()
    db = get_db()

    try:
        # 1. Create Default Users
        admin_email = "admin@college.edu"
        admin = db.users.find_one({"email": admin_email})
        if not admin:
            admin_id = str(uuid.uuid4())
            admin = {
                "id": admin_id,
                "name": "System Administrator",
                "email": admin_email,
                "hashed_password": get_password_hash("admin123"),
                "role": "super-admin",
                "status": "active",
                "created_at": datetime.utcnow(),
            }
            db.users.insert_one(admin)
            print(f"Created Super-Admin user: {admin_email} (password: admin123)")
        else:
            print(f"Super-Admin already exists: {admin_email}")

        student_email = "student@college.edu"
        student = db.users.find_one({"email": student_email})
        if not student:
            student_id = str(uuid.uuid4())
            student = {
                "id": student_id,
                "name": "Rahul Sharma",
                "email": student_email,
                "hashed_password": get_password_hash("student123"),
                "role": "user",
                "status": "active",
                "created_at": datetime.utcnow(),
            }
            db.users.insert_one(student)
            print(f"Created Student user: {student_email} (password: student123)")

        # 2. Create Default Collections
        collections_data = [
            ("admissions", "Admissions & Enrollment", "Application guidelines, eligibility, cutoffs, and deadlines."),
            ("hostel", "Hostel & Campus Life", "Hostel allotment, room rules, curfew hours, and mess charges."),
            ("academics", "Academics & Calendar", "Academic calendar, holidays, attendance criteria, and course schedules."),
            ("finance", "Fees & Scholarships", "Tuition fees, payment schedules, late fines, and scholarships."),
            ("examinations", "Examinations & Grading", "10-point GPA scale, internal assessment weightage, and exam regulations."),
        ]

        for col_id, col_name, desc in collections_data:
            col = db.collections.find_one({"id": col_id})
            if not col:
                db.collections.insert_one({
                    "id": col_id,
                    "name": col_name,
                    "description": desc,
                    "visibility": "public",
                    "status": "active",
                    "created_at": datetime.utcnow(),
                })
                print(f"Created Collection: {col_name} ({col_id})")

        # 3. Ingest and Publish Sample Documents
        sample_docs = [
            ("Admissions Policy 2026-27", "admissions", "sample_data/admissions_policy_2026.txt", "v1.0"),
            ("Hostel Handbook 2026-27", "hostel", "sample_data/hostel_handbook_2026.txt", "v2.0"),
            ("CSE & Department Fee Schedule 2026-27", "finance", "sample_data/cse_fee_structure_2026.txt", "v1.0"),
            ("Examination Regulations 2026-27", "examinations", "sample_data/exam_regulations_2026.txt", "v1.0"),
            ("Official Academic Calendar 2026-27", "academics", "sample_data/academic_calendar_2026_27.txt", "v1.0"),
        ]

        storage = get_storage_adapter()
        worker = IngestionPipeline(db=db)

        for title, col_id, file_path, version_str in sample_docs:
            if not os.path.exists(file_path):
                print(f"Warning: File {file_path} not found, skipping.")
                continue

            existing_doc = db.documents.find_one({"title": title})
            if existing_doc:
                old_doc_id = existing_doc["id"]
                db.document_chunks.delete_many({"document_id": old_doc_id})
                db.document_versions.delete_many({"document_id": old_doc_id})
                db.documents.delete_one({"id": old_doc_id})

            with open(file_path, "rb") as f:
                content_bytes = f.read()

            sha256 = hashlib.sha256(content_bytes).hexdigest()
            import io
            storage_key, stored_path, file_size = storage.save_file(io.BytesIO(content_bytes), os.path.basename(file_path))

            doc_id = str(uuid.uuid4())
            version_id = str(uuid.uuid4())
            now = datetime.utcnow()

            doc = {
                "id": doc_id,
                "title": title,
                "collection_id": col_id,
                "owner_id": admin["id"],
                "status": "published",
                "current_version": version_str,
                "current_version_id": version_id,
                "checksum": sha256,
                "storage_key": storage_key,
                "file_type": ".txt",
                "file_size_bytes": file_size,
                "created_at": now,
                "updated_at": now,
            }
            db.documents.insert_one(doc)

            doc_ver = {
                "id": version_id,
                "document_id": doc_id,
                "version": version_str,
                "status": "published",
                "checksum": sha256,
                "storage_key": storage_key,
                "uploaded_at": now,
                "published_at": now,
            }
            db.document_versions.insert_one(doc_ver)

            job_id = str(uuid.uuid4())
            job = {
                "id": job_id,
                "document_version_id": version_id,
                "status": "QUEUED",
                "stage": "UPLOADED",
                "progress": 0,
                "started_at": now,
            }
            db.ingestion_jobs.insert_one(job)

            print(f"Processing and indexing: '{title}' with Gemini embeddings...")
            worker.process_document_version(job_id, version_id)

            db.documents.update_one({"id": doc_id}, {"$set": {"status": "published"}})
            db.document_versions.update_many({"document_id": doc_id}, {"$set": {"status": "published"}})
            print(f"Successfully published: '{title}'")

        print("\nAll MongoDB database seeding completed successfully!")
    except Exception as e:
        print(f"MongoDB Notice: {e}. Connect your MongoDB instance when ready.")


if __name__ == "__main__":
    seed_database()
