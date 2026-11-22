"""Behaviour screens: what each menu key opens (see ui.gui.navigation.pages)."""

from education_system.systems.secondary.ui.gui.navigation.pages import Page

PAGES: dict[str, Page] = {
    "behaviour": Page(
        "Behaviour & Rewards",
        "behaviour_views",
        "draw_behaviour",
        state="_behaviour_state",
        links=("open_pupil",),
    ),
    "detentions": Page(
        "Detentions",
        "detentions_views",
        "draw_detentions",
        state="_detentions_state",
        links=("open_pupil",),
    ),
    "exclusions": Page(
        "Suspensions & Exclusions",
        "exclusions_views",
        "draw_exclusions",
        state="_exclusions_state",
        links=("open_pupil",),
    ),
}
