"""FE College: referrals to Adult Education (the platform's menu)."""

from education_system.platform.cross_system import adult_education_applications_cli
from education_system.systems.fe_college.services import adult_education_referrals


def board(ctl) -> None:
    identity = getattr(ctl, "identity", None)
    adult_education_applications_cli.menu(
        adult_education_referrals.SOURCE_SYSTEM,
        adult_education_referrals.referable_learners,
        can_refer=bool(identity and (identity.is_admin or identity.is_staff)),
        referrer=getattr(identity, "display_name", "") or "")
