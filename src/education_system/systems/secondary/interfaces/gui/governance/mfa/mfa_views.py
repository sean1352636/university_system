"""Multi-Factor Authentication view (Secondary School System) — moved to the platform.

This system used to carry its own email-only MFA screen. It now opens the
shared multi-method wizard at
``education_system.platform.delivery.gui.mfa_setup_gui``, which offers an
authenticator app, SMS, email and recovery codes rather than email alone.

Kept as a shim so the existing GUI menu wiring keeps resolving.
"""

from __future__ import annotations

from typing import Any

from education_system.platform.delivery.gui import mfa_setup_gui

__all__ = ["open_mfa"]


def open_mfa(host: Any) -> None:
    """Open the shared MFA wizard for the signed-in user."""
    mfa_setup_gui.open_mfa(host, auth=getattr(host, "auth", None))
