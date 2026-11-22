"""Reports menus: what each menu key runs (see ui.cli.menus.menus)."""

MENUS: dict[str, str] = {
    "attendance_report": "attendance_report_cli",
    "behaviour_report": "behaviour_report_cli",
    "results_analysis": "results_analysis_cli",
    "census": "census_cli",
    "data_export": "data_export_cli",
}
