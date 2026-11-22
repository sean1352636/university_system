"""SEND Service Requests menu (see ``platform.cross_system.send_referrals``)."""

from __future__ import annotations

from education_system.platform.cross_system import send_referrals_cli
from education_system.systems.primary.domain import access
from education_system.systems.primary.domain.learners.pupils.ap_referrals import (
    SCHOOL,
    on_roll_pupils,
)

TITLE = send_referrals_cli.TITLE


def open_send_requests() -> None:
    principal = access.current()
    send_referrals_cli.menu(SCHOOL, on_roll_pupils, can_request=principal.is_admin,
                            referrer=principal.username)


def dispatch(label: str) -> bool:
    if label != TITLE:
        return False
    open_send_requests()
    return True


__all__ = ["dispatch", "open_send_requests"]
