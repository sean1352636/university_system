from typing import Protocol, Any

class RecoveryRepository(Protocol):
    def consume_token(self, *args, **kwargs) -> Any: ...
