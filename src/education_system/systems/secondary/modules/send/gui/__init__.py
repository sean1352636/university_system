"""SEND screens: what each menu key opens (see ui.gui.navigation.pages)."""

from education_system.systems.secondary.ui.gui.navigation.pages import Page

PAGES: dict[str, Page] = {
    "send": Page(
        "SEND",
        "send_views",
        "draw_send",
        state="_send_state",
        links=("open_pupil",),
    ),
}
