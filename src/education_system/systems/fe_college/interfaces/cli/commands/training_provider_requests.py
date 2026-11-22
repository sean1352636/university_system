"""FE College: requests to the Training Provider (the platform's menu)."""

from education_system.platform.cross_system import training_provider_requests_cli
from education_system.systems.fe_college.services import adult_education_referrals


def board(ctl) -> None:
    identity = getattr(ctl, "identity", None)
    training_provider_requests_cli.menu(
        "fe_college", adult_education_referrals.referable_learners,
        can_request=bool(identity and (identity.is_admin or identity.is_staff)),
        referrer=getattr(identity, "display_name", "") or "")
