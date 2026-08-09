from typing import Protocol, Any

class CredentialRepository(Protocol):
    def get_for_user(self, *args, **kwargs) -> Any: ...
