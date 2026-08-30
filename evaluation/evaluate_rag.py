import os
import sys
import json
import uuid
from datetime import datetime

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.core.database import get_db
from backend.app.rag.orchestrator import RAGOrchestrator


def run_benchmark():
    dataset_path = os.path.join(os.path.dirname(__file__), "dataset.json")
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    db = get_db()
    orchestrator = RAGOrchestrator(db=db)

    user = db.users.find_one({"email": "student@college.edu"})
    if not user:
        user = db.users.find_one({}) or {"id": "eval-user", "name": "Eval User", "role": "user"}

    conv_id = str(uuid.uuid4())
    db.conversations.insert_one({
        "id": conv_id,
        "user_id": user["id"],
        "title": "Automated RAG Evaluation",
        "language": "en",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })

    print("=" * 70)
    print(f"STARTING RAG BENCHMARK EVALUATION ({len(dataset)} Queries)")
    print("=" * 70)

    total_queries = len(dataset)
    grounded_correct = 0
    unknown_correct = 0
    citation_correct = 0
    recall_hits = 0
    total_retrieval_ms = 0.0
    total_gen_ms = 0.0

    for idx, item in enumerate(dataset, start=1):
        q = item["question"]
        expected_status = item["expected_status"]
        target_doc = item.get("target_document")

        result = orchestrator.execute_rag(
            conversation_id=conv_id,
            question=q,
            user=user,
        )

        total_retrieval_ms += result.retrieval_ms
        total_gen_ms += result.generation_ms

        is_status_match = (result.evidence_status == expected_status)
        if expected_status == "insufficient_evidence" and is_status_match:
            unknown_correct += 1
        elif expected_status == "grounded" and is_status_match:
            grounded_correct += 1

        has_valid_citations = True
        if expected_status == "grounded":
            if not result.sources:
                has_valid_citations = False
            if target_doc:
                doc_titles = [s["title"] for s in result.sources]
                if target_doc in doc_titles:
                    recall_hits += 1

        if has_valid_citations:
            citation_correct += 1

        status_marker = "PASS" if is_status_match else "FAIL"
        print(f"[{idx:02d}/{total_queries:02d}] [{status_marker}] Q: {q[:45]}... | Status: {result.evidence_status} ({result.retrieval_ms}ms)")

    # Clean up evaluation conversation
    db.conversations.delete_one({"id": conv_id})
    db.messages.delete_many({"conversation_id": conv_id})

    grounded_total = sum(1 for d in dataset if d["expected_status"] == "grounded")
    unknown_total = sum(1 for d in dataset if d["expected_status"] == "insufficient_evidence")

    grounded_accuracy = (grounded_correct / max(1, grounded_total)) * 100
    unknown_accuracy = (unknown_correct / max(1, unknown_total)) * 100
    recall_rate = (recall_hits / max(1, grounded_total)) * 100
    avg_ret_ms = round(total_retrieval_ms / max(1, total_queries), 2)
    avg_gen_ms = round(total_gen_ms / max(1, total_queries), 2)

    print("\n" + "=" * 70)
    print("RAG BENCHMARK EVALUATION RESULTS")
    print("=" * 70)
    print(f"Total Benchmark Queries:     {total_queries}")
    print(f"Recall@k (Target Doc Hit):   {recall_rate:.1f}%")
    print(f"Groundedness Accuracy:       {grounded_accuracy:.1f}%")
    print(f"Unknown-Refusal Accuracy:    {unknown_accuracy:.1f}%")
    print(f"Citation Accuracy:           {(citation_correct / total_queries) * 100:.1f}%")
    print(f"Average Retrieval Latency:   {avg_ret_ms} ms")
    print(f"Average Generation Latency:  {avg_gen_ms} ms")
    print("=" * 70)


if __name__ == "__main__":
    run_benchmark()
