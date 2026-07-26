"""CLI handlers for mock exams."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.systems.secondary.domain.assessment.mock_exams import (
    mock_exams as data,
)
from education_system.systems.secondary.domain.assessment.mock_exams.mock_exams import (
    SERIES_STATUSES, PAPER_TIERS,
)
from education_system.systems.secondary.domain.academics.subjects import (
    subjects as subjects_data,
)
from education_system.systems.secondary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS,
)

logger = logging.getLogger(__name__)


def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _safe(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            print(f"  Validation error: {e}")
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _print_series(rows: list[data.MockSeries]) -> None:
    if not rows:
        print("  (no series)")
        return
    print(f"  {'ID':<4} {'Yr':<3} {'Start':<10} {'End':<10} "
          f"{'Status':<10} {'Name':<40}")
    print(f"  {'-'*4} {'-'*3} {'-'*10} {'-'*10} {'-'*10} {'-'*40}")
    for s in rows:
        print(f"  {s.series_id:<4} {s.year_group:<3} {s.start_date:<10} "
              f"{s.end_date:<10} {s.status:<10} {s.name[:40]:<40}")


def _print_papers(rows: list[data.MockPaper]) -> None:
    if not rows:
        print("  (no papers)")
        return
    print(f"  {'ID':<4} {'Date':<10} {'Subj':<6} {'Paper':<28} "
          f"{'Tier':<11} {'Max':<6}")
    print(f"  {'-'*4} {'-'*10} {'-'*6} {'-'*28} {'-'*11} {'-'*6}")
    for p in rows:
        print(f"  {p.paper_id:<4} {p.paper_date:<10} "
              f"{(p.subject_code or '?'):<6} {p.paper_name[:28]:<28} "
              f"{p.tier:<11} {p.max_marks:<6g}")


def _print_results(rows: list[data.MockResult]) -> None:
    if not rows:
        print("  (no results)")
        return
    print(f"  {'ID':<4} {'Pupil':<10} {'Yr':<3} {'Marks':<10} "
          f"{'%':<5} {'Grade':<5} {'Abs':<3}")
    print(f"  {'-'*4} {'-'*10} {'-'*3} {'-'*10} {'-'*5} {'-'*5} {'-'*3}")
    for r in rows:
        marks = ("ABS" if r.absent
                 else ("-" if r.marks_awarded is None
                        else (f"{r.marks_awarded:g}/{r.paper_max:g}"
                               if r.paper_max else f"{r.marks_awarded:g}")))
        print(f"  {r.result_id:<4} {r.pupil_id:<10} "
              f"{(r.pupil_year or '-'):<3} {marks:<10} "
              f"{(f'{r.mark_pct:.0f}' if r.mark_pct is not None else '-'):<5} "
              f"{(r.grade or '-'):<5} "
              f"{('Y' if r.absent else 'N'):<3}")


@_safe
def open_mock_exams() -> None:
    logger.debug("CLI: open_mock_exams")
    while True:
        print("\n  ── Mock Exams ──")
        print("  Series")
        print("    1) New series")
        print("    2) List series")
        print("    3) Edit series")
        print("    4) Set series status")
        print("    5) Delete series")
        print("  Papers")
        print("    6) Add paper")
        print("    7) List papers in series")
        print("    8) Edit paper")
        print("    9) Delete paper")
        print("    10) Paper summary stats")
        print("  Results")
        print("   11) Record / update result")
        print("   12) List results for paper")
        print("   13) Pupil mock history")
        print("   14) Delete result")
        print("    0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _new_series, "2": _list_series, "3": _edit_series,
            "4": _set_status, "5": _delete_series,
            "6": _new_paper, "7": _list_papers, "8": _edit_paper,
            "9": _delete_paper, "10": _summary,
            "11": _upsert_result, "12": _list_results,
            "13": _pupil_history, "14": _delete_result,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect_series(existing: data.MockSeries | None = None
                     ) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")
    f: dict[str, Any] = {}
    f["name"] = ask("Name", existing.name if existing else None)
    f["year_group"] = ask(f"Year ({'/'.join(YEAR_GROUPS)})",
                           existing.year_group if existing else None)
    f["start_date"] = ask("Start date (YYYY-MM-DD)",
                           existing.start_date if existing else None)
    f["end_date"]   = ask("End date (YYYY-MM-DD)",
                           existing.end_date if existing else None)
    f["status"]     = ask(f"Status ({'/'.join(SERIES_STATUSES)})",
                           existing.status if existing else "Planned")
    f["notes"]      = ask("Notes",
                           existing.notes if existing else None)
    return f


@_safe
def _new_series() -> None:
    print("\n  ── New Mock Series ──")
    fields = _collect_series()
    s = data.create_series(fields)
    print(f"  Created series #{s.series_id} {s.name}")


@_safe
def _list_series() -> None:
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    status = _prompt(
        f"  Status ({'/'.join(SERIES_STATUSES)}, blank): ") or None
    rows = data.list_series(year_group=yg, status=status)
    print(f"\n  {len(rows)} series:")
    _print_series(rows)
    _prompt("\n  Press Enter to continue...")


def _ask_id(label: str) -> int | None:
    raw = _prompt(f"  {label}: ")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        print(f"  {label} must be a number.")
        return None


@_safe
def _edit_series() -> None:
    sid = _ask_id("Series ID")
    if sid is None:
        return
    existing = data.get_series(sid)
    if existing is None:
        print("  No series with that ID.")
        return
    print("  Press Enter to keep existing value.")
    fields = _collect_series(existing)
    s = data.update_series(sid, fields)
    print(f"  Updated series #{s.series_id} (status {s.status})")


@_safe
def _set_status() -> None:
    sid = _ask_id("Series ID")
    if sid is None:
        return
    s = data.get_series(sid)
    if s is None:
        print("  No series with that ID.")
        return
    print(f"  Current: {s.status}")
    print(f"  Allowed: {', '.join(SERIES_STATUSES)}")
    new = _prompt("  New status: ")
    if not new:
        return
    s = data.set_series_status(sid, new)
    print(f"  Status now: {s.status}")


@_safe
def _delete_series() -> None:
    sid = _ask_id("Series ID")
    if sid is None:
        return
    s = data.get_series(sid)
    if s is None:
        print("  No series with that ID.")
        return
    confirm = _prompt(
        f"  Delete '{s.name}' and ALL its papers + results? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete_series(sid)
    print(f"  Deleted series #{sid}.")


def _collect_paper(existing: data.MockPaper | None = None,
                    *, series_id: int | None = None) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")
    f: dict[str, Any] = {}
    f["series_id"] = (existing.series_id if existing
                      else (series_id if series_id is not None
                             else int(ask("Series ID", None) or 0)))
    if not existing:
        print("  Active subjects:")
        for s in subjects_data.list_all(active_only=True)[:30]:
            print(f"    #{s.subject_id:<4} {s.code:<8} {s.name}")
    f["subject_id"] = ask("Subject ID",
                           existing.subject_id if existing else None)
    f["paper_name"] = ask("Paper name (e.g. Paper 1)",
                           existing.paper_name if existing else None)
    f["paper_date"] = ask("Paper date (YYYY-MM-DD)",
                           existing.paper_date if existing else None)
    f["max_marks"]  = ask("Max marks",
                           existing.max_marks if existing else None)
    f["tier"]       = ask(f"Tier ({'/'.join(PAPER_TIERS)})",
                           existing.tier if existing else "N/A")
    f["grade_boundaries"] = ask(
        "Grade boundaries (free text)",
        existing.grade_boundaries if existing else None)
    f["notes"]      = ask("Notes",
                           existing.notes if existing else None)
    return f


@_safe
def _new_paper() -> None:
    sid = _ask_id("Series ID")
    if sid is None:
        return
    if data.get_series(sid) is None:
        print("  No series with that ID.")
        return
    fields = _collect_paper(series_id=sid)
    p = data.create_paper(fields)
    print(f"  Created paper #{p.paper_id} {p.paper_name} "
          f"(subject {p.subject_code}, max {p.max_marks})")


@_safe
def _list_papers() -> None:
    sid = _ask_id("Series ID")
    if sid is None:
        return
    if data.get_series(sid) is None:
        print("  No series with that ID.")
        return
    rows = data.list_papers(sid)
    print(f"\n  {len(rows)} paper(s):")
    _print_papers(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _edit_paper() -> None:
    pid = _ask_id("Paper ID")
    if pid is None:
        return
    existing = data.get_paper(pid)
    if existing is None:
        print("  No paper with that ID.")
        return
    print("  Press Enter to keep existing value.")
    fields = _collect_paper(existing)
    p = data.update_paper(pid, fields)
    print(f"  Updated paper #{p.paper_id}")


@_safe
def _delete_paper() -> None:
    pid = _ask_id("Paper ID")
    if pid is None:
        return
    p = data.get_paper(pid)
    if p is None:
        print("  No paper with that ID.")
        return
    confirm = _prompt(
        f"  Delete paper '{p.paper_name}' and ALL its results? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete_paper(pid)
    print(f"  Deleted paper #{pid}.")


@_safe
def _upsert_result() -> None:
    pid = _ask_id("Paper ID")
    if pid is None:
        return
    pupil = _prompt("  Pupil ID: ")
    if not pupil:
        return
    absent = _prompt("  Absent? (y/N): ").lower().startswith("y")
    marks = None
    grade = None
    if not absent:
        marks = _prompt("  Marks awarded (blank if grade-only): ") or None
        grade = _prompt("  Grade (blank ok): ") or None
    notes = _prompt("  Notes (blank ok): ") or None
    r = data.upsert_result(pid, {
        "pupil_id": pupil, "marks_awarded": marks,
        "grade": grade, "absent": absent, "notes": notes,
    })
    print(f"  Saved result #{r.result_id}: pupil {r.pupil_id} "
          f"marks={r.marks_awarded} pct={r.mark_pct} "
          f"grade={r.grade or '-'} absent={r.absent}")


@_safe
def _list_results() -> None:
    pid = _ask_id("Paper ID")
    if pid is None:
        return
    p = data.get_paper(pid)
    if p is None:
        print("  No paper with that ID.")
        return
    rows = data.list_results(pid)
    print(f"\n  {len(rows)} result(s) for '{p.paper_name}':")
    _print_results(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _pupil_history() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    rows = data.results_for_pupil(pid)
    print(f"\n  {len(rows)} mock result(s) for {pid}:")
    _print_results(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete_result() -> None:
    rid = _ask_id("Result ID")
    if rid is None:
        return
    r = data.get_result(rid)
    if r is None:
        print("  No result with that ID.")
        return
    confirm = _prompt(
        f"  Delete result #{rid} ({r.pupil_id} on {r.paper_name})? "
        f"(y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete_result(rid)
    print(f"  Deleted result #{rid}.")


@_safe
def _summary() -> None:
    pid = _ask_id("Paper ID")
    if pid is None:
        return
    s = data.paper_summary(pid)
    p = s["paper"]
    print(f"\n  ── Summary: {p.paper_name} "
          f"({p.subject_code}, {p.paper_date}, max {p.max_marks}) ──")
    print(f"  Results: {s['count']}    Absent: {s['absent']}    "
          f"Avg %: {s['avg_pct'] if s['avg_pct'] is not None else '-'}    "
          f"Min %: {s['min_pct'] if s['min_pct'] is not None else '-'}    "
          f"Max %: {s['max_pct'] if s['max_pct'] is not None else '-'}")
    if s["grades"]:
        print("  Grades: "
              + "   ".join(f"{k}: {v}"
                            for k, v in sorted(s["grades"].items())))
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"Mock Exams": open_mock_exams}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching mock_exams CLI label: %s", label)
    handler()
    return True
