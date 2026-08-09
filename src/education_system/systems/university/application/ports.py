"""University-owned aliases for shared platform extension interfaces."""

from education_system.platform.kernel.ports import (
    AuditPort,
    ClockPort,
    ConfigurationPort,
    DatabasePort,
    EmailPort,
    EventPublisherPort,
    FileStorePort,
    NotificationPort,
    RealtimePort,
    SecretProviderPort,
    StorageLocationPort,
)

__all__ = [
    "AuditPort", "ClockPort", "ConfigurationPort", "DatabasePort", "EmailPort",
    "EventPublisherPort", "FileStorePort", "NotificationPort", "RealtimePort",
    "SecretProviderPort", "StorageLocationPort",
]
