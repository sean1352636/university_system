"""Local Authority menu (see ``platform.cross_system.local_authority_links``)."""

from __future__ import annotations

from education_system.platform.cross_system import local_authority_links_cli
from education_system.systems.primary.domain import access
from education_system.systems.primary.domain.learners.pupils.ap_referrals import (
    SCHOOL,
    on_roll_pupils,
)

TITLE = local_authority_links_cli.TITLE


def open_local_authority() -> None:
    principal = access.current()
    local_authority_links_cli.menu(SCHOOL, on_roll_pupils, can_notify=principal.is_admin,
                                   referrer=principal.username)


def dispatch(label: str) -> bool:
    if label != TITLE:
        return False
    open_local_authority()
    return True


__all__ = ["dispatch", "open_local_authority"]
