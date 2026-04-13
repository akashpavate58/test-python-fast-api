from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from app.core.config import AppSettings
from app.models.ingestion import (
    IngestionJobRecord,
    IngestionQueueMessage,
    IngestionStatus,
)
from app.services.ingestion import InMemoryJobRepository
from app.services.queue import InMemoryIngestionQueue
from app.worker import IngestionWorker


def create_job_record(job_id: str) -> IngestionJobRecord:
    now = datetime.now(timezone.utc)
    return IngestionJobRecord(
        job_id=job_id,
        submitted_url="https://example.com",
        status=IngestionStatus.queued,
        current_stage="queued",
        created_at=now,
        updated_at=now,
    )


def create_queue_message(job_id: str) -> IngestionQueueMessage:
    now = datetime.now(timezone.utc)
    return IngestionQueueMessage(
        schema_version=1,
        job_id=job_id,
        submitted_url="https://example.com",
        status_url=f"https://api.example.com/status/{job_id}",
        correlation_id=job_id,
        created_at=now,
        payload={"submitted_url": "https://example.com"},
    )


@pytest.mark.asyncio
async def test_worker_consumes_job_and_completes() -> None:
    settings = AppSettings(
        worker_max_concurrent_jobs=1,
        worker_max_concurrent_page_fetches_per_job=1,
        worker_max_concurrent_embedding_batches=1,
        worker_max_pending_chunk_volume_per_job=1,
    )
    queue = InMemoryIngestionQueue()
    repository = InMemoryJobRepository()
    job_id = "job-consume"
    repository.create_job(create_job_record(job_id))
    queue.enqueue_message(create_queue_message(job_id))

    worker = IngestionWorker(queue=queue, repository=repository, settings=settings)

    async def noop_fetch(_: str, __: str) -> None:
        await asyncio.sleep(0)

    async def noop_embed(_: str, __: str, ___: asyncio.Semaphore) -> None:
        await asyncio.sleep(0)

    worker._fetch_page = noop_fetch
    worker._embed_chunk = noop_embed

    run_task = asyncio.create_task(worker.run())
    await asyncio.sleep(0.1)
    worker.request_shutdown()
    await run_task

    job_record = repository.get_job(job_id)
    assert job_record is not None
    assert job_record.status == IngestionStatus.completed
    assert job_record.current_stage == "completed"
    assert not queue.enqueued_messages


@pytest.mark.asyncio
async def test_worker_enforces_concurrency_limits() -> None:
    settings = AppSettings(
        worker_max_concurrent_jobs=1,
        worker_max_concurrent_page_fetches_per_job=2,
        worker_max_concurrent_embedding_batches=1,
        worker_max_pending_chunk_volume_per_job=2,
        crawl_max_pages_per_job=4,
    )
    queue = InMemoryIngestionQueue()
    repository = InMemoryJobRepository()
    job_id = "job-concurrency"
    repository.create_job(create_job_record(job_id))
    queue.enqueue_message(create_queue_message(job_id))

    worker = IngestionWorker(queue=queue, repository=repository, settings=settings)

    active_fetches = 0
    max_fetches = 0
    active_pending_chunks = 0
    max_pending_chunks = 0
    active_embeddings = 0
    max_embeddings = 0

    async def tracked_fetch(_: str, __: str) -> None:
        nonlocal active_fetches, max_fetches
        active_fetches += 1
        max_fetches = max(max_fetches, active_fetches)
        await asyncio.sleep(0.05)
        active_fetches -= 1

    async def tracked_embed(job_id_arg: str, source: str, semaphore: asyncio.Semaphore) -> None:
        nonlocal active_embeddings, max_embeddings
        async with semaphore:
            active_embeddings += 1
            max_embeddings = max(max_embeddings, active_embeddings)
            await asyncio.sleep(0.05)
            active_embeddings -= 1

    class CountingWorker(IngestionWorker):
        async def _fetch_process_page(
            self,
            job_id_arg: str,
            page_url: str,
            page_fetch_semaphore: asyncio.Semaphore,
            pending_chunk_semaphore: asyncio.Semaphore,
            embedding_semaphore: asyncio.Semaphore,
        ) -> None:
            nonlocal active_pending_chunks, max_pending_chunks

            async with page_fetch_semaphore:
                await self._fetch_page(job_id_arg, page_url)
                self.repository.increment_job_progress(job_id_arg, pages_discovered=1, pages_fetched=1)

            async with pending_chunk_semaphore:
                active_pending_chunks += 1
                max_pending_chunks = max(max_pending_chunks, active_pending_chunks)
                self.repository.increment_job_progress(job_id_arg, pages_extracted=1, chunks_created=1)
                await self._embed_chunk(job_id_arg, page_url, embedding_semaphore)
                active_pending_chunks -= 1

    counting_worker = CountingWorker(
        queue=queue,
        repository=repository,
        settings=settings,
    )
    counting_worker._fetch_page = tracked_fetch
    counting_worker._embed_chunk = tracked_embed

    run_task = asyncio.create_task(counting_worker.run())
    await asyncio.sleep(0.3)
    counting_worker.request_shutdown()
    await run_task

    assert max_fetches <= settings.worker_max_concurrent_page_fetches_per_job
    assert max_embeddings <= settings.worker_max_concurrent_embedding_batches
    assert max_pending_chunks <= settings.worker_max_pending_chunk_volume_per_job


