from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    app_name: str = "FastAPI Service"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    allowed_cors_origins: str | list[str] = []

    api_base_url: str = ""
    job_status_database_url: str = "sqlite:///./job_status.db"
    ingestion_status_poll_retry_after_seconds: int = 5
    job_status_retention_days: int = 30

    crawl_max_depth: int = 3
    crawl_max_pages_per_job: int = 100
    crawl_request_timeout_seconds: int = 10
    crawl_max_redirects: int = 5
    crawl_same_host_only: bool = True
    crawl_allowed_schemes: str | list[str] = ["https", "http"]
    crawl_user_agent: str = "FastAPICrawler/1.0"

    chunk_size_chars: int = 1000
    chunk_overlap_chars: int = 200
    chunk_min_non_whitespace_chars: int = 50

    embedding_provider: str = "openai"
    embedding_model_name: str = "text-embedding-3-large"
    embedding_vector_size: int = 1536
    embedding_max_batch_size: int = 16
    embedding_max_concurrency: int = 4
    embedding_request_timeout_seconds: int = 30
    embedding_max_retries: int = 3

    service_bus_queue_ingestion: str = "ingestion-queue"
    worker_max_concurrent_jobs: int = 2
    worker_max_concurrent_page_fetches_per_job: int = 5
    worker_max_concurrent_embedding_batches: int = 2
    worker_max_pending_chunk_volume_per_job: int = 20
    worker_shutdown_grace_seconds: int = 30
    worker_message_retry_limit: int = 5

    azure_blob_connection_string: str = ""
    azure_service_bus_connection_string: str = ""
    blob_container_raw_pages: str = "raw-pages"
    blob_container_chunks: str = "chunks"

    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_collection_name: str = "ingestion-docs"
    qdrant_payload_store_mode: Literal["structured", "binary"] = "structured"

    external_api_base_url: str = ""
    external_api_timeout_seconds: int = 10

    @field_validator("allowed_cors_origins", "crawl_allowed_schemes", mode="before")
    @classmethod
    def _normalize_string_list(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator(
        "crawl_max_depth",
        "crawl_max_pages_per_job",
        "crawl_request_timeout_seconds",
        "crawl_max_redirects",
        "job_status_retention_days",
        "worker_shutdown_grace_seconds",
        "embedding_max_retries",
        mode="before",
    )
    @classmethod
    def _validate_non_negative(cls, value):
        if isinstance(value, str):
            try:
                value = int(value)
            except ValueError:
                return value
        if isinstance(value, int) and value < 0:
            raise ValueError("value must be zero or positive")
        return value

    @field_validator(
        "chunk_size_chars",
        "chunk_min_non_whitespace_chars",
        "embedding_vector_size",
        "embedding_max_batch_size",
        "embedding_max_concurrency",
        "worker_max_concurrent_jobs",
        "worker_max_concurrent_page_fetches_per_job",
        "worker_max_concurrent_embedding_batches",
        "worker_max_pending_chunk_volume_per_job",
        "worker_message_retry_limit",
        "ingestion_status_poll_retry_after_seconds",
        "embedding_request_timeout_seconds",
        mode="before",
    )
    @classmethod
    def _validate_positive(cls, value):
        if isinstance(value, str):
            try:
                value = int(value)
            except ValueError:
                return value
        if isinstance(value, int) and value <= 0:
            raise ValueError("value must be positive")
        return value

    @model_validator(mode="after")
    def _validate_chunk_defaults(self):
        if self.chunk_overlap_chars >= self.chunk_size_chars:
            raise ValueError(
                "chunk_overlap_chars must be less than chunk_size_chars"
            )
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
