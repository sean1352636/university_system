"""Referrals to Alternative Provision menu (see ``domain.learners.pupils.ap_referrals``)."""

from __future__ import annotations

from education_system.platform.cross_system import ap_referrals_cli
from education_system.systems.primary.domain import access
from education_system.systems.primary.domain.learners.pupils.ap_referrals import (
    SCHOOL,
    TITLE,
    on_roll_pupils,
)


def open_ap_referrals() -> None:
    principal = access.current()
    ap_referrals_cli.menu(SCHOOL, on_roll_pupils, can_refer=principal.is_admin,
                          referrer=principal.username)


def dispatch(label: str) -> bool:
    if label != TITLE:
        return False
    open_ap_referrals()
    return True


__all__ = ["dispatch", "open_ap_referrals"]
