"""Wellbeing screens: what each menu key opens (see ui.gui.navigation.pages)."""

from education_system.systems.secondary.ui.gui.navigation.pages import Page

PAGES: dict[str, Page] = {
    "wellbeing": Page(
        "Wellbeing",
        "wellbeing_views",
        "draw_wellbeing",
        state="_wellbeing_state",
        links=("open_pupil",),
    ),
}
