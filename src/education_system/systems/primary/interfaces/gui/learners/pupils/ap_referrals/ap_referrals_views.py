"""Referrals to Alternative Provision screen (pupils sent to the AP / PRU).

The board is the platform's (``platform.cross_system.ap_referrals_gui``);
this page supplies the school's on-roll pupils and who may refer (the head /
admin - the page is admin only, see ``domain.access.ADMIN_ONLY``).
"""

from __future__ import annotations

from education_system.platform.cross_system import ap_referrals_gui
from education_system.systems.primary.domain import access
from education_system.systems.primary.domain.learners.pupils.ap_referrals import (
    SCHOOL,
    TITLE,
    on_roll_pupils,
)
from education_system.systems.primary.interfaces.gui import kit


def _user_id(host) -> int | None:
    user = getattr(getattr(host, "auth", None), "current_user", None) or {}
    uid = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    return uid if isinstance(uid, int) else None


def open_ap_referrals(host) -> None:
    principal = getattr(host, "principal", None) or access.current()
    kit.show_page(host, TITLE, lambda parent: ap_referrals_gui.render(
        parent, SCHOOL, pupils=on_roll_pupils, can_refer=principal.is_admin,
        referrer=principal.username, actor_user_id=_user_id(host)))


__all__ = ["open_ap_referrals"]
