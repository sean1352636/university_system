"""Trips screens: what each menu key opens (see ui.gui.navigation.pages)."""

from education_system.systems.secondary.ui.gui.navigation.pages import Page

PAGES: dict[str, Page] = {
    "trips": Page(
        "Trips & Payments",
        "trips_views",
        "draw_trips",
        state="_trips_state",
        links=("open_pupil",),
    ),
}
