"""Communication screens: what each menu key opens (see ui.gui.navigation.pages)."""

from education_system.systems.secondary.ui.gui.navigation.pages import Page

PAGES: dict[str, Page] = {
    "messages": Page("Email", "email_views", "draw_outbox", links=("open_message",)),
    "parents_evenings": Page(
        "Parents' Evenings",
        "parents_evenings_views",
        "draw_parents_evenings",
        state="_parents_evenings_state",
        links=("open_pupil",),
    ),
    "announcements": Page(
        "Announcements",
        "announcements_views",
        "draw_announcements",
        state="_announcements_state",
    ),
    "letters": Page(
        "Letters",
        "letters_views",
        "draw_letters",
        state="_letters_state",
        links=("open_pupil",),
    ),
}
