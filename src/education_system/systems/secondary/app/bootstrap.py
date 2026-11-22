"""Start-up shared by the CLI and GUI entry points.

Both are launched only by the unified launcher after the shared login. Each
one checks the shared session is there, works out who is signed in and opens
their activity-log session, then, for staff, runs the year-end rollover when
it is due. Those steps live here so the two programs can't drift apart.
"""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.secondary.core.permissions import access
from education_system.systems.secondary.infrastructure.logging import activity_log

logger = logging.getLogger(__name__)


def require_shared_session(shared_auth: Any, interface: str) -> None:
    """Refuse to start without the launcher's signed-in session (no standalone login)."""
    if shared_auth is None or not getattr(shared_auth, "current_user", None):
        logger.error("Secondary %s invoked without a shared_auth session", interface.upper())
        raise RuntimeError(
            f"The Secondary School {interface.upper()} must be launched via "
            "python -m education_system - no standalone login is available.")


def start_session(auth: Any, role: str | None, interface: str) -> access.Principal:
    """Who is signed in, with their activity-log session opened for *interface*."""
    principal = access.from_auth(auth, role)
    activity_log.start_session(principal, interface)
    return principal


def roll_year_if_due(principal: access.Principal) -> list[Any]:
    """Run the year-end rollover if a new school year has started (staff start-up)."""
    from education_system.systems.secondary.modules.pupils.domain import year_rollover
    return year_rollover.run_if_due(triggered_by=principal)


__all__ = ["require_shared_session", "roll_year_if_due", "start_session"]
