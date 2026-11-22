"""Curriculum menus: what each menu key runs (see ui.cli.menus.menus)."""

MENUS: dict[str, str] = {
    "academic_year": "calendar_cli",
    "year_groups": "year_groups_cli",
    "form_groups": "form_groups_cli",
    "subjects": "subjects_cli",
    "teaching_groups": "teaching_groups_cli",
    "timetable": "timetable_cli",
    "lesson_plans": "lesson_plans_cli",
    "cover": "cover_cli",
    "homework": "homework_cli",
    "options": "options_cli",
    "enrichment": "enrichment_cli",
    "form_tutors": "form_tutors_cli",
}
