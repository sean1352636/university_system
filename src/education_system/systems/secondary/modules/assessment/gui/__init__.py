"""Assessment screens: what each menu key opens (see ui.gui.navigation.pages)."""

from education_system.systems.secondary.ui.gui.navigation.pages import Page

PAGES: dict[str, Page] = {
    "gradebook": Page(
        "Gradebook",
        "gradebook_views",
        "draw_gradebook",
        state="_gradebook_state",
        links=("open_pupil",),
    ),
    "assessment_points": Page(
        "Assessment Points",
        "assessment_points_views",
        "draw_assessment_points",
        state="_assessment_points_state",
        links=("open_pupil",),
    ),
    "target_grades": Page(
        "Target Grades",
        "target_grades_views",
        "draw_target_grades",
        state="_target_grades_state",
        links=("open_pupil",),
    ),
    "headline_measures": Page(
        "Attainment 8 & Progress 8",
        "headline_measures_views",
        "draw_headline_measures",
        state="_headline_measures_state",
        links=("open_pupil",),
    ),
    "interventions": Page(
        "Interventions",
        "interventions_views",
        "draw_interventions",
        state="_interventions_state",
        links=("open_pupil",),
    ),
    "reports_to_parents": Page(
        "Reports to Parents",
        "reports_to_parents_views",
        "draw_reports_to_parents",
        state="_reports_to_parents_state",
        links=("open_pupil",),
    ),
}
