"""Library screens: what each menu key opens (see ui.gui.navigation.pages)."""

from education_system.systems.secondary.ui.gui.navigation.pages import Page

PAGES: dict[str, Page] = {
    "library": Page(
        "Library", "library_views", "draw_library", state="_library_state", links=("open_pupil",)
    ),
}
