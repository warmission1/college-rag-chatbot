import os
import pytest
from backend.app.documents.parser import parse_document, clean_text
from backend.app.core.errors import DocumentInvalidError


def test_clean_text():
    raw = "Hello   world!\r\n\r\n\r\nThis is   a test.\n\n\n\nDone."
    cleaned = clean_text(raw)
    assert "\r" not in cleaned
    assert "   " not in cleaned
    assert "\n\n\n" not in cleaned


def test_parse_text_document():
    test_path = "sample_data/admissions_policy_2026.txt"
    if os.path.exists(test_path):
        extracted = parse_document(test_path)
        assert extracted.page_count >= 1
        assert len(extracted.pages) >= 1
        assert "Admissions" in extracted.pages[0].text


def test_unsupported_file_extension():
    with pytest.raises(DocumentInvalidError):
        parse_document("invalid_file.xyz")
