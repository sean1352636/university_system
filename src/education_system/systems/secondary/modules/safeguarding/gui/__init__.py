"""Safeguarding screens: what each menu key opens (see ui.gui.navigation.pages)."""

from education_system.systems.secondary.ui.gui.navigation.pages import Page

PAGES: dict[str, Page] = {
    "safeguarding": Page(
        "Safeguarding",
        "safeguarding_views",
        "draw_safeguarding",
        state="_safeguarding_state",
        links=("open_pupil",),
    ),
    "report_concern": Page(
        "Report a Safeguarding Concern",
        "report_concern_views",
        "draw_report_concern",
        state="_report_concern_state",
        links=("open_pupil",),
    ),
}
