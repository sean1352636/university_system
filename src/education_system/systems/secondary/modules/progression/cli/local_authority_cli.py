"""Local Authority menu (see ``gui.local_authority_views``)."""

from __future__ import annotations

from education_system.platform.cross_system import local_authority_links_cli
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.modules.progression.domain.ap_referrals import (
    SCHOOL,
    on_roll_pupils,
)
from education_system.systems.secondary.modules.progression.gui.local_authority_views import (
    NOTIFIERS,
)


def menu(principal: Principal) -> None:
    local_authority_links_cli.menu(SCHOOL, on_roll_pupils,
                                   can_notify=principal.role in NOTIFIERS,
                                   referrer=principal.username,
                                   actor_user_id=principal.user_id
                                   if isinstance(principal.user_id, int) else None)
