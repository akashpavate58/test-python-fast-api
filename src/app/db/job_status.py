from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.ingestion import IngestionJobRecord, IngestionStatus

_DEFAULT_DATABASE_URL = "sqlite:///./job_status.db"


class JobStatusRepositoryError(Exception):
    pass


class SqliteJobStatusRepository:
    def __init__(self, database_url: str = _DEFAULT_DATABASE_URL) -> None:
        self.database_path = self._resolve_database_path(database_url)
        self._connection = sqlite3.connect(
            self.database_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        self._ensure_schema()

    @staticmethod
    def _resolve_database_path(database_url: str) -> str:
        if not database_url:
            database_url = _DEFAULT_DATABASE_URL

        if database_url.startswith("sqlite:///"):
            path = database_url[len("sqlite:///"):]
            return path or ":memory:"

        if database_url.startswith("sqlite://"):
            path = database_url[len("sqlite://"):]
            return path or ":memory:"

        raise JobStatusRepositoryError(
            "Unsupported database URL. Use sqlite:///PATH or sqlite:///:memory:."
        )

    def _ensure_schema(self) -> None:
        path = Path(self.database_path)
        if path.parent and str(path.parent) != ".":
            path.parent.mkdir(parents=True, exist_ok=True)

        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ingestion_jobs (
                job_id TEXT PRIMARY KEY,
                submitted_url TEXT NOT NULL,
                status TEXT NOT NULL,
                current_stage TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                pages_discovered INTEGER NOT NULL DEFAULT 0,
                pages_fetched INTEGER NOT NULL DEFAULT 0,
                pages_extracted INTEGER NOT NULL DEFAULT 0,
                pages_failed INTEGER NOT NULL DEFAULT 0,
                chunks_created INTEGER NOT NULL DEFAULT 0,
                chunks_embedded INTEGER NOT NULL DEFAULT 0,
                vectors_stored INTEGER NOT NULL DEFAULT 0,
                error_code TEXT,
                error_message TEXT,
                summary TEXT
            )
            """
        ).connection.commit()

    def create_job(self, job_record: IngestionJobRecord) -> None:
        try:
            self._connection.execute(
                """
                INSERT INTO ingestion_jobs (
                    job_id,
                    submitted_url,
                    status,
                    current_stage,
                    created_at,
                    updated_at,
                    pages_discovered,
                    pages_fetched,
                    pages_extracted,
                    pages_failed,
                    chunks_created,
                    chunks_embedded,
                    vectors_stored,
                    error_code,
                    error_message,
                    summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_record.job_id,
                    str(job_record.submitted_url),
                    job_record.status.value,
                    job_record.current_stage,
                    job_record.created_at.isoformat(),
                    job_record.updated_at.isoformat(),
                    job_record.pages_discovered,
                    job_record.pages_fetched,
                    job_record.pages_extracted,
                    job_record.pages_failed,
                    job_record.chunks_created,
                    job_record.chunks_embedded,
                    job_record.vectors_stored,
                    job_record.error_code,
                    job_record.error_message,
                    getattr(job_record, "summary", None),
                ),
            )
            self._connection.commit()
        except sqlite3.IntegrityError as exc:
            raise JobStatusRepositoryError("Job record already exists.") from exc

    def get_job(self, job_id: str) -> IngestionJobRecord | None:
        cursor = self._connection.execute(
            "SELECT * FROM ingestion_jobs WHERE job_id = ?", (job_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_job_record(row)

    def update_job_status(
        self,
        job_id: str,
        status: IngestionStatus,
        current_stage: str,
        error_code: str | None = None,
        error_message: str | None = None,
        summary: str | None = None,
    ) -> None:
        updated_at = datetime.now(timezone.utc).isoformat()
        self._connection.execute(
            """
            UPDATE ingestion_jobs
            SET status = ?,
                current_stage = ?,
                updated_at = ?,
                error_code = ?,
                error_message = ?,
                summary = COALESCE(?, summary)
            WHERE job_id = ?
            """,
            (status.value, current_stage, updated_at, error_code, error_message, summary, job_id),
        )
        self._connection.commit()

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
        if any(value < 0 for value in (
            pages_discovered,
            pages_fetched,
            pages_extracted,
            pages_failed,
            chunks_created,
            chunks_embedded,
            vectors_stored,
        )):
            raise JobStatusRepositoryError("Progress counters must be zero or positive.")

        updated_at = datetime.now(timezone.utc).isoformat()
        self._connection.execute(
            """
            UPDATE ingestion_jobs
            SET pages_discovered = pages_discovered + ?,
                pages_fetched = pages_fetched + ?,
                pages_extracted = pages_extracted + ?,
                pages_failed = pages_failed + ?,
                chunks_created = chunks_created + ?,
                chunks_embedded = chunks_embedded + ?,
                vectors_stored = vectors_stored + ?,
                updated_at = ?
            WHERE job_id = ?
            """,
            (
                pages_discovered,
                pages_fetched,
                pages_extracted,
                pages_failed,
                chunks_created,
                chunks_embedded,
                vectors_stored,
                updated_at,
                job_id,
            ),
        )
        self._connection.commit()

    @staticmethod
    def _row_to_job_record(row: Any) -> IngestionJobRecord:
        return IngestionJobRecord(
            job_id=row["job_id"],
            submitted_url=row["submitted_url"],
            status=IngestionStatus(row["status"]),
            current_stage=row["current_stage"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            pages_discovered=row["pages_discovered"],
            pages_fetched=row["pages_fetched"],
            pages_extracted=row["pages_extracted"],
            pages_failed=row["pages_failed"],
            chunks_created=row["chunks_created"],
            chunks_embedded=row["chunks_embedded"],
            vectors_stored=row["vectors_stored"],
            error_code=row["error_code"],
            error_message=row["error_message"],
            summary=row["summary"],
        )

    def mark_job_failed(self, job_id: str, error_code: str, error_message: str) -> None:
        self.update_job_status(
            job_id=job_id,
            status=IngestionStatus.failed,
            current_stage="failed",
            error_code=error_code,
            error_message=error_message,
        )
