import pytest
from backend.app.documents.parser import ExtractedDocument, ExtractedPage
from backend.app.rag.chunking import RecursiveStructureChunker, estimate_tokens


def test_estimate_tokens():
    text = "This is a short sample sentence for token testing."
    tokens = estimate_tokens(text)
    assert tokens > 0
    assert tokens == len(text) // 4


def test_recursive_chunker_sections():
    sample_text = (
        "# ADMISSION GUIDELINES\n\n"
        "All candidates must submit their application online before July 15, 2026.\n\n"
        "## ELIGIBILITY CRITERIA\n\n"
        "Candidates require 60% in Physics, Chemistry, and Mathematics.\n\n"
        "## FEE STRUCTURE\n\n"
        "The application fee is INR 1,200 for General candidates."
    )
    doc = ExtractedDocument(
        page_count=1,
        pages=[ExtractedPage(page_number=1, text=sample_text, headings=["ADMISSION GUIDELINES", "ELIGIBILITY CRITERIA", "FEE STRUCTURE"])],
    )
    
    chunker = RecursiveStructureChunker(target_tokens=200, overlap_tokens=20, min_tokens=10, max_tokens=400)
    chunks = chunker.chunk_document(
        extracted_doc=doc,
        document_id="doc-test-1",
        version="v1.0",
        collection_id="admissions",
    )
    
    assert len(chunks) >= 1
    for c in chunks:
        assert c.id is not None
        assert c.token_count > 0
        assert c.metadata["document_id"] == "doc-test-1"
        assert c.metadata["version"] == "v1.0"
