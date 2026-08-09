from typing import Protocol, Any

class ImmutableAuditStore(Protocol):
    def append(self, event: dict[str, Any]) -> Any: ...
