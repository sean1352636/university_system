"""SEND Service Requests menu (see ``gui.send_requests_views``)."""

from __future__ import annotations

from education_system.platform.cross_system import send_referrals_cli
from education_system.systems.secondary.core.permissions.access import SEND_EDITORS, Principal
from education_system.systems.secondary.modules.progression.domain.ap_referrals import (
    SCHOOL,
    on_roll_pupils,
)


def menu(principal: Principal) -> None:
    send_referrals_cli.menu(SCHOOL, on_roll_pupils,
                            can_request=principal.role in SEND_EDITORS,
                            referrer=principal.username,
                            actor_user_id=principal.user_id
                            if isinstance(principal.user_id, int) else None)
