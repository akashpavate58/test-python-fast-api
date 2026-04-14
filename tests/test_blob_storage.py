from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.config import AppSettings
from app.integrations.blob_storage import (
    BlobStorageUploadError,
    InMemoryBlobStorageAdapter,
)
from app.models.ingestion import ExtractedPageContent
from app.services.blob_storage import (
    build_page_blob_name,
    upload_page_text_blob,
)


def test_build_page_blob_name_is_deterministic() -> None:
    first = build_page_blob_name("job-123", "https://example.com/page")
    second = build_page_blob_name("job-123", "https://example.com/page")

    assert first == second
    assert first.startswith("job-123/pages/")
    assert first.endswith(".txt")
    assert build_page_blob_name("job-123", "https://example.com/other") != first


def test_upload_page_text_blob_attaches_blob_reference_metadata() -> None:
    adapter = InMemoryBlobStorageAdapter()
    settings = AppSettings(blob_container_raw_pages="raw-pages")
    extracted_page = ExtractedPageContent(
        submitted_url="https://example.com",
        page_url="https://example.com/page",
        final_url="https://example.com/page",
        fetched_at=datetime.now(timezone.utc),
        http_status=200,
        content_type="text/html",
        content_length=20,
        fetch_error=None,
        html="<p>Example</p>",
        text="Example",
    )

    blob_reference = upload_page_text_blob(adapter, settings, "job-123", extracted_page)

    assert blob_reference.container_name == "raw-pages"
    assert blob_reference.blob_name == build_page_blob_name("job-123", "https://example.com/page")
    assert extracted_page.metadata["blob_reference"]["blob_name"] == blob_reference.blob_name
    assert adapter.blobs[("raw-pages", blob_reference.blob_name)] == b"Example"


def test_upload_page_text_blob_propagates_adapter_errors() -> None:
    class FailingAdapter:
        def upload_blob(
            self,
            container_name: str,
            blob_name: str,
            data: bytes,
            content_type: str = "text/plain; charset=utf-8",
        ) -> str:
            raise RuntimeError("simulated storage failure")

    settings = AppSettings(blob_container_raw_pages="raw-pages")
    extracted_page = ExtractedPageContent(
        submitted_url="https://example.com",
        page_url="https://example.com/page",
        final_url="https://example.com/page",
        fetched_at=datetime.now(timezone.utc),
        http_status=200,
        content_type="text/html",
        content_length=20,
        fetch_error=None,
        html="<p>Example</p>",
        text="Example",
    )

    with pytest.raises(BlobStorageUploadError):
        upload_page_text_blob(FailingAdapter(), settings, "job-123", extracted_page)
