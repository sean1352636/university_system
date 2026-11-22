"""Training Provider Requests: FE learners sent on a short course. The board
is the platform's own (``training_provider_requests_gui``); this screen
hosts it. Certificates come back onto the learner's prior attainment."""

from __future__ import annotations

from education_system.platform.cross_system import training_provider_requests_gui
from education_system.systems.fe_college.services import adult_education_referrals

TITLE = training_provider_requests_gui.TITLE
SOURCE_SYSTEM = "fe_college"


def open_window(host) -> None:
    host.clear_content()
    identity = getattr(host.ctl, "identity", None)
    training_provider_requests_gui.render(
        host.content_frame, SOURCE_SYSTEM,
        learners=adult_education_referrals.referable_learners,
        can_request=bool(identity and (identity.is_admin or identity.is_staff)),
        referrer=getattr(identity, "display_name", "") or "")
    host.set_status(TITLE)
