"""Correspondence, as a tutor sees it.

The same screen as the admin view, not a second implementation: the
service scopes the log to the actor's caseload, so a tutor opening this
sees their own apprentices and the employers who supervise them. Nav
resolves modules inside each role's own package, so a shared screen is
re-exported rather than duplicated.
"""

from __future__ import annotations

from education_system.systems.apprenticeships.interfaces.gui.windows.admin.email import (
    render,
)

__all__ = ["render"]
