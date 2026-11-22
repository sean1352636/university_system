"""SEND Service Requests screen (asking the SEND service for advice or an
EHC needs assessment).

The board is the platform's (``platform.cross_system.send_referrals_gui``);
this page supplies the school's on-roll pupils and who may send a request
(the head / SENCO - the page is admin only, see ``domain.access.ADMIN_ONLY``).
The SEND service's EHCP decisions also land on the pupil's SEND record
(``domain.pastoral.send``) and SEN status through the adapter.
"""

from __future__ import annotations

from education_system.platform.cross_system import send_referrals_gui
from education_system.systems.primary.domain import access
from education_system.systems.primary.domain.learners.pupils.ap_referrals import (
    SCHOOL,
    on_roll_pupils,
)
from education_system.systems.primary.interfaces.gui import kit
from education_system.systems.primary.interfaces.gui.learners.pupils.ap_referrals.ap_referrals_views import (  # noqa: E501
    _user_id,
)

TITLE = send_referrals_gui.TITLE


def open_send_requests(host) -> None:
    principal = getattr(host, "principal", None) or access.current()
    kit.show_page(host, TITLE, lambda parent: send_referrals_gui.render(
        parent, SCHOOL, pupils=on_roll_pupils, can_request=principal.is_admin,
        referrer=principal.username, actor_user_id=_user_id(host)))


__all__ = ["open_send_requests"]
