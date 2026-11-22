"""Referrals to Alternative Provision and SEND service requests: what this
school gives the platform.

The referral workflow is the platform's (``platform.cross_system.ap_referrals``);
the school only lists who can be referred. The handover itself is built by the
primary adapter's ``export_handover``. A pupil the AP sends back as a new
admission arrives through the platform transfer, like any other.
"""

from __future__ import annotations

from education_system.systems.primary.domain.learners.pupils import pupils

SCHOOL = "primary"
TITLE = "Referrals to Alternative Provision"


def _year(year_group: str) -> str:
    return "Reception" if year_group == "R" else f"Year {year_group}"


def on_roll_pupils() -> list[tuple[str, str]]:
    """``(pupil_id, label)`` for every pupil on roll."""
    return [(str(p.pupil_id), f"{p.first_name} {p.last_name} ({_year(p.year_group)})")
            for p in pupils.list_pupils()]
