"""Medical screens: what each menu key opens (see ui.gui.navigation.pages)."""

from education_system.systems.secondary.ui.gui.navigation.pages import Page

PAGES: dict[str, Page] = {
    "medical": Page(
        "Medical",
        "medical_views",
        "draw_medical",
        state="_medical_state",
        links=("open_pupil",),
    ),
}
