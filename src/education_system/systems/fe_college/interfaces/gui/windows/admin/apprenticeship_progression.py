"""FE College apprenticeship progression dashboard."""

from education_system.platform.cross_system.apprenticeship_applications_gui import render

TITLE = "Apprenticeship progression"


def open_window(host) -> None:
    render(host, "fe_college")
