import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import app
from app.api.v1.endpoints.ingestions import get_ingestion_queue, get_job_repository
from app.models.ingestion import IngestionJobRecord, IngestionStatus
from app.services.ingestion import IngestionQueue, JobRepository


class StubJobRepository(JobRepository):
    def __init__(self) -> None:
        self.created_jobs: list[IngestionJobRecord] = []
        self.failed_jobs: list[str] = []

    def create_job(self, job_record: IngestionJobRecord) -> None:
        self.created_jobs.append(job_record)

    def mark_job_failed(self, job_id: str, error_code: str, error_message: str) -> None:
        self.failed_jobs.append(job_id)

    def get_job(self, job_id: str) -> IngestionJobRecord | None:
        return next((job for job in self.created_jobs if job.job_id == job_id), None)


class StubIngestionQueue(IngestionQueue):
    def __init__(self) -> None:
        self.enqueued_messages: list[object] = []

    def enqueue_message(self, message: object) -> None:
        self.enqueued_messages.append(message)


@pytest.mark.asyncio
async def test_post_ingestion_returns_202_with_location_and_retry_after():
    stub_repo = StubJobRepository()
    stub_queue = StubIngestionQueue()
    app.dependency_overrides[get_job_repository] = lambda: stub_repo
    app.dependency_overrides[get_ingestion_queue] = lambda: stub_queue

    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/v1/ingestions",
                json={"url": "https://example.com"},
            )

    try:
        assert response.status_code == 202
        assert response.headers["Location"] == response.json()["status_url"]
        assert response.headers["Retry-After"] == str(
            get_settings().ingestion_status_poll_retry_after_seconds
        )
        assert response.json()["status"] == "accepted"
        assert response.json()["job_id"]
        assert len(stub_queue.enqueued_messages) == 1
        assert len(stub_repo.created_jobs) == 1
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_post_ingestion_rejects_invalid_url():
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post("/api/v1/ingestions", json={"url": "not-a-valid-url"})

    assert response.status_code == 422
    assert response.json()["error_code"] == "validation_error"
    assert response.json()["message"] == "Invalid request."
    assert response.headers.get("x-request-id")


@pytest.mark.asyncio
async def test_post_ingestion_rejects_unsupported_scheme():
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post("/api/v1/ingestions", json={"url": "ftp://example.com"})

    assert response.status_code == 422
    assert response.json()["error_code"] == "validation_error"
    assert response.json()["message"] == "URL scheme is not supported."


@pytest.mark.asyncio
async def test_post_ingestion_rejects_malformed_json():
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/v1/ingestions",
                content='{"url": "https://example.com",}',
                headers={"Content-Type": "application/json"},
            )

    assert response.status_code == 422
    assert response.json()["error_code"] == "validation_error"
    assert response.json()["message"] == "Invalid request."


@pytest.mark.asyncio
async def test_ingestion_status_endpoint_is_available_after_submission():
    app.dependency_overrides.clear()

    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            post_response = await client.post(
                "/api/v1/ingestions",
                json={"url": "https://example.com"},
            )
            assert post_response.status_code == 202
            status_url = post_response.headers["Location"]
            status_response = await client.get(status_url)

    assert status_response.status_code == 200
    assert status_response.json()["status"] == "accepted"
    assert status_response.json()["job_id"] == post_response.json()["job_id"]
