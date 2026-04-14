from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.ingestion import (
    CrawledPage,
    DiscoveredLink,
    ExtractedPageContent,
    IngestionAcceptedResponse,
    IngestionJobStatusResponse,
    IngestionRequest,
    IngestionQueueMessage,
    IngestionStatus,
)


def test_ingestion_request_accepts_valid_url():
    request = IngestionRequest(url="https://example.com/page")

    assert str(request.url) == "https://example.com/page"


def test_ingestion_request_rejects_invalid_url():
    with pytest.raises(ValidationError):
        IngestionRequest(url="not-a-valid-url")


def test_ingestion_accepted_response_shape():
    accepted = IngestionAcceptedResponse(
        job_id="job-123",
        status="queued",
        submitted_url="https://example.com/page",
        status_url="https://api.example.com/status/job-123",
        created_at=datetime.now(timezone.utc),
    )

    assert accepted.job_id == "job-123"
    assert accepted.status == "queued"
    assert str(accepted.submitted_url) == "https://example.com/page"
    assert str(accepted.status_url) == "https://api.example.com/status/job-123"
    assert "created_at" in accepted.model_dump()


def test_ingestion_job_status_response_required_fields_and_enum_validation():
    valid_status = IngestionJobStatusResponse(
        job_id="job-456",
        submitted_url="https://example.com/page",
        status=IngestionStatus.running,
        current_stage="fetching",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        status_url="https://api.example.com/status/job-456",
        pages_discovered=1,
        pages_fetched=1,
        pages_extracted=0,
        pages_failed=0,
        chunks_created=0,
        chunks_embedded=0,
        vectors_stored=0,
        error_code=None,
        error_message=None,
    )

    assert valid_status.status == IngestionStatus.running
    assert valid_status.current_stage == "fetching"

    with pytest.raises(ValidationError):
        IngestionJobStatusResponse(
            job_id="job-456",
            submitted_url="https://example.com/page",
            status="invalid_status",
            current_stage="fetching",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            status_url="https://api.example.com/status/job-456",
            pages_discovered=1,
            pages_fetched=1,
            pages_extracted=0,
            pages_failed=0,
            chunks_created=0,
            chunks_embedded=0,
            vectors_stored=0,
        )


def test_internal_models_preserve_submitted_and_page_url_separation():
    crawled_page = CrawledPage(
        version=1,
        submitted_url="https://example.com",
        page_url="https://example.com/docs/page",
        final_url="https://example.com/docs/page",
        fetched_at=datetime.now(timezone.utc),
        http_status=200,
    )

    discovered_link = DiscoveredLink(
        version=1,
        submitted_url="https://example.com",
        page_url="https://example.com/docs/page",
        link_url="https://example.com/docs/other",
    )

    queue_message = IngestionQueueMessage(
        schema_version=1,
        job_id="job-789",
        submitted_url="https://example.com",
        status_url="https://api.example.com/status/job-789",
        correlation_id="job-789",
        created_at=datetime.now(timezone.utc),
    )

    assert crawled_page.submitted_url != crawled_page.page_url
    assert discovered_link.submitted_url != discovered_link.page_url
    assert str(queue_message.submitted_url) == "https://example.com/"
    assert str(queue_message.status_url) == "https://api.example.com/status/job-789"


def test_extracted_page_content_includes_fetch_metadata():
    extracted = ExtractedPageContent(
        version=1,
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

    assert str(extracted.page_url) == "https://example.com/page"
    assert str(extracted.final_url) == "https://example.com/page"
    assert extracted.text == "Example"
    assert extracted.content_type == "text/html"
