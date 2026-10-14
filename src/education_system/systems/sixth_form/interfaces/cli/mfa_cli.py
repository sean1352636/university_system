"""Multi-Factor Authentication CLI (Sixth Form System) — moved to the platform.

This system used to carry its own email-only MFA menu. It now opens the
shared multi-method enrolment CLI at
``education_system.platform.delivery.cli.mfa_setup_cli``, which offers an
authenticator app, email, SMS and recovery codes, against the shared
``auth.db`` — the same store the GUI wizard writes to.

Kept as a shim so the existing CLI menu dispatch keeps resolving.
"""

from __future__ import annotations

from education_system.platform.delivery.cli.mfa_setup_cli import (  # noqa: F401
    dispatch,
    open_mfa,
    run,
)

__all__ = ["dispatch", "open_mfa", "run"]
