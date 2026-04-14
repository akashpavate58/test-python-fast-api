from __future__ import annotations

from typing import Protocol

from azure.core.exceptions import AzureError, ResourceExistsError
from azure.storage.blob import BlobServiceClient, ContentSettings


class BlobStorageUploadError(Exception):
    """Raised when a blob upload fails."""


class BlobStorageAdapter(Protocol):
    def upload_blob(
        self,
        container_name: str,
        blob_name: str,
        data: bytes,
        content_type: str = "text/plain; charset=utf-8",
    ) -> str:
        ...


class AzureBlobStorageAdapter:
    def __init__(self, connection_string: str) -> None:
        self._client = BlobServiceClient.from_connection_string(connection_string)

    def upload_blob(
        self,
        container_name: str,
        blob_name: str,
        data: bytes,
        content_type: str = "text/plain; charset=utf-8",
    ) -> str:
        try:
            container_client = self._client.get_container_client(container_name)
            try:
                container_client.create_container()
            except ResourceExistsError:
                pass

            blob_client = container_client.get_blob_client(blob_name)
            blob_client.upload_blob(
                data,
                overwrite=True,
                content_settings=ContentSettings(content_type=content_type),
            )
            return blob_client.url
        except AzureError as exc:
            raise BlobStorageUploadError(
                "Failed to upload blob to Azure Blob Storage."
            ) from exc


class InMemoryBlobStorageAdapter:
    def __init__(self) -> None:
        self.blobs: dict[tuple[str, str], bytes] = {}

    def upload_blob(
        self,
        container_name: str,
        blob_name: str,
        data: bytes,
        content_type: str = "text/plain; charset=utf-8",
    ) -> str:
        self.blobs[(container_name, blob_name)] = data
        return f"https://{container_name}.blob.local/{blob_name}"


def get_blob_storage_adapter(connection_string: str | None = None) -> BlobStorageAdapter:
    if connection_string:
        return AzureBlobStorageAdapter(connection_string)
    return InMemoryBlobStorageAdapter()
