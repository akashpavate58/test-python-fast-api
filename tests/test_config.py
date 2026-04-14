import os

import pytest
from pydantic import ValidationError

from app.core.config import get_settings


def teardown_function(function):
    for key in [
        "APP_NAME",
        "ENVIRONMENT",
        "API_V1_PREFIX",
        "ALLOWED_CORS_ORIGINS",
        "API_BASE_URL",
        "CRAWL_ALLOWED_SCHEMES",
        "CHUNK_SIZE_CHARS",
        "CHUNK_OVERLAP_CHARS",
        "WORKER_MAX_CONCURRENT_JOBS",
        "WORKER_MAX_CONCURRENT_PAGE_FETCHES_PER_JOB",
        "CRAWL_MAX_DEPTH",
        "CRAWL_MAX_PAGES_PER_JOB",
        "INGESTION_STATUS_POLL_RETRY_AFTER_SECONDS",
    ]:
        os.environ.pop(key, None)
    get_settings.cache_clear()


def test_default_settings_load_when_env_missing():
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.app_name == "FastAPI Service"
    assert settings.environment == "development"
    assert settings.debug is False
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.host == "0.0.0.0"
    assert settings.port == 8000
    assert settings.log_level == "INFO"
    assert settings.allowed_cors_origins == []
    assert settings.api_base_url == ""
    assert settings.ingestion_status_poll_retry_after_seconds == 5
    assert settings.job_status_retention_days == 30
    assert settings.crawl_allowed_schemes == ["https", "http"]
    assert settings.chunk_size_chars == 1000
    assert settings.chunk_overlap_chars == 200
    assert settings.embedding_vector_size == 1536
    assert settings.worker_max_concurrent_jobs == 2
    assert settings.azure_blob_connection_string == ""
    assert settings.azure_service_bus_connection_string == ""
    assert settings.service_bus_queue_ingestion == "ingestion-queue"
    assert settings.qdrant_collection_name == "ingestion-docs"
    assert settings.qdrant_payload_store_mode == "structured"
    assert settings.external_api_timeout_seconds == 10


def test_environment_variable_overrides():
    os.environ["APP_NAME"] = "Test Service"
    os.environ["ENVIRONMENT"] = "production"
    os.environ["API_V1_PREFIX"] = "/api/v1/test"
    os.environ["API_BASE_URL"] = "https://api.test"
    os.environ["INGESTION_STATUS_POLL_RETRY_AFTER_SECONDS"] = "10"
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.app_name == "Test Service"
    assert settings.environment == "production"
    assert settings.api_v1_prefix == "/api/v1/test"
    assert settings.api_base_url == "https://api.test"
    assert settings.ingestion_status_poll_retry_after_seconds == 10


def test_allowed_cors_origins_list_parsing():
    os.environ["ALLOWED_CORS_ORIGINS"] = "http://localhost:3000,http://example.com"
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.allowed_cors_origins == [
        "http://localhost:3000",
        "http://example.com",
    ]


def test_allowed_cors_origins_and_crawl_allowed_schemes_parsing():
    os.environ["ALLOWED_CORS_ORIGINS"] = "http://localhost:3000, http://example.com"
    os.environ["CRAWL_ALLOWED_SCHEMES"] = "https, ftp"
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.allowed_cors_origins == [
        "http://localhost:3000",
        "http://example.com",
    ]
    assert settings.crawl_allowed_schemes == ["https", "ftp"]


def test_invalid_chunk_overlap_raises_validation_error():
    os.environ["CHUNK_SIZE_CHARS"] = "100"
    os.environ["CHUNK_OVERLAP_CHARS"] = "100"
    get_settings.cache_clear()

    with pytest.raises(ValidationError):
        get_settings()


def test_invalid_concurrency_settings_raises_validation_error():
    os.environ["WORKER_MAX_CONCURRENT_JOBS"] = "0"
    os.environ["WORKER_MAX_CONCURRENT_PAGE_FETCHES_PER_JOB"] = "-1"
    get_settings.cache_clear()

    with pytest.raises(ValidationError):
        get_settings()


def test_invalid_crawl_settings_raises_validation_error():
    os.environ["CRAWL_MAX_DEPTH"] = "-1"
    os.environ["CRAWL_MAX_PAGES_PER_JOB"] = "-5"
    get_settings.cache_clear()

    with pytest.raises(ValidationError):
        get_settings()
