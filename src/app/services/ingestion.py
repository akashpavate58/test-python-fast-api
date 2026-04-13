from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Protocol

from app.core.config import get_settings
from app.db.job_status import SqliteJobStatusRepository
from app.models.ingestion import IngestionJobRecord, IngestionQueueMessage, IngestionStatus


class InvalidJobStatusTransition(ValueError):
    pass


ALLOWED_JOB_STATUS_TRANSITIONS: dict[IngestionStatus, set[IngestionStatus]] = {
    IngestionStatus.accepted: {IngestionStatus.queued},
    IngestionStatus.queued: {IngestionStatus.running},
    IngestionStatus.running: {
        IngestionStatus.completed,
        IngestionStatus.failed,
        IngestionStatus.partially_completed,
    },
    IngestionStatus.completed: set(),
    IngestionStatus.failed: set(),
    IngestionStatus.partially_completed: set(),
}


def validate_status_transition(
    current_status: IngestionStatus, next_status: IngestionStatus
) -> None:
    allowed = ALLOWED_JOB_STATUS_TRANSITIONS.get(current_status, set())
    if next_status not in allowed:
        raise InvalidJobStatusTransition(
            f"Invalid transition from {current_status.value} to {next_status.value}."
        )


class JobRepository(Protocol):
    def create_job(self, job_record: IngestionJobRecord) -> None:
        ...

    def get_job(self, job_id: str) -> IngestionJobRecord | None:
        ...

    def update_job_status(
        self,
        job_id: str,
        status: IngestionStatus,
        current_stage: str,
        error_code: str | None = None,
        error_message: str | None = None,
        summary: str | None = None,
    ) -> None:
        ...

    def increment_job_progress(
        self,
        job_id: str,
        pages_discovered: int = 0,
        pages_fetched: int = 0,
        pages_extracted: int = 0,
        pages_failed: int = 0,
        chunks_created: int = 0,
        chunks_embedded: int = 0,
        vectors_stored: int = 0,
    ) -> None:
        ...

    def mark_job_failed(self, job_id: str, error_code: str, error_message: str) -> None:
        ...


class InMemoryJobRepository:
    def __init__(self) -> None:
        self._jobs: Dict[str, IngestionJobRecord] = {}

    def create_job(self, job_record: IngestionJobRecord) -> None:
        self._jobs[job_record.job_id] = job_record

    def get_job(self, job_id: str) -> IngestionJobRecord | None:
        return self._jobs.get(job_id)

    def update_job_status(
        self,
        job_id: str,
        status: IngestionStatus,
        current_stage: str,
        error_code: str | None = None,
        error_message: str | None = None,
        summary: str | None = None,
    ) -> None:
        record = self._jobs.get(job_id)
        if record is None:
            return
        record.status = status
        record.current_stage = current_stage
        record.updated_at = datetime.now(timezone.utc)
        record.error_code = error_code
        record.error_message = error_message
        if summary is not None:
            setattr(record, "summary", summary)

    def increment_job_progress(
        self,
        job_id: str,
        pages_discovered: int = 0,
        pages_fetched: int = 0,
        pages_extracted: int = 0,
        pages_failed: int = 0,
        chunks_created: int = 0,
        chunks_embedded: int = 0,
        vectors_stored: int = 0,
    ) -> None:
        record = self._jobs.get(job_id)
        if record is None:
            return
        record.pages_discovered += pages_discovered
        record.pages_fetched += pages_fetched
        record.pages_extracted += pages_extracted
        record.pages_failed += pages_failed
        record.chunks_created += chunks_created
        record.chunks_embedded += chunks_embedded
        record.vectors_stored += vectors_stored
        record.updated_at = datetime.now(timezone.utc)

    def mark_job_failed(self, job_id: str, error_code: str, error_message: str) -> None:
        self.update_job_status(
            job_id=job_id,
            status=IngestionStatus.failed,
            current_stage="failed",
            error_code=error_code,
            error_message=error_message,
        )


class IngestionQueue(Protocol):
    def enqueue_message(self, message: IngestionQueueMessage) -> None:
        ...


class InMemoryIngestionQueue:
    def __init__(self) -> None:
        self.enqueued_messages: list[IngestionQueueMessage] = []

    def enqueue_message(self, message: IngestionQueueMessage) -> None:
        self.enqueued_messages.append(message)


_default_job_repository = SqliteJobStatusRepository(
    database_url=get_settings().job_status_database_url
)
_default_ingestion_queue = InMemoryIngestionQueue()


def get_job_repository() -> JobRepository:
    return _default_job_repository


def get_ingestion_queue() -> IngestionQueue:
    return _default_ingestion_queue


def get_job(repository: JobRepository, job_id: str) -> IngestionJobRecord | None:
    return repository.get_job(job_id)


def transition_job_status(
    repository: JobRepository,
    job_id: str,
    next_status: IngestionStatus,
    current_stage: str,
    error_code: str | None = None,
    error_message: str | None = None,
    summary: str | None = None,
) -> None:
    job_record = repository.get_job(job_id)
    if job_record is None:
        raise ValueError("Job not found.")
    validate_status_transition(job_record.status, next_status)
    repository.update_job_status(
        job_id=job_id,
        status=next_status,
        current_stage=current_stage,
        error_code=error_code,
        error_message=error_message,
        summary=summary,
    )


def increment_job_progress(
    repository: JobRepository,
    job_id: str,
    pages_discovered: int = 0,
    pages_fetched: int = 0,
    pages_extracted: int = 0,
    pages_failed: int = 0,
    chunks_created: int = 0,
    chunks_embedded: int = 0,
    vectors_stored: int = 0,
) -> None:
    job_record = repository.get_job(job_id)
    if job_record is None:
        raise ValueError("Job not found.")
    repository.increment_job_progress(
        job_id=job_id,
        pages_discovered=pages_discovered,
        pages_fetched=pages_fetched,
        pages_extracted=pages_extracted,
        pages_failed=pages_failed,
        chunks_created=chunks_created,
        chunks_embedded=chunks_embedded,
        vectors_stored=vectors_stored,
    )
