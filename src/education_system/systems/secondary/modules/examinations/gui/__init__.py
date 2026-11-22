"""Examinations screens: what each menu key opens (see ui.gui.navigation.pages)."""

from education_system.systems.secondary.ui.gui.navigation.pages import Page

PAGES: dict[str, Page] = {
    "mock_exams": Page(
        "Mock Exams",
        "mock_exams_views",
        "draw_mock_exams",
        state="_mock_exams_state",
        links=("open_pupil",),
    ),
    "exam_entries": Page(
        "Exam Entries",
        "exam_entries_views",
        "draw_exam_entries",
        state="_exam_entries_state",
        links=("open_pupil", "on_status"),
    ),
    "exam_results": Page(
        "Exam Results",
        "exam_results_views",
        "draw_exam_results",
        state="_exam_results_state",
        links=("open_pupil", "on_status"),
    ),
}
