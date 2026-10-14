"""CLI flow for Change Password (Nursery System) — moved to the platform.

The implementation is now
``education_system.platform.delivery.cli.change_password_cli``. This
module stays as a re-export so the CLI menu dispatch keeps resolving.
"""

from __future__ import annotations

from education_system.platform.delivery.cli.change_password_cli import (  # noqa: F401
    dispatch,
    run,
)

__all__ = ["dispatch", "run"]
