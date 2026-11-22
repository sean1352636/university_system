"""Assessment menus: what each menu key runs (see ui.cli.menus.menus)."""

MENUS: dict[str, str] = {
    "gradebook": "gradebook_cli",
    "assessment_points": "assessment_points_cli",
    "target_grades": "target_grades_cli",
    "headline_measures": "headline_measures_cli",
    "interventions": "interventions_cli",
    "reports_to_parents": "reports_to_parents_cli",
}
