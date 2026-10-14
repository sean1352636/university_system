"""FE College University progression commands."""

from education_system.platform.cross_system import university_applications_cli


def dashboard(_ctl) -> None:
    university_applications_cli.dashboard("fe_college")


def create(_ctl) -> None:
    university_applications_cli.create("fe_college")
