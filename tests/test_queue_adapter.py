from __future__ import annotations

import importlib
import json
import sys
from types import ModuleType
from datetime import datetime, timezone

import pytest

from app.models.ingestion import IngestionQueueMessage
from app.services.queue import InMemoryIngestionQueue, QueueMessageReceipt


def test_ingestion_queue_message_includes_schema_version_and_correlation_id() -> None:
    message = IngestionQueueMessage(
        schema_version=1,
        job_id="job-123",
        submitted_url="https://example.com",
        status_url="https://api.example.com/status/job-123",
        correlation_id="job-123",
        created_at=datetime.now(timezone.utc),
    )

    payload = message.model_dump()

    assert payload["schema_version"] == 1
    assert payload["correlation_id"] == "job-123"
    assert payload["job_id"] == "job-123"


def test_in_memory_ingestion_queue_abandon_and_dead_letter_paths() -> None:
    queue = InMemoryIngestionQueue()
    message = IngestionQueueMessage(
        schema_version=1,
        job_id="job-456",
        submitted_url="https://example.com",
        status_url="https://api.example.com/status/job-456",
        correlation_id="job-456",
        created_at=datetime.now(timezone.utc),
    )

    queue.enqueue_message(message)

    receipt = queue.receive_message()
    assert isinstance(receipt, QueueMessageReceipt)
    assert receipt.message.job_id == "job-456"

    queue.abandon_message(receipt)
    assert queue.enqueued_messages and queue.enqueued_messages[0].job_id == "job-456"

    receipt = queue.receive_message()
    queue.dead_letter_message(receipt, reason="processing_failed")
    assert queue.dead_letter_messages[0].job_id == "job-456"
    assert not queue.enqueued_messages


def test_azure_service_bus_ingestion_queue_serializes_and_settles_messages(monkeypatch) -> None:
    fake_azure = ModuleType("azure")
    fake_servicebus = ModuleType("azure.servicebus")

    sent_messages: list[dict[str, object]] = []
    completed_messages: list[object] = []
    abandoned_messages: list[object] = []
    dead_lettered_messages: list[tuple[object, str | None]] = []

    class FakeServiceBusMessage:
        def __init__(self, body: str, correlation_id: str | None = None) -> None:
            self.body = body
            self.correlation_id = correlation_id

    class FakeServiceBusSender:
        def __enter__(self) -> "FakeServiceBusSender":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def send_messages(self, message: FakeServiceBusMessage) -> None:
            sent_messages.append({
                "body": message.body,
                "correlation_id": message.correlation_id,
            })

    class FakeServiceBusReceiver:
        def __init__(self, messages: list[FakeServiceBusMessage]) -> None:
            self._messages = messages
            self.closed = False

        def receive_messages(self, max_message_count: int = 1, max_wait_time: int = 5) -> list[FakeServiceBusMessage]:
            return self._messages

        def complete_message(self, message: FakeServiceBusMessage) -> None:
            completed_messages.append(message)

        def abandon_message(self, message: FakeServiceBusMessage) -> None:
            abandoned_messages.append(message)

        def dead_letter_message(self, message: FakeServiceBusMessage, reason: str | None = None) -> None:
            dead_lettered_messages.append((message, reason))

        def close(self) -> None:
            self.closed = True

    class FakeServiceBusClient:
        def __init__(self, connection_string: str) -> None:
            self.connection_string = connection_string

        @classmethod
        def from_connection_string(cls, connection_string: str) -> "FakeServiceBusClient":
            return cls(connection_string)

        def get_queue_sender(self, queue_name: str) -> FakeServiceBusSender:
            return FakeServiceBusSender()

        def get_queue_receiver(self, queue_name: str, max_wait_time: int = 5) -> FakeServiceBusReceiver:
            body = json.dumps(
                {
                    "schema_version": 1,
                    "job_id": "job-789",
                    "submitted_url": "https://example.com",
                    "status_url": "https://api.example.com/status/job-789",
                    "correlation_id": "job-789",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            return FakeServiceBusReceiver([FakeServiceBusMessage(body, correlation_id="job-789")])

    fake_servicebus.ServiceBusClient = FakeServiceBusClient
    fake_servicebus.ServiceBusMessage = FakeServiceBusMessage
    fake_azure.servicebus = fake_servicebus
    sys.modules["azure"] = fake_azure
    sys.modules["azure.servicebus"] = fake_servicebus

    import app.integrations.service_bus as service_bus_module
    importlib.reload(service_bus_module)

    queue = service_bus_module.AzureServiceBusIngestionQueue(
        connection_string="Endpoint=sb://example.servicebus.windows.net/;SharedAccessKeyName=key;SharedAccessKey=value",
        queue_name="ingestion-queue",
    )

    message = IngestionQueueMessage(
        schema_version=1,
        job_id="job-789",
        submitted_url="https://example.com",
        status_url="https://api.example.com/status/job-789",
        correlation_id="job-789",
        created_at=datetime.now(timezone.utc),
    )

    queue.enqueue_message(message)

    assert len(sent_messages) == 1
    payload = json.loads(sent_messages[0]["body"])
    assert payload["schema_version"] == 1
    assert payload["job_id"] == "job-789"
    assert sent_messages[0]["correlation_id"] == "job-789"

    receipt = queue.receive_message()
    assert receipt is not None
    assert receipt.message.job_id == "job-789"

    queue.complete_message(receipt)
    assert completed_messages
    assert receipt.receiver is not None and receipt.receiver.closed

    receipt = queue.receive_message()
    assert receipt is not None
    queue.abandon_message(receipt, reason="retry")
    assert abandoned_messages

    receipt = queue.receive_message()
    assert receipt is not None
    queue.dead_letter_message(receipt, reason="permanent_failure")
    assert dead_lettered_messages[0][1] == "permanent_failure"
