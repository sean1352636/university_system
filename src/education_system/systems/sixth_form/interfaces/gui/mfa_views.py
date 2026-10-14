"""Multi-Factor Authentication dialog (Sixth Form System) — moved to the platform.

This system used to carry its own email-only MFA dialog, backed by a
bespoke ``interfaces/mfa.py`` with its own SMTP sending and pending-code
table. It now opens the shared multi-method wizard at
``education_system.platform.delivery.gui.mfa_setup_gui``.

Kept as a shim so the existing GUI menu wiring keeps resolving.
"""

from __future__ import annotations

from typing import Any

from education_system.platform.delivery.gui import mfa_setup_gui

__all__ = ["open_mfa", "open_mfa_dialog"]


def open_mfa_dialog(parent: Any = None, *, auth: Any = None) -> None:
    """Open the shared MFA wizard for the signed-in user."""
    mfa_setup_gui.open_mfa(parent, auth=auth)


def open_mfa(host: Any) -> None:
    """Host-style entry point, matching the other systems."""
    mfa_setup_gui.open_mfa(host, auth=getattr(host, "auth", None))
