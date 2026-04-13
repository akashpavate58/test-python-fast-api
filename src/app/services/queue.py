from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Optional, Protocol

from app.models.ingestion import IngestionQueueMessage


@dataclass
class QueueMessageReceipt:
    message: IngestionQueueMessage
    raw_message: Any | None = None
    receiver: Any | None = None
    delivery_count: int = 1


class IngestionQueue(Protocol):
    def enqueue_message(self, message: IngestionQueueMessage) -> None:
        ...

    def receive_message(self, timeout_seconds: int = 5) -> QueueMessageReceipt | None:
        ...

    def complete_message(self, receipt: QueueMessageReceipt) -> None:
        ...

    def abandon_message(self, receipt: QueueMessageReceipt, reason: str | None = None) -> None:
        ...

    def dead_letter_message(
        self, receipt: QueueMessageReceipt, reason: str | None = None
    ) -> None:
        ...


class InMemoryIngestionQueue:
    def __init__(self) -> None:
        self.enqueued_messages: Deque[IngestionQueueMessage] = deque()
        self.dead_letter_messages: list[IngestionQueueMessage] = []
        self._pending_receipts: list[QueueMessageReceipt] = []

    def enqueue_message(self, message: IngestionQueueMessage) -> None:
        self.enqueued_messages.append(message)

    def receive_message(self, timeout_seconds: int = 5) -> QueueMessageReceipt | None:
        if not self.enqueued_messages:
            return None

        message = self.enqueued_messages.popleft()
        delivery_count = 1
        if isinstance(message.payload, dict):
            delivery_count = int(message.payload.get("delivery_count", 1))

        receipt = QueueMessageReceipt(message=message, delivery_count=delivery_count)
        self._pending_receipts.append(receipt)
        return receipt

    def complete_message(self, receipt: QueueMessageReceipt) -> None:
        if receipt in self._pending_receipts:
            self._pending_receipts.remove(receipt)

    def abandon_message(self, receipt: QueueMessageReceipt, reason: str | None = None) -> None:
        if receipt in self._pending_receipts:
            self._pending_receipts.remove(receipt)
            receipt.delivery_count += 1
            if isinstance(receipt.message.payload, dict):
                receipt.message.payload["delivery_count"] = receipt.delivery_count
            self.enqueued_messages.append(receipt.message)

    def dead_letter_message(self, receipt: QueueMessageReceipt, reason: str | None = None) -> None:
        if receipt in self._pending_receipts:
            self._pending_receipts.remove(receipt)
            self.dead_letter_messages.append(receipt.message)
