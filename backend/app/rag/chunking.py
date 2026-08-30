import re
import uuid
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from backend.app.core.config import settings
from backend.app.documents.parser import ExtractedDocument


class ChunkOutput(BaseModel):
    id: str
    chunk_index: int
    content: str
    page_number: Optional[int] = None
    section_path: Optional[str] = None
    token_count: int
    metadata: Dict[str, Any] = {}


def estimate_tokens(text: str) -> int:
    """Fast token estimator (approx 4 chars per token for English)."""
    return max(1, len(text) // 4)


class RecursiveStructureChunker:
    def __init__(
        self,
        target_tokens: int = settings.CHUNK_TARGET_SIZE,
        overlap_tokens: int = settings.CHUNK_OVERLAP,
        min_tokens: int = settings.CHUNK_MIN_SIZE,
        max_tokens: int = settings.CHUNK_MAX_SIZE,
    ):
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens

    def _split_into_sections(self, text: str) -> List[tuple[str, str]]:
        """Split text by markdown/custom headers (# Title, ## Section, etc.)"""
        lines = text.split("\n")
        sections: List[tuple[str, str]] = []
        current_section = "General"
        current_lines = []

        for line in lines:
            trimmed = line.strip()
            # Detect Markdown headings or numbered sections
            if trimmed.startswith("#") or re.match(r"^(SECTION|CHAPTER|\d+\.)\s+", trimmed, re.IGNORECASE):
                if current_lines:
                    sections.append((current_section, "\n".join(current_lines).strip()))
                    current_lines = []
                current_section = re.sub(r"^#+\s*", "", trimmed)
                current_lines.append(line)
            else:
                current_lines.append(line)

        if current_lines:
            sections.append((current_section, "\n".join(current_lines).strip()))

        return sections

    def _split_into_paragraphs(self, text: str) -> List[str]:
        return [p.strip() for p in text.split("\n\n") if p.strip()]

    def _split_into_sentences(self, text: str) -> List[str]:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    def chunk_document(
        self,
        extracted_doc: ExtractedDocument,
        document_id: str,
        version: str,
        collection_id: str,
        doc_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[ChunkOutput]:
        chunks: List[ChunkOutput] = []
        chunk_idx = 0
        doc_meta = doc_metadata or {}

        for page in extracted_doc.pages:
            page_num = page.page_number
            sections = self._split_into_sections(page.text)

            for sec_name, sec_text in sections:
                if not sec_text:
                    continue

                paragraphs = self._split_into_paragraphs(sec_text)
                current_chunk_paragraphs: List[str] = []
                current_token_count = 0

                for para in paragraphs:
                    para_tokens = estimate_tokens(para)

                    # If a single paragraph is too huge, split into sentences
                    if para_tokens > self.max_tokens:
                        sentences = self._split_into_sentences(para)
                        for sent in sentences:
                            sent_tokens = estimate_tokens(sent)
                            if current_token_count + sent_tokens > self.target_tokens and current_token_count >= self.min_tokens:
                                # Finalize current chunk
                                chunk_text = " ".join(current_chunk_paragraphs).strip()
                                chunks.append(self._create_chunk(
                                    idx=chunk_idx,
                                    text=chunk_text,
                                    page_number=page_num,
                                    section_path=sec_name,
                                    document_id=document_id,
                                    version=version,
                                    collection_id=collection_id,
                                    doc_meta=doc_meta,
                                ))
                                chunk_idx += 1
                                # Overlap: retain last sentence if possible
                                if self.overlap_tokens > 0 and current_chunk_paragraphs:
                                    current_chunk_paragraphs = [current_chunk_paragraphs[-1], sent]
                                    current_token_count = estimate_tokens(" ".join(current_chunk_paragraphs))
                                else:
                                    current_chunk_paragraphs = [sent]
                                    current_token_count = sent_tokens
                            else:
                                current_chunk_paragraphs.append(sent)
                                current_token_count += sent_tokens
                    else:
                        if current_token_count + para_tokens > self.target_tokens and current_token_count >= self.min_tokens:
                            # Finalize chunk
                            chunk_text = "\n\n".join(current_chunk_paragraphs).strip()
                            chunks.append(self._create_chunk(
                                idx=chunk_idx,
                                text=chunk_text,
                                page_number=page_num,
                                section_path=sec_name,
                                document_id=document_id,
                                version=version,
                                collection_id=collection_id,
                                doc_meta=doc_meta,
                            ))
                            chunk_idx += 1
                            # Overlap: keep last paragraph
                            if self.overlap_tokens > 0 and current_chunk_paragraphs:
                                current_chunk_paragraphs = [current_chunk_paragraphs[-1], para]
                                current_token_count = estimate_tokens("\n\n".join(current_chunk_paragraphs))
                            else:
                                current_chunk_paragraphs = [para]
                                current_token_count = para_tokens
                        else:
                            current_chunk_paragraphs.append(para)
                            current_token_count += para_tokens

                # Flush remaining paragraphs in section
                if current_chunk_paragraphs:
                    chunk_text = "\n\n".join(current_chunk_paragraphs).strip()
                    if chunk_text:
                        chunks.append(self._create_chunk(
                            idx=chunk_idx,
                            text=chunk_text,
                            page_number=page_num,
                            section_path=sec_name,
                            document_id=document_id,
                            version=version,
                            collection_id=collection_id,
                            doc_meta=doc_meta,
                        ))
                        chunk_idx += 1

        return chunks

    def _create_chunk(
        self,
        idx: int,
        text: str,
        page_number: int,
        section_path: str,
        document_id: str,
        version: str,
        collection_id: str,
        doc_meta: Dict[str, Any],
    ) -> ChunkOutput:
        token_count = estimate_tokens(text)
        metadata = {
            "document_id": document_id,
            "version": version,
            "collection_id": collection_id,
            "page_number": page_number,
            "section_path": section_path,
            "token_count": token_count,
            **doc_meta,
        }
        return ChunkOutput(
            id=str(uuid.uuid4()),
            chunk_index=idx,
            content=text,
            page_number=page_number,
            section_path=section_path,
            token_count=token_count,
            metadata=metadata,
        )
