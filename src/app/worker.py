from __future__ import annotations

import asyncio
import logging
import signal

from app.core.config import AppSettings, get_settings
from app.core.logging import init_logging
from app.integrations.blob_storage import BlobStorageAdapter, get_blob_storage_adapter
from app.models.ingestion import ExtractedPageContent, IngestionQueueMessage, IngestionStatus
from app.services.blob_storage import upload_page_text_blob
from app.services.ingestion import (
    JobRepository,
    get_ingestion_queue,
    get_job_repository,
    transition_job_status,
)
from app.services.queue import IngestionQueue, QueueMessageReceipt


logger = logging.getLogger("app.worker")


class IngestionWorker:
    def __init__(
        self,
        queue: IngestionQueue | None = None,
        repository: JobRepository | None = None,
        settings: AppSettings | None = None,
        blob_storage: BlobStorageAdapter | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.queue = queue or get_ingestion_queue()
        self.repository = repository or get_job_repository()
        self.blob_storage = blob_storage or get_blob_storage_adapter(
            self.settings.azure_blob_connection_string
        )
        self._shutdown_event = asyncio.Event()
        self._job_semaphore = asyncio.Semaphore(self.settings.worker_max_concurrent_jobs)
        self._active_tasks: set[asyncio.Task[None]] = set()
        self._logger = logging.getLogger("app.worker")

    def request_shutdown(self) -> None:
        self._logger.info("Ingestion worker shutdown requested")
        self._shutdown_event.set()

    async def run(self) -> None:
        self._logger.info(
            "Starting ingestion worker",
            extra={
                "max_concurrent_jobs": self.settings.worker_max_concurrent_jobs,
                "max_page_fetches_per_job": self.settings.worker_max_concurrent_page_fetches_per_job,
                "max_embedding_batches": self.settings.worker_max_concurrent_embedding_batches,
                "max_pending_chunk_volume": self.settings.worker_max_pending_chunk_volume_per_job,
            },
        )

        loop = asyncio.get_running_loop()
        self._install_signal_handlers(loop)

        try:
            while not self._shutdown_event.is_set():
                await self._job_semaphore.acquire()
                if self._shutdown_event.is_set():
                    self._job_semaphore.release()
                    break

                receipt = await self._receive_message(timeout_seconds=1)
                if receipt is None:
                    self._job_semaphore.release()
                    continue

                if self._shutdown_event.is_set():
                    await self._abandon_message(receipt, reason="shutdown")
                    self._job_semaphore.release()
                    break

                task = asyncio.create_task(self._process_receipt(receipt))
                self._active_tasks.add(task)
                task.add_done_callback(self._on_job_done)
        finally:
            await self._shutdown_inflight()
            self._logger.info("Ingestion worker stopped")

    def _install_signal_handlers(self, loop: asyncio.AbstractEventLoop) -> None:
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self.request_shutdown)
            except NotImplementedError:
                pass

    async def _receive_message(self, timeout_seconds: int) -> QueueMessageReceipt | None:
        return await asyncio.to_thread(self.queue.receive_message, timeout_seconds)

    async def _complete_message(self, receipt: QueueMessageReceipt) -> None:
        await asyncio.to_thread(self.queue.complete_message, receipt)

    async def _abandon_message(self, receipt: QueueMessageReceipt, reason: str | None = None) -> None:
        await asyncio.to_thread(self.queue.abandon_message, receipt, reason)

    async def _dead_letter_message(self, receipt: QueueMessageReceipt, reason: str | None = None) -> None:
        await asyncio.to_thread(self.queue.dead_letter_message, receipt, reason)

    def _on_job_done(self, task: asyncio.Task[None]) -> None:
        self._active_tasks.discard(task)
        self._job_semaphore.release()
        if task.cancelled():
            self._logger.warning("A job task was cancelled before completion")
            return
        exception = task.exception()
        if exception is not None:
            self._logger.exception("A job task failed unexpectedly", exc_info=exception)

    async def _process_receipt(self, receipt: QueueMessageReceipt) -> None:
        job_id = receipt.message.job_id
        self._logger.info("Processing ingestion job %s", job_id)

        try:
            transition_job_status(self.repository, job_id, IngestionStatus.running, "running")
            await self._run_job_pipeline(job_id, receipt.message)
            transition_job_status(self.repository, job_id, IngestionStatus.completed, "completed")
            await self._complete_message(receipt)
            self._logger.info("Job %s completed successfully", job_id)
        except Exception as exc:
            await self._handle_processing_error(receipt, exc)

    async def _run_job_pipeline(self, job_id: str, message: IngestionQueueMessage) -> None:
        page_count = max(1, min(self.settings.crawl_max_pages_per_job, 10))
        page_urls = [f"{message.submitted_url}?page={index}" for index in range(1, page_count + 1)]

        page_fetch_semaphore = asyncio.Semaphore(self.settings.worker_max_concurrent_page_fetches_per_job)
        embedding_semaphore = asyncio.Semaphore(self.settings.worker_max_concurrent_embedding_batches)
        pending_chunk_semaphore = asyncio.Semaphore(self.settings.worker_max_pending_chunk_volume_per_job)

        async with asyncio.TaskGroup() as task_group:
            for page_url in page_urls:
                task_group.create_task(
                    self._fetch_process_page(
                        job_id,
                        page_url,
                        page_fetch_semaphore,
                        pending_chunk_semaphore,
                        embedding_semaphore,
                    )
                )

    async def _fetch_process_page(
        self,
        job_id: str,
        page_url: str,
        page_fetch_semaphore: asyncio.Semaphore,
        pending_chunk_semaphore: asyncio.Semaphore,
        embedding_semaphore: asyncio.Semaphore,
    ) -> None:
        extracted_page: ExtractedPageContent | None = None
        async with page_fetch_semaphore:
            extracted_page = await self._fetch_page(job_id, page_url)
            self.repository.increment_job_progress(job_id, pages_discovered=1, pages_fetched=1)

        async with pending_chunk_semaphore:
            self.repository.increment_job_progress(job_id, pages_extracted=1, chunks_created=1)
            if extracted_page is not None:
                await self._store_page_text(job_id, extracted_page)
            await self._embed_chunk(job_id, page_url, embedding_semaphore)

    async def _fetch_page(self, job_id: str, page_url: str) -> ExtractedPageContent | None:
        await asyncio.sleep(0)
        return None

    async def _store_page_text(
        self,
        job_id: str,
        extracted_page: ExtractedPageContent,
    ) -> None:
        await asyncio.to_thread(
            upload_page_text_blob,
            self.blob_storage,
            self.settings,
            job_id,
            extracted_page,
        )

    async def _embed_chunk(
        self,
        job_id: str,
        chunk_source: str,
        embedding_semaphore: asyncio.Semaphore,
    ) -> None:
        async with embedding_semaphore:
            await asyncio.sleep(0)
            self.repository.increment_job_progress(job_id, chunks_embedded=1, vectors_stored=1)

    async def _handle_processing_error(
        self,
        receipt: QueueMessageReceipt,
        exc: BaseException,
    ) -> None:
        job_id = receipt.message.job_id
        retry_allowed = self._should_retry(receipt)

        if retry_allowed:
            self._logger.warning(
                "Retrying ingestion job %s due to transient failure: %s",
                job_id,
                exc,
            )
            try:
                transition_job_status(
                    self.repository,
                    job_id,
                    IngestionStatus.queued,
                    "retrying",
                    error_code="processing_retry",
                    error_message=str(exc),
                )
            except Exception:
                pass
            await self._abandon_message(receipt, reason="processing_retry")
            return

        self._logger.error(
            "Dead-lettering ingestion job %s after retry limit: %s",
            job_id,
            exc,
        )
        self.repository.mark_job_failed(job_id, error_code="processing_failed", error_message=str(exc))
        await self._dead_letter_message(receipt, reason="retry_limit_exceeded")

    def _should_retry(self, receipt: QueueMessageReceipt) -> bool:
        return receipt.delivery_count < self.settings.worker_message_retry_limit

    async def _shutdown_inflight(self) -> None:
        if not self._active_tasks:
            return

        self._logger.info(
            "Waiting for %d in-flight job(s) to finish",
            len(self._active_tasks),
        )
        done, pending = await asyncio.wait(
            self._active_tasks,
            timeout=self.settings.worker_shutdown_grace_seconds,
        )

        if pending:
            self._logger.warning(
                "Cancelling %d job(s) still running after shutdown grace period",
                len(pending),
            )
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)


async def main() -> None:
    settings = get_settings()
    init_logging(settings.log_level)

    worker = IngestionWorker()
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
