"""FE College University progression dashboard."""

from education_system.platform.cross_system.university_applications_gui import render

TITLE = "University progression"


def open_window(host) -> None:
    render(host, "fe_college")
