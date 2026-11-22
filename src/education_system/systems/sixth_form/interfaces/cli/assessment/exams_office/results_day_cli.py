"""CLI: results release/embargo, qualification results, import, history.

These flows are added to the Results Day menu.
"""

from __future__ import annotations

from education_system.systems.sixth_form.domain.assessment.exams_office import results_day as rd
from education_system.systems.sixth_form.interfaces.cli.assessment.exams_office.exams_cli_helpers import (
    ask,
    board,
    form,
    pause,
    series,
    show_table,
    yes,
)


def releases() -> None:
    print("\n═══ Results release & embargo ═══")
    rows = rd.list_releases()
    show_table([("Series", 12), ("Board", 18), ("Results day", 11), ("Embargo until", 16),
                ("Released", 16), ("Hidden p/q", 10)],
               [(f"{r.season} {r.year}", r.exam_board or "All boards", r.results_date,
                 r.embargo_until, r.released_at or ("DUE" if r.due else "embargoed"),
                 "{}/{}".format(*rd.embargoed_counts(r.season, r.year))) for r in rows])
    if yes("Schedule / change a results day"):
        season, year = series()
        b = board(allow_blank=True)
        rd.schedule_release({"season": season, "year": year, "exam_board": b,
                             "results_date": ask("Results day (YYYY-MM-DD)", required=True),
                             "embargo_until": ask(f"Embargo until (blank = "
                                                  f"{rd.DEFAULT_RELEASE_TIME})")})
        print("  ✓ Scheduled")
    pause()


def release() -> None:
    season, year = series()
    b = board(allow_blank=True)
    if yes(f"Release {season} {year} {b or '(all boards)'} to students now"):
        comp, qual = rd.release_series(season, year, b or None)
        print(f"  ✓ Released {comp} paper and {qual} qualification result(s)")
    pause()


def release_due() -> None:
    out = rd.release_due()
    print(f"  ✓ {len(out)} series released" if out else "  Nothing due.")
    pause()


def qualification_results() -> None:
    season, year = series()
    rows = rd.list_qualification_results(season=season, year=year, released_only=False)
    show_table([("#", 4), ("Student", 10), ("Board", 18), ("Entry", 8), ("Subject", 16),
                ("Grade", 12), ("Marks", 5), ("Visible", 7)],
               [(q.qual_result_id, q.student_id, q.exam_board, q.entry_code, q.subject,
                 q.grade, q.marks, "Yes" if q.visible else "") for q in rows])
    if yes("Add / update a qualification result"):
        data = form([("student_id", "Student ID"), ("entry_code", "Entry code"),
                     ("grade", "Grade"), ("marks", "Total marks"), ("ums", "UMS"),
                     ("qualification_type", "Qualification type (blank = catalogue)")])
        rd.save_qualification_result({**data, "exam_board": board(), "season": season,
                                      "year": year})
        print("  ✓ Saved")
    pause()


def roll_up() -> None:
    season, year = series()
    rows = rd.component_totals(season, year)
    show_table([("Student", 10), ("Name", 22), ("Entry", 8), ("Comps", 5), ("Results", 7),
                ("Marks", 6), ("Qual grade", 10)],
               [(t.student_id, t.full_name, t.entry_code, t.components_entered,
                 t.components_with_results, t.total_marks, t.qualification_grade)
                for t in rows])
    pause()


def import_results() -> None:
    from education_system.systems.sixth_form.interfaces.cli.assessment.exams_office import (
        edi_cli,
    )
    edi_cli.import_results()


def history() -> None:
    rid = ask("Paper result # (blank = all)")
    rows = rd.history(result_id=int(rid) if rid else None)
    show_table([("When", 19), ("Result", 6), ("Qual", 5), ("Old", 6), ("New", 6),
                ("Marks", 11), ("Reason", 44)],
               [(h.changed_at, h.result_id, h.qual_result_id, h.old_grade, h.new_grade,
                 f"{h.old_marks}→{h.new_marks}", h.reason) for h in rows])
    pause()


MENU = [
    ("Release schedule & embargo", releases),
    ("Release a series", release),
    ("Release everything due", release_due),
    ("Qualification results", qualification_results),
    ("Component roll-up", roll_up),
    ("Import board results file", import_results),
    ("Result history", history),
]
