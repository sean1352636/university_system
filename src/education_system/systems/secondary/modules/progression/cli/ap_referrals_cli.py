"""Referrals to Alternative Provision menu (see ``domain.ap_referrals``)."""

from __future__ import annotations

from education_system.platform.cross_system import ap_referrals_cli
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.modules.progression.domain.ap_referrals import (
    SCHOOL,
    on_roll_pupils,
)


def menu(principal: Principal) -> None:
    ap_referrals_cli.menu(SCHOOL, on_roll_pupils, can_refer=principal.is_admin,
                          referrer=principal.username,
                          actor_user_id=principal.user_id
                          if isinstance(principal.user_id, int) else None)
