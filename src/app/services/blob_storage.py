from __future__ import annotations

import hashlib

from app.core.config import AppSettings
from app.integrations.blob_storage import BlobStorageAdapter, BlobStorageUploadError
from app.models.ingestion import BlobReference, ExtractedPageContent


def build_page_blob_name(job_id: str, page_url: str) -> str:
    blob_hash = hashlib.sha256(f"{job_id}|{page_url}".encode("utf-8")).hexdigest()
    return f"{job_id}/pages/{blob_hash}.txt"


def upload_page_text_blob(
    blob_storage: BlobStorageAdapter,
    settings: AppSettings,
    job_id: str,
    extracted_page: ExtractedPageContent,
) -> BlobReference:
    blob_name = build_page_blob_name(job_id, str(extracted_page.page_url))
    try:
        uri = blob_storage.upload_blob(
            settings.blob_container_raw_pages,
            blob_name,
            extracted_page.text.encode("utf-8"),
        )
    except Exception as exc:
        raise BlobStorageUploadError(
            "Failed to upload extracted page text to blob storage."
        ) from exc

    blob_reference = BlobReference(
        submitted_url=extracted_page.submitted_url,
        page_url=extracted_page.page_url,
        container_name=settings.blob_container_raw_pages,
        blob_name=blob_name,
        uri=uri,
    )
    extracted_page.metadata["blob_reference"] = blob_reference.model_dump()
    return blob_reference
