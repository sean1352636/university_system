"""CLI: board data files — entries export and results import (EDI or CSV)."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.assessment.exams_office import edi
from education_system.systems.sixth_form.interfaces.cli.assessment.exams_office.exams_cli_helpers import (
    ask,
    board,
    pause,
    pick,
    run_menu,
    save_text,
    series,
    yes,
)

_NOTE = ("  Note: the fixed-width (EDI) layout is a configurable field map in "
         "exams_office/edi.py;\n  check it against the current JCQ Formats specification "
         "before live use.")


def export() -> None:
    print(_NOTE)
    b = board()
    season, year = series()
    fmt = pick("Format", ["edi", "csv"], default="edi")
    f = edi.export_entries(b, season, year, fmt=fmt,
                           centre_number=ask("Centre number", default=edi.CENTRE_NUMBER) or None,
                           include_withdrawn=yes("Include withdrawals", default=True))
    for p in f.problems:
        print(f"  ! {p}")
    save_text(f.content, f.suggested_name)


def import_results() -> None:
    print(_NOTE)
    path = ask("Results file path", required=True)
    season, year = series()
    fmt = pick("Format", ["auto", "csv", "edi"], default="auto")
    b = board(allow_blank=True) if fmt != "csv" else ""
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            content = fh.read()
    except OSError as e:
        print(f"  ✗ {e}")
        return
    dry = edi.import_results_file(content, season=season, year=year, fmt=fmt,
                                  exam_board=b or None, dry_run=True)
    print(f"\n  Dry run: {dry.rows} row(s), {dry.components} paper result(s), "
          f"{dry.qualifications} qualification result(s), {len(dry.problems)} problem(s)")
    for p in dry.problems[:30]:
        print(f"    {p}")
    if yes("Import now (results stay hidden until the series is released)"):
        rep = edi.import_results_file(content, season=season, year=year, fmt=fmt,
                                      exam_board=b or None)
        print(f"  ✓ Imported {rep.components} paper and {rep.qualifications} "
              "qualification result(s)")
    pause()


MENU = [("Export entries file", export), ("Import results file", import_results)]


def run() -> None:
    run_menu("Board Data Files (EDI)", MENU)
