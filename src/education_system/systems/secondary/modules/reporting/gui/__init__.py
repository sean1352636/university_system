"""Reports screens: what each menu key opens (see ui.gui.navigation.pages)."""

from education_system.systems.secondary.ui.gui.navigation.pages import Page

PAGES: dict[str, Page] = {
    "attendance_report": Page(
        "Attendance Report",
        "attendance_report_views",
        "draw_attendance_report",
        state="_attendance_report_state",
        links=("open_pupil",),
    ),
    "behaviour_report": Page(
        "Behaviour Report",
        "behaviour_report_views",
        "draw_behaviour_report",
        state="_behaviour_report_state",
        links=("open_pupil",),
    ),
    "results_analysis": Page(
        "Results Analysis",
        "results_analysis_views",
        "draw_results_analysis",
        state="_results_analysis_state",
        links=("open_pupil",),
    ),
    "census": Page(
        "School Census",
        "census_views",
        "draw_census",
        state="_census_state",
        links=("open_pupil",),
    ),
    "data_export": Page(
        "Data Export",
        "data_export_views",
        "draw_data_export",
        state="_data_export_state",
    ),
}
