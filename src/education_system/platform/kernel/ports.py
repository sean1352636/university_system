"""Stable extension interfaces for shared platform capabilities."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, Protocol


class DatabasePort(Protocol):
    def transaction(self) -> AbstractContextManager[Any]: ...


class EventPublisherPort(Protocol):
    def publish(
        self,
        connection: Any,
        event_name: str,
        payload: Mapping[str, Any],
        *,
        aggregate_id: str,
        idempotency_key: str,
        correlation_id: str | None = None,
        causation_id: str | None = None,
    ) -> str: ...


class AuditPort(Protocol):
    def record(self, action: str, *, actor_id: str, details: Mapping[str, Any]) -> None: ...


class EmailPort(Protocol):
    def send(self, template: str, recipient: str, context: Mapping[str, Any]) -> str: ...


class NotificationPort(Protocol):
    def notify(self, recipient_id: str, message: str, *, channel: str = "in_app") -> str: ...


class FileStorePort(Protocol):
    def put(self, name: str, content: bytes, *, classification: str) -> str: ...

    def get(self, reference: str) -> bytes: ...


class SecretProviderPort(Protocol):
    def get_secret(self, name: str) -> str: ...


class ConfigurationPort(Protocol):
    def get(self, name: str, default: str | None = None) -> str | None: ...


class RealtimePort(Protocol):
    def emit(self, topic: str, payload: Mapping[str, Any]) -> None: ...


class ClockPort(Protocol):
    def now(self) -> Any: ...


class StorageLocationPort(Protocol):
    def database_path(self, classification: str) -> Path: ...


__all__ = [
    "AuditPort",
    "ClockPort",
    "ConfigurationPort",
    "DatabasePort",
    "EmailPort",
    "EventPublisherPort",
    "FileStorePort",
    "NotificationPort",
    "RealtimePort",
    "SecretProviderPort",
    "StorageLocationPort",
]
