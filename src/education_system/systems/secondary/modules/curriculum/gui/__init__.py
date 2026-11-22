"""Curriculum screens: what each menu key opens (see ui.gui.navigation.pages)."""

from education_system.systems.secondary.ui.gui.navigation.pages import Page

PAGES: dict[str, Page] = {
    "academic_year": Page(
        "Academic Year & Calendar",
        "calendar_views",
        "draw_academic_calendar",
        state="_calendar_state",
    ),
    "year_groups": Page(
        "Year Groups", "year_groups_views", "draw_year_groups", links=("open_year",)
    ),
    "form_groups": Page(
        "Form Groups",
        "form_groups_views",
        "draw_form_groups",
        state="_form_groups_state",
        links=("open_form",),
    ),
    "subjects": Page("Subjects", "subjects_views", "draw_subjects", state="_subjects_state"),
    "teaching_groups": Page(
        "Teaching Groups",
        "teaching_groups_views",
        "draw_teaching_groups",
        state="_teaching_groups_state",
        links=("open_group",),
    ),
    "timetable": Page("Timetable", "timetable_views", "draw_timetable", state="_timetable_state"),
    "lesson_plans": Page(
        "Lesson Plans", "lesson_plans_views", "draw_lesson_plans", state="_lesson_plans_state"
    ),
    "cover": Page("Cover", "cover_views", "draw_cover", state="_cover_state"),
    "homework": Page(
        "Homework",
        "homework_views",
        "draw_homework",
        state="_homework_state",
        links=("open_pupil",),
    ),
    "options": Page(
        "Year 9 Options",
        "options_views",
        "draw_options",
        state="_options_state",
        links=("open_pupil",),
    ),
    "enrichment": Page(
        "Enrichment & Clubs",
        "enrichment_views",
        "draw_enrichment",
        state="_enrichment_state",
        links=("open_pupil",),
    ),
    "form_tutors": Page(
        "Form Tutors",
        "form_tutors_views",
        "draw_form_tutors",
        state="_form_tutors_state",
        links=("open_pupil",),
    ),
}
