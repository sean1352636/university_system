from typing import Protocol, Any

class SessionRepository(Protocol):
    def get(self, *args, **kwargs) -> Any: ...
