"""FE College apprenticeship progression commands."""

from education_system.platform.cross_system import apprenticeship_applications_cli


def dashboard(_ctl) -> None:
    apprenticeship_applications_cli.dashboard("fe_college")


def create(_ctl) -> None:
    apprenticeship_applications_cli.new_application("fe_college")
