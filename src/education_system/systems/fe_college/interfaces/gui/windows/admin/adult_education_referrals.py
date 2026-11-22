"""Referrals to Adult Education. The board is the platform's own
(``adult_education_applications_gui``); this screen hosts it."""

from __future__ import annotations

from education_system.platform.cross_system import adult_education_applications_gui
from education_system.systems.fe_college.services import adult_education_referrals

TITLE = adult_education_applications_gui.TITLE


def open_window(host) -> None:
    host.clear_content()
    identity = getattr(host.ctl, "identity", None)
    adult_education_applications_gui.render(
        host.content_frame, adult_education_referrals.SOURCE_SYSTEM,
        learners=adult_education_referrals.referable_learners,
        can_refer=bool(identity and (identity.is_admin or identity.is_staff)),
        referrer=getattr(identity, "display_name", "") or "")
    host.set_status(TITLE)
