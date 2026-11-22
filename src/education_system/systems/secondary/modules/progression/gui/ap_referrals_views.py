"""Referrals to Alternative Provision screen (pupils sent to the AP / PRU).

The board itself is the platform's (``platform.cross_system.ap_referrals_gui``):
this page supplies the school's on-roll pupils and who may refer. Pupils the
AP sends back as new admissions arrive on *Incoming from Primary*, marked
"(from AP)".
"""

from __future__ import annotations

from tkinter import ttk
from typing import Callable

from education_system.platform.cross_system import ap_referrals_gui
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.modules.progression.domain.ap_referrals import (
    SCHOOL,
    on_roll_pupils,
)


def draw_ap_referrals(parent: ttk.Frame, *, principal: Principal, state: dict,
                      open_pupil: Callable[[int], None] | None = None) -> None:
    ap_referrals_gui.render(parent, SCHOOL, pupils=on_roll_pupils,
                            can_refer=principal.is_admin, referrer=principal.username,
                            actor_user_id=principal.user_id
                            if isinstance(principal.user_id, int) else None)
