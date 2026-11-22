"""Who may act on admissions records.

The menu gate (``MENU_CAPABILITIES``) only decides who sees the
Admissions window. These helpers make the domain itself check the
signed-in principal, so a CLI flow, a script or an API route cannot read
or change applicant records without the ``admissions`` capability.

Work that runs without a person signed in — the public online form, the
cross-system intake consumer, scheduled jobs — names itself with
:func:`system_actor`, which binds a principal for that block only. An
anonymous call is refused, never treated as trusted.
"""

from __future__ import annotations

import contextlib
from typing import Any, Iterable, Iterator


def _access():
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return access


def principal() -> Any:
    return _access().current()


def actor() -> str | None:
    """Username to stamp on records and timeline events."""
    return principal().username or None


def require(action: str, capability: str | None = None) -> Any:
    """Require *capability* (default ``admissions``); return the principal."""
    access = _access()
    p = access.current()
    p.require(capability or access.ADMISSIONS, action)
    return p


def require_any(capabilities: Iterable[str], action: str) -> Any:
    access = _access()
    p = access.current()
    caps = tuple(capabilities)
    if not any(p.can(c) for c in caps):
        p.require(caps[0], action)
    return p


def can(capability: str | None = None) -> bool:
    access = _access()
    return access.current().can(capability or access.ADMISSIONS)


@contextlib.contextmanager
def system_actor(name: str, capabilities: Iterable[str] | None = None
                 ) -> Iterator[Any]:
    """Run a block as ``system:<name>`` with *capabilities* (default
    ``admissions``). Used by the online form, intake and scheduled jobs."""
    access = _access()
    caps = frozenset(capabilities or (access.ADMISSIONS,))
    p = access.Principal(username=f"system:{name}", user_id=None,
                         role="system", capabilities=caps)
    token = access.bind_request(p)
    try:
        yield p
    finally:
        access.unbind_request(token)


def log_sensitive(area: str, action: str, *, applicant_id: str,
                  allowed: bool = True) -> None:
    """Record a read/write of sensitive applicant data in the sixth form
    sensitive-access log (never raises)."""
    access = _access()
    try:
        access.log_sensitive_access(access.current(), area, action,
                                    record_ref=f"applicant:{applicant_id}",
                                    allowed=allowed)
    except Exception:  # noqa: BLE001 — logging must not block the work
        import logging
        logging.getLogger(__name__).warning(
            "Could not log sensitive access to %s for %s", area,
            applicant_id, exc_info=True)
