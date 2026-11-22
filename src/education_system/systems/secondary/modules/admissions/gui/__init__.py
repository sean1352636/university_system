"""Admissions screens: what each menu key opens (see ui.gui.navigation.pages)."""

from education_system.systems.secondary.ui.gui.navigation.pages import Page

PAGES: dict[str, Page] = {
    "admissions": Page(
        "Admissions",
        "admissions_views",
        "draw_admissions",
        state="_admissions_state",
        links=("open_application",),
    ),
}
