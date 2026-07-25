"""CLI handlers for the gradebook."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.systems.secondary.domain.assessment.gradebook import (
    gradebook as data,
)
from education_system.systems.secondary.domain.assessment.gradebook.gradebook import (
    ASSESSMENT_TYPES, TERMS,
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


def _print_entries(rows: list[data.GradebookEntry]) -> None:
    if not rows:
        print("  (no entries)")
        return
    print(f"  {'ID':<5} {'Date':<10} {'Pupil':<10} {'Subj':<6} "
          f"{'Term':<7} {'Type':<10} {'Assessment':<22} "
          f"{'Marks':<8} {'%':<5} {'Grade':<5}")
    print(f"  {'-'*5} {'-'*10} {'-'*10} {'-'*6} {'-'*7} {'-'*10} {'-'*22} "
          f"{'-'*8} {'-'*5} {'-'*5}")
    for e in rows:
        marks = ("-" if e.marks_awarded is None
                 else (f"{e.marks_awarded:g}/{e.max_marks:g}"
                        if e.max_marks else f"{e.marks_awarded:g}"))
        pct = f"{e.mark_pct:.0f}" if e.mark_pct is not None else "-"
        print(f"  {e.entry_id:<5} {e.assessment_date:<10} "
              f"{e.pupil_id:<10} {(e.subject_code or '?'):<6} "
              f"{e.term:<7} {e.assessment_type[:10]:<10} "
              f"{e.assessment_name[:22]:<22} {marks:<8} {pct:<5} "
              f"{(e.grade or '-'):<5}")


@_safe
def open_gradebook() -> None:
    logger.debug("CLI: open_gradebook")
    while True:
        print("\n  ── Gradebook ──")
        print("   1) Record / update entry")
        print("   2) List entries")
        print("   3) Pupil / subject summary")
        print("   4) Cohort assessment summary")
        print("   5) Delete entry")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _upsert, "2": _list, "3": _pupil_summary,
            "4": _cohort_summary, "5": _delete,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect(existing: data.GradebookEntry | None = None) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")

    f: dict[str, Any] = {}
    f["pupil_id"] = ask("Pupil ID",
                         existing.pupil_id if existing else None)
    if not existing:
        print("  Active subjects:")
        for s in subjects_data.list_all(active_only=True)[:20]:
            print(f"    #{s.subject_id:<4} {s.code:<8} {s.name}")
    f["subject_id"]      = ask("Subject ID",
                                existing.subject_id if existing else None)
    f["assessment_name"] = ask("Assessment name",
                                existing.assessment_name if existing
                                else None)
    f["assessment_type"] = ask(f"Type ({'/'.join(ASSESSMENT_TYPES)})",
                                existing.assessment_type if existing
                                else "Test")
    f["term"]            = ask(f"Term ({'/'.join(TERMS)})",
                                existing.term if existing else "Autumn")
    f["assessment_date"] = ask("Date (YYYY-MM-DD, blank = today)",
                                existing.assessment_date if existing
                                else None)
    f["marks_awarded"]   = ask("Marks awarded (blank ok)",
                                existing.marks_awarded if existing
                                else None)
    f["max_marks"]       = ask("Max marks (blank ok)",
                                existing.max_marks if existing else None)
    f["grade"]           = ask("Grade (blank ok)",
                                existing.grade if existing else None)
    f["teacher"]         = ask("Teacher",
                                existing.teacher if existing else None)
    f["comments"]        = ask("Comments",
                                existing.comments if existing else None)
    return f


@_safe
def _upsert() -> None:
    print("\n  ── Record / Update Gradebook Entry ──")
    fields = _collect()
    e = data.upsert_entry(fields)
    print(f"  Saved entry #{e.entry_id}: {e.pupil_id} / "
          f"{e.subject_code} — {e.assessment_name} "
          f"({e.marks_awarded if e.marks_awarded is not None else '-'}/"
          f"{e.max_marks if e.max_marks else '-'} = "
          f"{e.mark_pct if e.mark_pct is not None else '-'}%, "
          f"grade={e.grade or '-'})")


@_safe
def _list() -> None:
    pid = _prompt("  Pupil ID (blank): ") or None
    sid_raw = _prompt("  Subject ID (blank): ")
    sid = None
    if sid_raw:
        try:
            sid = int(sid_raw)
        except ValueError:
            print("  Subject ID must be a number.")
            return
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    term = _prompt(f"  Term ({'/'.join(TERMS)}, blank): ") or None
    atype = _prompt(
        f"  Type ({'/'.join(ASSESSMENT_TYPES)}, blank): ") or None
    df = _prompt("  From date (blank): ") or None
    dt = _prompt("  To date (blank): ") or None
    rows = data.list_entries(pupil_id=pid, subject_id=sid,
                              year_group=yg, term=term,
                              assessment_type=atype,
                              date_from=df, date_to=dt)
    print(f"\n  {len(rows)} entry(ies):")
    _print_entries(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _pupil_summary() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    sid_raw = _prompt("  Subject ID: ")
    if not sid_raw:
        return
    try:
        sid = int(sid_raw)
    except ValueError:
        print("  Subject ID must be a number.")
        return
    s = data.pupil_subject_summary(pid, sid)
    print(f"\n  ── {pid} / subject #{sid} ──")
    print(f"  Entries: {s['count']}    "
          f"Avg %: {s['avg_pct'] if s['avg_pct'] is not None else '-'}    "
          f"Latest grade: {s['latest_grade'] or '-'}")
    print("  By term: "
          + "   ".join(f"{k}: {v}" for k, v in s["by_term"].items()))
    _print_entries(s["entries"])
    _prompt("\n  Press Enter to continue...")


@_safe
def _cohort_summary() -> None:
    sid_raw = _prompt("  Subject ID: ")
    if not sid_raw:
        return
    try:
        sid = int(sid_raw)
    except ValueError:
        print("  Subject ID must be a number.")
        return
    name = _prompt("  Assessment name: ")
    if not name:
        return
    date = _prompt("  Assessment date (YYYY-MM-DD): ")
    if not date:
        return
    s = data.assessment_summary(sid, name, date)
    print(f"\n  ── {name} ({date}) ──")
    print(f"  Pupils: {s['count']}    "
          f"Avg %: {s['avg_pct'] if s['avg_pct'] is not None else '-'}    "
          f"Min %: {s['min_pct'] if s['min_pct'] is not None else '-'}    "
          f"Max %: {s['max_pct'] if s['max_pct'] is not None else '-'}")
    if s["grades"]:
        print("  Grades: "
              + "   ".join(f"{k}: {v}"
                            for k, v in sorted(s["grades"].items())))
    _print_entries(s["entries"])
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    raw = _prompt("  Entry ID: ")
    if not raw:
        return
    try:
        eid = int(raw)
    except ValueError:
        print("  Entry ID must be a number.")
        return
    e = data.get_entry(eid)
    if e is None:
        print("  No entry with that ID.")
        return
    confirm = _prompt(
        f"  Delete entry #{eid} ({e.pupil_id} — {e.assessment_name})? "
        f"(y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete_entry(eid)
    print(f"  Deleted entry #{eid}.")


_DISPATCH = {"Gradebook": open_gradebook}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching gradebook CLI label: %s", label)
    handler()
    return True
