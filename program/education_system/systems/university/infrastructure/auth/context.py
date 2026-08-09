"""Thread-safe current authenticated-principal registry."""
from .facade import (
    OptionalDependencyError, get_chatbot_class, is_chatbot_available,
    is_voice_interface_available, logger,
)
import threading

_current_auth_instance = None

_auth_instance_lock = threading.Lock()

def __getattr__(name):  # noqa: N807 — PEP 562 module-level hook
    if name == 'CHATBOT_AVAILABLE':
        try:
            return is_chatbot_available()
        except (ImportError, OptionalDependencyError, AttributeError) as e:
            logger.warning(f"Failed to probe chatbot availability: {e}")
            return False
    if name == 'VOICE_AVAILABLE':
        try:
            return is_voice_interface_available()
        except (ImportError, OptionalDependencyError, AttributeError):
            return False
    if name == 'UniversityChatbot':
        try:
            return get_chatbot_class()
        except (ImportError, OptionalDependencyError, AttributeError) as e:
            logger.warning(f"Failed to get chatbot class: {e}")
            return None
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

def get_current_user():
    """
    Get the current logged-in user information from the global auth instance.

    Returns
    -------
    dict or None
        User information dictionary containing user details if a user
        is logged in, or None if no user is logged in.
    """
    with _auth_instance_lock:
        if _current_auth_instance and _current_auth_instance.current_user:
            return _current_auth_instance.current_user
        return None

def set_auth_instance(auth_instance):
    """
    Set the global authentication instance for the application.

    Parameters
    ----------
    auth_instance : UserAuth
        The authentication instance to register globally.
    """
    global _current_auth_instance
    with _auth_instance_lock:
        _current_auth_instance = auth_instance

def get_auth_instance():
    """Get the current global auth instance"""
    with _auth_instance_lock:
        return _current_auth_instance
