"""Referrals to Alternative Provision and SEND service requests: what this
school gives the platform.

The referral workflow is the platform's (``platform.cross_system.ap_referrals``);
the school only lists who can be referred. The handover itself (attendance,
behaviour, exclusions, SEN, medical) is built by the secondary adapter's
``export_handover`` for the ``alternative_provision`` destination.
"""

from __future__ import annotations

from education_system.systems.secondary.modules.pupils.domain import pupils as P

SCHOOL = "secondary"


def on_roll_pupils() -> list[tuple[str, str]]:
    """``(pupil_id, label)`` for every pupil on roll."""
    return [(str(p.pupil_id), f"{p.display_name} (Year {p.year_group})")
            for p in P.list_pupils(roll_status="on_roll")]
