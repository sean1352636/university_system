"""Examinations menus: what each menu key runs (see ui.cli.menus.menus)."""

MENUS: dict[str, str] = {
    "mock_exams": "mock_exams_cli",
    "exam_entries": "exam_entries_cli",
    "exam_results": "exam_results_cli",
}
