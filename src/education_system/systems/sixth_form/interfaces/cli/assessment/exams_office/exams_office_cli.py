"""CLI: the Exams Office menu (dispatch label "Exams Office")."""

from __future__ import annotations

import importlib
import logging

from education_system.systems.sixth_form.interfaces.cli.assessment.exams_office.exams_cli_helpers import (
    pause,
    run_menu,
)

logger = logging.getLogger(__name__)

_PKG = "education_system.systems.sixth_form.interfaces.cli."

# (label, module under interfaces/cli, function)
_AREAS: tuple[tuple[str, str, str], ...] = (
    ("Exam timetable & clashes", "assessment.exams_office.timetable_cli", "run"),
    ("Invigilation", "assessment.exams_office.invigilation_cli", "run"),
    ("Exam registers & seating", "academics.attendance.attendance_exams_cli", "run"),
    ("Access arrangements", "assessment.exams_office.access_arrangements_cli", "run"),
    ("Special consideration", "assessment.exams_office.special_consideration_cli", "run"),
    ("Malpractice log", "assessment.exams_office.malpractice_cli", "run"),
    ("Post-results services", "assessment.exams_office.post_results_cli", "run"),
    ("Certificates", "assessment.exams_office.certificates_cli", "run"),
    ("Board data files (EDI)", "assessment.exams_office.edi_cli", "run"),
    ("Exam Entries", "assessment.exam_entries.exam_entry_cli", "run"),
    ("Results Day", "assessment.exam_results.exam_result_cli", "run"),
)


def _opener(module: str, func: str):
    def go() -> None:
        getattr(importlib.import_module(_PKG + module), func)()
    return go


def run() -> None:
    run_menu("Exams Office", [(label, _opener(m, f)) for label, m, f in _AREAS])


def dispatch(label: str) -> bool:
    if label != "Exams Office":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Exams Office CLI crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        pause()
    return True
