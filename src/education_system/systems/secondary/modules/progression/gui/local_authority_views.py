"""Local Authority screen: notifications to the authority (attendance
referrals, suspensions and exclusions, children missing education, elective
home education, EHC needs assessment requests) and the school places it
allocates here.

The board is the platform's (``platform.cross_system.local_authority_links_gui``);
this page supplies the school's on-roll pupils and who may notify (admin -
``access.RESTRICTED``). A place from the authority lands under Incoming from
Primary (labelled "from LA"); the authority's EHC decisions also land on the
pupil's SEND record through the adapter.
"""

from __future__ import annotations

from tkinter import ttk
from typing import Callable

from education_system.platform.cross_system import local_authority_links_gui
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.modules.progression.domain.ap_referrals import (
    SCHOOL,
    on_roll_pupils,
)

#: Who may send a notification (the head / admissions office).
NOTIFIERS = frozenset({"admin", "superadmin"})


def draw_local_authority(parent: ttk.Frame, *, principal: Principal, state: dict,
                         open_pupil: Callable[[int], None] | None = None) -> None:
    local_authority_links_gui.render(parent, SCHOOL, pupils=on_roll_pupils,
                                     can_notify=principal.role in NOTIFIERS,
                                     referrer=principal.username,
                                     actor_user_id=principal.user_id
                                     if isinstance(principal.user_id, int) else None)
