from __future__ import annotations

import hashlib
from typing import Iterable

from app.core.config import get_settings
from app.models.ingestion import BlobReference, TextChunk


def _build_chunk_id(
    job_id: str,
    submitted_url: str,
    page_url: str,
    start_index: int,
    end_index: int,
) -> str:
    digest = hashlib.sha256(
        f"{job_id}|{submitted_url}|{page_url}|{start_index}|{end_index}".encode(
            "utf-8"
        )
    ).hexdigest()
    return digest


def chunk_page_text(
    job_id: str,
    submitted_url: str,
    page_url: str,
    page_blob_reference: BlobReference,
    text: str,
    chunk_size_chars: int | None = None,
    chunk_overlap_chars: int | None = None,
    min_non_whitespace_chars: int | None = None,
) -> list[TextChunk]:
    settings = get_settings()
    chunk_size_chars = chunk_size_chars or settings.chunk_size_chars
    chunk_overlap_chars = chunk_overlap_chars or settings.chunk_overlap_chars
    min_non_whitespace_chars = (
        min_non_whitespace_chars
        if min_non_whitespace_chars is not None
        else settings.chunk_min_non_whitespace_chars
    )

    normalized_text = text or ""
    if not normalized_text.strip():
        return []
    if len(normalized_text.strip()) < min_non_whitespace_chars:
        return []

    step = chunk_size_chars - chunk_overlap_chars
    chunks: list[TextChunk] = []
    start_index = 0
    text_length = len(normalized_text)

    while start_index < text_length:
        end_index = min(start_index + chunk_size_chars, text_length)
        chunk_text = normalized_text[start_index:end_index]
        if chunk_text.strip():
            chunks.append(
                TextChunk(
                    job_id=job_id,
                    submitted_url=submitted_url,
                    page_url=page_url,
                    page_blob_reference=page_blob_reference,
                    chunk_id=_build_chunk_id(
                        job_id,
                        submitted_url,
                        page_url,
                        start_index,
                        end_index,
                    ),
                    chunk_index=len(chunks),
                    total_chunks=0,
                    text=chunk_text,
                    start_index=start_index,
                    end_index=end_index,
                )
            )
        if end_index == text_length:
            break
        start_index += step

    total_chunks = len(chunks)
    for index, chunk in enumerate(chunks):
        chunk.chunk_index = index
        chunk.total_chunks = total_chunks

    return chunks
