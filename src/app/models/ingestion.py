from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import AnyUrl, BaseModel, Field, HttpUrl, NonNegativeInt


class IngestionStatus(str, Enum):
    accepted = "accepted"
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    partially_completed = "partially_completed"


class IngestionRequest(BaseModel):
    url: AnyUrl


class IngestionAcceptedResponse(BaseModel):
    job_id: str
    status: Literal["accepted", "queued"]
    submitted_url: HttpUrl
    status_url: HttpUrl
    created_at: datetime


class IngestionJobStatusResponse(BaseModel):
    job_id: str
    submitted_url: HttpUrl
    status: IngestionStatus
    current_stage: str
    created_at: datetime
    updated_at: datetime
    status_url: HttpUrl
    pages_discovered: NonNegativeInt
    pages_fetched: NonNegativeInt
    pages_extracted: NonNegativeInt
    pages_failed: NonNegativeInt
    chunks_created: NonNegativeInt
    chunks_embedded: NonNegativeInt
    vectors_stored: NonNegativeInt
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    summary: Optional[str] = None


class IngestionQueueMessage(BaseModel):
    schema_version: int = Field(default=1, ge=1)
    job_id: str
    submitted_url: HttpUrl
    status_url: HttpUrl
    correlation_id: str
    created_at: datetime
    payload: Optional[Dict[str, Any]] = None


class IngestionJobRecord(BaseModel):
    version: int = Field(default=1, ge=1)
    job_id: str
    submitted_url: HttpUrl
    status: IngestionStatus
    current_stage: str
    created_at: datetime
    updated_at: datetime
    pages_discovered: NonNegativeInt = 0
    pages_fetched: NonNegativeInt = 0
    pages_extracted: NonNegativeInt = 0
    pages_failed: NonNegativeInt = 0
    chunks_created: NonNegativeInt = 0
    chunks_embedded: NonNegativeInt = 0
    vectors_stored: NonNegativeInt = 0
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    summary: Optional[str] = None


class CrawledPage(BaseModel):
    version: int = Field(default=1, ge=1)
    submitted_url: HttpUrl
    page_url: HttpUrl
    final_url: HttpUrl
    fetched_at: datetime
    http_status: int
    content_type: Optional[str] = None
    content_length: Optional[int] = None
    fetch_error: Optional[str] = None


class DiscoveredLink(BaseModel):
    version: int = Field(default=1, ge=1)
    submitted_url: HttpUrl
    page_url: HttpUrl
    link_url: HttpUrl


class ExtractedPageContent(BaseModel):
    version: int = Field(default=1, ge=1)
    submitted_url: HttpUrl
    page_url: HttpUrl
    final_url: HttpUrl
    fetched_at: datetime
    http_status: int
    content_type: Optional[str] = None
    content_length: Optional[int] = None
    fetch_error: Optional[str] = None
    html: str
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TextChunk(BaseModel):
    version: int = Field(default=1, ge=1)
    job_id: str
    submitted_url: HttpUrl
    page_url: HttpUrl
    page_blob_reference: BlobReference
    chunk_id: str
    chunk_index: NonNegativeInt
    total_chunks: NonNegativeInt
    text: str
    start_index: int
    end_index: int


class BlobReference(BaseModel):
    version: int = Field(default=1, ge=1)
    submitted_url: HttpUrl
    page_url: HttpUrl
    container_name: str
    blob_name: str
    uri: str


class VectorPointPayload(BaseModel):
    version: int = Field(default=1, ge=1)
    submitted_url: HttpUrl
    page_url: HttpUrl
    chunk_id: str
    vector: List[float]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IngestionJobSummary(BaseModel):
    version: int = Field(default=1, ge=1)
    job_id: str
    submitted_url: HttpUrl
    status: IngestionStatus
    current_stage: str
    created_at: datetime
    updated_at: datetime
    pages_discovered: NonNegativeInt = 0
    pages_fetched: NonNegativeInt = 0
    pages_extracted: NonNegativeInt = 0
    pages_failed: NonNegativeInt = 0
    chunks_created: NonNegativeInt = 0
    chunks_embedded: NonNegativeInt = 0
    vectors_stored: NonNegativeInt = 0
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    summary: Optional[str] = None