@pytest.mark.asyncio
async def test_worker_graceful_shutdown_stops_receiving_new_jobs() -> None:
    settings = AppSettings(
        worker_max_concurrent_jobs=1,
        worker_max_concurrent_page_fetches_per_job=1,
        worker_max_concurrent_embedding_batches=1,
        worker_max_pending_chunk_volume_per_job=1,
    )
    queue = InMemoryIngestionQueue()
    repository = InMemoryJobRepository()
    first_job_id = "job-first"
    second_job_id = "job-second"
    repository.create_job(create_job_record(first_job_id))
    repository.create_job(create_job_record(second_job_id))
    queue.enqueue_message(create_queue_message(first_job_id))
    queue.enqueue_message(create_queue_message(second_job_id))

    worker = IngestionWorker(queue=queue, repository=repository, settings=settings)
    first_started = asyncio.Event()

    async def slow_fetch(_: str, __: str) -> None:
        first_started.set()
        await asyncio.sleep(0.2)

    async def noop_embed(_: str, __: str, ___: asyncio.Semaphore) -> None:
        await asyncio.sleep(0.01)

    worker._fetch_page = slow_fetch
    worker._embed_chunk = noop_embed

    run_task = asyncio.create_task(worker.run())
    await first_started.wait()
    await asyncio.sleep(0.05)
    worker.request_shutdown()
    await run_task

    assert repository.get_job(first_job_id) is not None
    assert repository.get_job(first_job_id).status == IngestionStatus.completed
    assert queue.enqueued_messages and queue.enqueued_messages[0].job_id == second_job_id


@pytest.mark.asyncio
async def test_worker_retries_failed_job_before_completion() -> None:
    settings = AppSettings(
        worker_max_concurrent_jobs=1,
        worker_max_concurrent_page_fetches_per_job=1,
        worker_max_concurrent_embedding_batches=1,
        worker_max_pending_chunk_volume_per_job=1,
        worker_message_retry_limit=2,
    )
    queue = InMemoryIngestionQueue()
    repository = InMemoryJobRepository()
    job_id = "job-retry"
    repository.create_job(create_job_record(job_id))
    queue.enqueue_message(create_queue_message(job_id))

    worker = IngestionWorker(queue=queue, repository=repository, settings=settings)
    attempts = 0

    async def retry_pipeline(job_id_arg: str, message: IngestionQueueMessage) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("simulated transient failure")

    worker._run_job_pipeline = retry_pipeline

    run_task = asyncio.create_task(worker.run())
    await asyncio.sleep(0.2)
    worker.request_shutdown()
    await run_task

    assert attempts == 2
    job_record = repository.get_job(job_id)
    assert job_record is not None
    assert job_record.status == IngestionStatus.completed
    assert not queue.enqueued_messages


@pytest.mark.asyncio
async def test_worker_dead_letters_job_after_retry_limit_exceeded() -> None:
    settings = AppSettings(
        worker_max_concurrent_jobs=1,
        worker_max_concurrent_page_fetches_per_job=1,
        worker_max_concurrent_embedding_batches=1,
        worker_max_pending_chunk_volume_per_job=1,
        worker_message_retry_limit=1,
    )
    queue = InMemoryIngestionQueue()
    repository = InMemoryJobRepository()
    job_id = "job-deadletter"
    repository.create_job(create_job_record(job_id))
    queue.enqueue_message(create_queue_message(job_id))

    worker = IngestionWorker(queue=queue, repository=repository, settings=settings)

    async def always_fail(_: str, __: IngestionQueueMessage) -> None:
        raise RuntimeError("permanent failure")

    worker._run_job_pipeline = always_fail

    run_task = asyncio.create_task(worker.run())
    await asyncio.sleep(0.2)
    worker.request_shutdown()
    await run_task

    assert len(queue.dead_letter_messages) == 1
    assert queue.dead_letter_messages[0].job_id == job_id
    job_record = repository.get_job(job_id)
    assert job_record is not None
    assert job_record.status == IngestionStatus.failed
