from __future__ import annotations

import json
from importlib import import_module
from typing import Any

from app.models.ingestion import IngestionQueueMessage
from app.services.queue import QueueMessageReceipt


class AzureServiceBusIngestionQueue:
    def __init__(self, connection_string: str, queue_name: str) -> None:
        self._connection_string = connection_string
        self._queue_name = queue_name
        self._client = self._create_client(connection_string)

    @staticmethod
    def _create_client(connection_string: str) -> Any:
        servicebus = import_module("azure.servicebus")
        return servicebus.ServiceBusClient.from_connection_string(connection_string)

    @staticmethod
    def _decode_body(raw_body: Any) -> str:
        if isinstance(raw_body, str):
            return raw_body
        if isinstance(raw_body, (bytes, bytearray)):
            return raw_body.decode("utf-8")
        if isinstance(raw_body, list):
            parts: list[str] = []
            for chunk in raw_body:
                if isinstance(chunk, (bytes, bytearray)):
                    parts.append(chunk.decode("utf-8"))
                elif isinstance(chunk, str):
                    parts.append(chunk)
                else:
                    raise TypeError("Unsupported message body chunk type")
            return "".join(parts)
        raise TypeError("Unsupported message body type")

    def enqueue_message(self, message: IngestionQueueMessage) -> None:
        servicebus = import_module("azure.servicebus")
        body = json.dumps(message.model_dump(mode="json"))
        service_message = servicebus.ServiceBusMessage(
            body,
            correlation_id=message.correlation_id,
        )

        with self._client.get_queue_sender(self._queue_name) as sender:
            sender.send_messages(service_message)

    def receive_message(self, timeout_seconds: int = 5) -> QueueMessageReceipt | None:
        receiver = self._client.get_queue_receiver(
            self._queue_name,
            max_wait_time=timeout_seconds,
        )
        messages = receiver.receive_messages(max_message_count=1, max_wait_time=timeout_seconds)
        if not messages:
            receiver.close()
            return None

        raw_message = messages[0]
        payload_text = self._decode_body(raw_message.body)
        payload = json.loads(payload_text)
        ingestion_message = IngestionQueueMessage.model_validate(payload)
        return QueueMessageReceipt(message=ingestion_message, raw_message=raw_message, receiver=receiver)

    def complete_message(self, receipt: QueueMessageReceipt) -> None:
        if receipt.receiver is None or receipt.raw_message is None:
            return
        receipt.receiver.complete_message(receipt.raw_message)
        receipt.receiver.close()

    def abandon_message(self, receipt: QueueMessageReceipt, reason: str | None = None) -> None:
        if receipt.receiver is None or receipt.raw_message is None:
            return
        receipt.receiver.abandon_message(receipt.raw_message)
        receipt.receiver.close()

    def dead_letter_message(self, receipt: QueueMessageReceipt, reason: str | None = None) -> None:
        if receipt.receiver is None or receipt.raw_message is None:
            return
        receipt.receiver.dead_letter_message(receipt.raw_message, reason=reason)
        receipt.receiver.close()
