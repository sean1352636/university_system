"""Staff screens: what each menu key opens (see ui.gui.navigation.pages)."""

from education_system.systems.secondary.ui.gui.navigation.pages import Page

PAGES: dict[str, Page] = {
    "staff_directory": Page(
        "Staff Directory",
        "staff_directory_views",
        "draw_staff_directory",
        state="_staff_directory_state",
    ),
    "departments": Page(
        "Departments",
        "departments_views",
        "draw_departments",
        state="_departments_state",
    ),
    "staff_absence": Page(
        "Staff Absence",
        "staff_absence_views",
        "draw_staff_absence",
        state="_staff_absence_state",
    ),
    "single_central_record": Page(
        "Single Central Record",
        "single_central_record_views",
        "draw_single_central_record",
        state="_single_central_record_state",
    ),
    "appraisals": Page(
        "Appraisals & CPD",
        "appraisals_views",
        "draw_appraisals",
        state="_appraisals_state",
    ),
}
