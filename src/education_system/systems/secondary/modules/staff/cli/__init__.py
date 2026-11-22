"""Staff menus: what each menu key runs (see ui.cli.menus.menus)."""

MENUS: dict[str, str] = {
    "staff_directory": "staff_directory_cli",
    "departments": "departments_cli",
    "staff_absence": "staff_absence_cli",
    "single_central_record": "single_central_record_cli",
    "appraisals": "appraisals_cli",
}
