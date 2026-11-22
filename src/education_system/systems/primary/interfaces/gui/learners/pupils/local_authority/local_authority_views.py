"""Local Authority screen: notifications to the authority (attendance
referrals, suspensions and exclusions, children missing education, elective
home education, EHC needs assessment requests) and the school places it
allocates here.

The board is the platform's (``platform.cross_system.local_authority_links_gui``);
this page supplies the school's on-roll pupils and who may notify (the head /
admin - the page is admin only, see ``domain.access.ADMIN_ONLY``). A place
from the authority is an accepted application on Admissions; enrolling it
tells the platform. The authority's EHC decisions also land on the pupil's
SEND record and SEN status through the adapter.
"""

from __future__ import annotations

from education_system.platform.cross_system import local_authority_links_gui
from education_system.systems.primary.domain import access
from education_system.systems.primary.domain.learners.pupils.ap_referrals import (
    SCHOOL,
    on_roll_pupils,
)
from education_system.systems.primary.interfaces.gui import kit
from education_system.systems.primary.interfaces.gui.learners.pupils.ap_referrals.ap_referrals_views import (  # noqa: E501
    _user_id,
)

TITLE = local_authority_links_gui.TITLE


def open_local_authority(host) -> None:
    principal = getattr(host, "principal", None) or access.current()
    kit.show_page(host, TITLE, lambda parent: local_authority_links_gui.render(
        parent, SCHOOL, pupils=on_roll_pupils, can_notify=principal.is_admin,
        referrer=principal.username, actor_user_id=_user_id(host)))


__all__ = ["open_local_authority"]
