"""Attendance screens: what each menu key opens (see ui.gui.navigation.pages)."""

from education_system.systems.secondary.ui.gui.navigation.pages import Page

PAGES: dict[str, Page] = {
    "attendance": Page(
        "Registers & Attendance",
        "attendance_views",
        "draw_attendance",
        state="_attendance_state",
        links=("open_pupil",),
    ),
    "attendance_concerns": Page(
        "Attendance Concerns",
        "attendance_concerns_views",
        "draw_attendance_concerns",
        state="_attendance_concerns_state",
        links=("open_pupil",),
    ),
}
