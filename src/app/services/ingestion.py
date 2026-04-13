from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Protocol

from app.models.ingestion import IngestionJobRecord, IngestionQueueMessage, IngestionStatus


class JobRepository(Protocol):
    def create_job(self, job_record: IngestionJobRecord) -> None:
        ...

    def mark_job_failed(self, job_id: str, error_code: str, error_message: str) -> None:
        ...

    def get_job(self, job_id: str) -> IngestionJobRecord | None:
        ...


class InMemoryJobRepository:
    def __init__(self) -> None:
        self._jobs: Dict[str, IngestionJobRecord] = {}

    def create_job(self, job_record: IngestionJobRecord) -> None:
        self._jobs[job_record.job_id] = job_record

    def mark_job_failed(self, job_id: str, error_code: str, error_message: str) -> None:
        record = self._jobs.get(job_id)
        if record is not None:
            record.status = IngestionStatus.failed
            record.updated_at = datetime.now(timezone.utc)
            record.current_stage = "failed"
            record.error_code = error_code
            record.error_message = error_message

    def get_job(self, job_id: str) -> IngestionJobRecord | None:
        return self._jobs.get(job_id)


class IngestionQueue(Protocol):
    def enqueue_message(self, message: IngestionQueueMessage) -> None:
        ...


class InMemoryIngestionQueue:
    def __init__(self) -> None:
        self.enqueued_messages: list[IngestionQueueMessage] = []

    def enqueue_message(self, message: IngestionQueueMessage) -> None:
        self.enqueued_messages.append(message)


_default_job_repository = InMemoryJobRepository()
_default_ingestion_queue = InMemoryIngestionQueue()


def get_job_repository() -> JobRepository:
    return _default_job_repository


def get_ingestion_queue() -> IngestionQueue:
    return _default_ingestion_queue
