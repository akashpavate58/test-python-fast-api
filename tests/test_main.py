import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import app, create_app


@pytest.mark.asyncio
async def test_app_lifespan_starts_and_stops_without_error():
    async with LifespanManager(app):
        assert app.state.azuresql_client is None
        assert app.state.qdrant_client is None
        assert app.state.external_api_client is None


@pytest.mark.asyncio
async def test_openapi_document_is_available():
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json().get("openapi", "").startswith("3.")


@pytest.mark.asyncio
async def test_api_v1_router_prefix_exists():
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/api/v1/hello")

    assert response.status_code == 200
    assert response.json() == {
        "message": "Hello, world!",
        "service_name": get_settings().app_name,
        "environment": get_settings().environment,
        "request_id": response.headers["x-request-id"],
    }


@pytest.mark.asyncio
async def test_hello_response_includes_request_id_header():
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/api/v1/hello")

    assert response.status_code == 200
    assert response.headers.get("x-request-id")
    assert response.headers["x-request-id"].strip() != ""


@pytest.mark.asyncio
async def test_unsupported_route_returns_standard_error_shape():
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/api/v1/not-found")

    assert response.status_code == 404
    assert response.headers.get("x-request-id")
    assert response.headers["x-request-id"].strip() != ""

    assert response.json() == {
        "error_code": "not_found",
        "message": "Resource not found.",
        "request_id": response.headers["x-request-id"],
    }


@pytest.mark.asyncio
async def test_validation_error_returns_standard_error_shape():
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/api/v1/test-validation", params={"count": "invalid"})

    assert response.status_code == 422
    assert response.headers.get("x-request-id")
    assert response.json() == {
        "error_code": "validation_error",
        "message": "Invalid request.",
        "request_id": response.headers["x-request-id"],
    }


@pytest.mark.asyncio
async def test_internal_exception_returns_safe_error_shape():
    async with LifespanManager(app):
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/api/v1/test-error")

    assert response.status_code == 500
    assert response.headers.get("x-request-id")
    assert response.json() == {
        "error_code": "internal_error",
        "message": "Internal server error.",
        "request_id": response.headers["x-request-id"],
    }
    assert "traceback" not in response.text.lower()
    assert "simulated internal failure" not in response.text.lower()


@pytest.mark.asyncio
async def test_cors_middleware_allows_configured_origin(monkeypatch):
    monkeypatch.setenv("ALLOWED_CORS_ORIGINS", "http://allowed.example")
    get_settings.cache_clear()
    test_app = create_app()

    async with LifespanManager(test_app):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
            headers={"Origin": "http://allowed.example"},
        ) as client:
            response = await client.get("/api/v1/hello")

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://allowed.example"

    get_settings.cache_clear()
