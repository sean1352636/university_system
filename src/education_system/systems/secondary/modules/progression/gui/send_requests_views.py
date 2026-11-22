"""SEND Service Requests screen (asking the SEND service for advice or an
EHC needs assessment).

The board is the platform's (``platform.cross_system.send_referrals_gui``);
this page supplies the school's on-roll pupils and who may send a request
(the SENCO, ``access.SEND_EDITORS``). The SEND service's EHCP decisions also
land on the pupil's SEND record (``modules.send``) through the adapter.
"""

from __future__ import annotations

from tkinter import ttk
from typing import Callable

from education_system.platform.cross_system import send_referrals_gui
from education_system.systems.secondary.core.permissions.access import SEND_EDITORS, Principal
from education_system.systems.secondary.modules.progression.domain.ap_referrals import (
    SCHOOL,
    on_roll_pupils,
)


def draw_send_requests(parent: ttk.Frame, *, principal: Principal, state: dict,
                       open_pupil: Callable[[int], None] | None = None) -> None:
    send_referrals_gui.render(parent, SCHOOL, pupils=on_roll_pupils,
                              can_request=principal.role in SEND_EDITORS,
                              referrer=principal.username,
                              actor_user_id=principal.user_id
                              if isinstance(principal.user_id, int) else None)
