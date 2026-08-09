from typing import Protocol, Any

class RecoveryNotificationGateway(Protocol):
    def send(self, *args, **kwargs) -> Any: ...
