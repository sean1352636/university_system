"""Shared mutable state for the email infrastructure package."""

from __future__ import annotations

from typing import Any

# Import auth instance management from user_authentication
try:
    from university_system.infrastructure.auth import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

auth: Any = None  # Authentication context shared across modules

def set_auth(auth_instance):
    """Set the authentication instance for the email infrastructure."""
    global auth
    auth = auth_instance
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)


class AuthProxy:
    """Lightweight proxy to access the shared auth object safely."""

    def __bool__(self) -> bool:  # pragma: no cover - trivial
        return bool(auth)

    def __getattr__(self, name: str) -> Any:  # pragma: no cover - thin wrapper
        if auth is None:
            raise AttributeError(name)
        return getattr(auth, name)

    def __setattr__(self, name: str, value: Any) -> None:  # pragma: no cover - thin wrapper
        if name.startswith("_"):
            super().__setattr__(name, value)
            return
        if auth is None:
            raise AttributeError(name)
        setattr(auth, name, value)


auth_proxy = AuthProxy()
