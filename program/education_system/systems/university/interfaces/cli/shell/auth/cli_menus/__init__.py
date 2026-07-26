"""Auth CLI menus subpackage.

Aggregates the six top-level menu entry points (each implemented in its own
sibling module) and exposes a PEP 562 ``__getattr__`` hook so the lazy
``CHATBOT_AVAILABLE`` flag is computed on first access rather than at import
time. The split into per-menu modules came from breaking up the original
monolithic ``cli_menus.py``; this is now the canonical aggregator, not a
compatibility shim.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from ._shared import ROLES, is_chatbot_available  # noqa: E402,F401

from .auth_menu        import display_auth_menu
from .user_management  import display_user_management_menu
from .role_management  import display_role_management_menu
from .my_account       import display_my_account_menu
from .mfa_settings     import display_mfa_settings_menu
from .chatbot          import display_chatbot_integration_menu


def __getattr__(name):  # noqa: N807 — PEP 562 module-level hook
    """Lazy attribute lookup: defers the chatbot probe until first read."""
    if name == "CHATBOT_AVAILABLE":
        try:
            return is_chatbot_available()
        except Exception:
            return False
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "display_auth_menu",
    "display_user_management_menu",
    "display_role_management_menu",
    "display_my_account_menu",
    "display_mfa_settings_menu",
    "display_chatbot_integration_menu",
]
