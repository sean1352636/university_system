"""Thread-safe global auth singleton."""

import threading

from education_system.college_system.infrastructure.auth.core import UserAuth

_auth_instance: UserAuth | None = None
_lock = threading.Lock()


def get_auth(db_path: str | None = None) -> UserAuth:
    """Get or create the global UserAuth instance."""
    global _auth_instance
    with _lock:
        if _auth_instance is None:
            _auth_instance = UserAuth(db_path)
        return _auth_instance


def reset_auth():
    """Reset the global auth instance (used in testing)."""
    global _auth_instance
    with _lock:
        _auth_instance = None
