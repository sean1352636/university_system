"""Session helpers for the GUI layer.

There is deliberately no controller layer in this system. Windows call
the services directly, because the services already carry everything a
controller would: the permission check, the scoping, the validation and
the audit write. A class that only forwarded to them would be a second
place to keep in step with no behaviour of its own.

What *is* useful is the small amount of session plumbing every window
would otherwise repeat — turning a login into an :class:`Actor`, asking
what that actor may do, and getting their dashboard. That lives here.
"""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.application.workspace import reporting_service
from education_system.systems.apprenticeships.application.security.access import Actor, resolve

logger = logging.getLogger(__name__)

__all__ = [
    "Actor",
    "actor_from_auth",
    "capability_summary",
    "dashboard_for",
    "resolve",
]


def actor_from_auth(shared_auth: Any, user_info: Any = None, role: str | None = None) -> Actor:
    """Turn a shared-auth session into an apprenticeships :class:`Actor`."""
    return resolve(user_info or getattr(shared_auth, "current_user", None), role)


def dashboard_for(actor: Actor) -> dict[str, Any]:
    """The dashboard payload for *actor*'s role."""
    return reporting_service.dashboard(actor)


def capability_summary(actor: Actor) -> list[tuple[str, bool]]:
    """Every permission and whether *actor* holds it.

    Used by the settings and about screens to answer "why can't I see
    that button?" without anyone having to read the permission table in
    the source.
    """
    held = actor.permissions()
    return [(name, name in held) for name in config.PERMISSIONS]
