"""Pupils menus: what each menu key runs (see ui.cli.menus.menus)."""

MENUS: dict[str, str] = {
    "pupil_directory": "pupils_cli:directory",
    "add_pupil": "pupils_cli:add",
    "search_pupils": "pupils_cli:search",
    "pupil_profile": "pupils_cli:profile",
    "enrolment": "enrolment_cli",
    "bulk_import": "bulk_import_cli",
    "alumni": "alumni_cli",
}
