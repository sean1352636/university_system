"""Pupils screens: what each menu key opens (see ui.gui.navigation.pages)."""

from education_system.systems.secondary.ui.gui.navigation.pages import Page

PAGES: dict[str, Page] = {
    "enrolment": Page(
        "Enrolment & Leavers",
        "enrolment_views",
        "draw_enrolment",
        state="_enrolment_state",
        links=("open_pupil",),
    ),
    "bulk_import": Page(
        "Bulk Import", "bulk_import_views", "draw_bulk_import", links=("open_pupil",)
    ),
    "alumni": Page(
        "Alumni", "alumni_views", "draw_alumni", state="_alumni_state", links=("open_pupil",)
    ),
}
