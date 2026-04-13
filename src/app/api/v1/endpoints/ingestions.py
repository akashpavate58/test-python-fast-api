from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, Response, status

from app.core.config import AppSettings, get_settings
from app.core.exceptions import AppError
from app.models import (
    IngestionAcceptedResponse,
    IngestionJobRecord,
    IngestionJobStatusResponse,
    IngestionQueueMessage,
    IngestionRequest,
    IngestionStatus,
)
from app.services.ingestion import (
    IngestionQueue,
    JobRepository,
    get_ingestion_queue,
    get_job_repository,
)

router = APIRouter()


def _build_status_url(request: Request, job_id: str) -> str:
    return str(request.url_for("get_ingestion_status", job_id=job_id))


def _validate_scheme(url: object, settings: AppSettings) -> None:
    if getattr(url, "scheme", None) not in settings.crawl_allowed_schemes:
        raise AppError(
            "URL scheme is not supported.",
            error_code="validation_error",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )


def _build_job_record(job_id: str, submitted_url: object, status_url: str) -> IngestionJobRecord:
    now = datetime.now(timezone.utc)
    return IngestionJobRecord(
        job_id=job_id,
        submitted_url=submitted_url,
        status=IngestionStatus.accepted,
        current_stage="accepted",
        created_at=now,
        updated_at=now,
    )


@router.post(
    "/ingestions",
    response_model=IngestionAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def submit_ingestion(
    request: Request,
    response: Response,
    ingestion_request: IngestionRequest,
    settings: AppSettings = Depends(get_settings),
    repository: JobRepository = Depends(get_job_repository),
    queue: IngestionQueue = Depends(get_ingestion_queue),
) -> IngestionAcceptedResponse:
    _validate_scheme(ingestion_request.url, settings)

    job_id = uuid4().hex
    status_url = _build_status_url(request, job_id)
    job_record = _build_job_record(job_id, ingestion_request.url, status_url)

    repository.create_job(job_record)

    queue_message = IngestionQueueMessage(
        job_id=job_id,
        submitted_url=ingestion_request.url,
        status_url=status_url,
        created_at=job_record.created_at,
        payload={
            "submitted_url": str(ingestion_request.url),
        },
    )

    try:
        queue.enqueue_message(queue_message)
    except Exception as exc:
        repository.mark_job_failed(
            job_id,
            error_code="queue_submission_failed",
            error_message=str(exc),
        )
        raise AppError(
            "Failed to submit ingestion job.",
            error_code="job_submission_failed",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    response.headers["Location"] = status_url
    response.headers["Retry-After"] = str(settings.ingestion_status_poll_retry_after_seconds)

    return IngestionAcceptedResponse(
        job_id=job_id,
        status=IngestionStatus.accepted,
        submitted_url=ingestion_request.url,
        status_url=status_url,
        created_at=job_record.created_at,
    )


@router.get(
    "/ingestions/{job_id}",
    name="get_ingestion_status",
    response_model=IngestionJobStatusResponse,
)
def get_ingestion_status(
    request: Request,
    job_id: str,
    repository: JobRepository = Depends(get_job_repository),
) -> IngestionJobStatusResponse:
    job_record = repository.get_job(job_id)
    if job_record is None:
        raise AppError(
            "Ingestion job not found.",
            error_code="not_found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return IngestionJobStatusResponse(
        job_id=job_record.job_id,
        submitted_url=job_record.submitted_url,
        status=job_record.status,
        current_stage=job_record.current_stage,
        created_at=job_record.created_at,
        updated_at=job_record.updated_at,
        status_url=_build_status_url(request, job_id),
        pages_discovered=job_record.pages_discovered,
        pages_fetched=job_record.pages_fetched,
        pages_extracted=job_record.pages_extracted,
        pages_failed=job_record.pages_failed,
        chunks_created=job_record.chunks_created,
        chunks_embedded=job_record.chunks_embedded,
        vectors_stored=job_record.vectors_stored,
        error_code=job_record.error_code,
        error_message=job_record.error_message,
    )
