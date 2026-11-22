"""FE College: incoming referrals from the Sixth Form, Apprenticeships, Adult Education and
the Training Provider."""

from education_system.platform.cross_system import fe_applications_cli


def incoming(ctl) -> None:
    identity = getattr(ctl, "identity", None)
    fe_applications_cli.work_queue(getattr(identity, "label", None) or "FE admissions")
