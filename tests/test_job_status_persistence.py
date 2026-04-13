from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.db.job_status import SqliteJobStatusRepository
from app.models.ingestion import IngestionJobRecord, IngestionStatus
from app.services.ingestion import (
    InvalidJobStatusTransition,
    get_job,
    increment_job_progress,
    transition_job_status,
)


def build_job_record(job_id: str = "job-1") -> IngestionJobRecord:
    now = datetime.now(timezone.utc)
    return IngestionJobRecord(
        job_id=job_id,
        submitted_url="https://example.com",
        status=IngestionStatus.accepted,
        current_stage="accepted",
        created_at=now,
        updated_at=now,
    )


def test_sqlite_job_repository_persists_job_record(tmp_path: Path) -> None:
    database_path = tmp_path / "job_status.db"
    repository = SqliteJobStatusRepository(f"sqlite:///{database_path}")
    job_record = build_job_record()

    repository.create_job(job_record)
    loaded_job = repository.get_job(job_record.job_id)

    assert loaded_job is not None
    assert loaded_job.job_id == job_record.job_id
    assert loaded_job.status == IngestionStatus.accepted
    assert loaded_job.current_stage == "accepted"
    assert loaded_job.created_at == job_record.created_at


def test_valid_job_status_transitions_are_persisted(tmp_path: Path) -> None:
    database_path = tmp_path / "job_status.db"
    repository = SqliteJobStatusRepository(f"sqlite:///{database_path}")
    job_record = build_job_record("job-2")
    repository.create_job(job_record)

    transition_job_status(
        repository,
        job_id=job_record.job_id,
        next_status=IngestionStatus.queued,
        current_stage="queued",
    )
    transition_job_status(
        repository,
        job_id=job_record.job_id,
        next_status=IngestionStatus.running,
        current_stage="fetching",
    )
    transition_job_status(
        repository,
        job_id=job_record.job_id,
        next_status=IngestionStatus.completed,
        current_stage="completed",
        summary="All pages crawled successfully.",
    )

    loaded_job = get_job(repository, job_record.job_id)
    assert loaded_job is not None
    assert loaded_job.status == IngestionStatus.completed
    assert loaded_job.current_stage == "completed"
    assert loaded_job.summary == "All pages crawled successfully."


def test_invalid_job_status_transition_is_rejected(tmp_path: Path) -> None:
    database_path = tmp_path / "job_status.db"
    repository = SqliteJobStatusRepository(f"sqlite:///{database_path}")
    job_record = build_job_record("job-3")
    repository.create_job(job_record)

    with pytest.raises(InvalidJobStatusTransition):
        transition_job_status(
            repository,
            job_id=job_record.job_id,
            next_status=IngestionStatus.completed,
            current_stage="completed",
        )


def test_progress_counters_can_be_incremented(tmp_path: Path) -> None:
    database_path = tmp_path / "job_status.db"
    repository = SqliteJobStatusRepository(f"sqlite:///{database_path}")
    job_record = build_job_record("job-4")
    repository.create_job(job_record)

    increment_job_progress(
        repository,
        job_id=job_record.job_id,
        pages_discovered=3,
        pages_fetched=2,
        pages_extracted=1,
        pages_failed=0,
        chunks_created=5,
        chunks_embedded=4,
        vectors_stored=4,
    )

    loaded_job = repository.get_job(job_record.job_id)
    assert loaded_job is not None
    assert loaded_job.pages_discovered == 3
    assert loaded_job.pages_fetched == 2
    assert loaded_job.pages_extracted == 1
    assert loaded_job.pages_failed == 0
    assert loaded_job.chunks_created == 5
    assert loaded_job.chunks_embedded == 4
    assert loaded_job.vectors_stored == 4


def test_failed_job_persists_error_fields(tmp_path: Path) -> None:
    database_path = tmp_path / "job_status.db"
    repository = SqliteJobStatusRepository(f"sqlite:///{database_path}")
    job_record = build_job_record("job-5")
    repository.create_job(job_record)

    transition_job_status(
        repository,
        job_id=job_record.job_id,
        next_status=IngestionStatus.queued,
        current_stage="queued",
    )
    transition_job_status(
        repository,
        job_id=job_record.job_id,
        next_status=IngestionStatus.running,
        current_stage="fetching",
    )
    transition_job_status(
        repository,
        job_id=job_record.job_id,
        next_status=IngestionStatus.failed,
        current_stage="failed",
        error_code="crawl_failed",
        error_message="Page fetch failed.",
    )

    loaded_job = repository.get_job(job_record.job_id)
    assert loaded_job is not None
    assert loaded_job.status == IngestionStatus.failed
    assert loaded_job.error_code == "crawl_failed"
    assert loaded_job.error_message == "Page fetch failed."
