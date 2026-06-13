"""CLI handlers for homework assignments and submissions."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.secondarysch_system.modules.domain.academics.homework import (
    homework as data,
)
from education_system.secondarysch_system.modules.domain.academics.homework.homework import (
    ASSIGNMENT_STATUSES, SUBMISSION_STATUSES,
)
from education_system.secondarysch_system.modules.domain.academics.subjects import (
    subjects as subjects_data,
)
from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
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


def _print_assignments(rows: list[data.Assignment]) -> None:
    if not rows:
        print("  (no assignments)")
        return
    print(f"  {'ID':<4} {'Due':<10} {'Yr':<3} {'Form':<5} "
          f"{'Subj':<6} {'Title':<32} {'By':<14} {'Pts':<4} {'Status':<8}")
    print(f"  {'-'*4} {'-'*10} {'-'*3} {'-'*5} {'-'*6} {'-'*32} {'-'*14} "
          f"{'-'*4} {'-'*8}")
    for a in rows:
        print(f"  {a.assignment_id:<4} {a.due_date:<10} {a.year_group:<3} "
              f"{(a.form_group or '-'):<5} "
              f"{(a.subject_code or '?'):<6} {a.title[:32]:<32} "
              f"{(a.set_by or '-')[:14]:<14} "
              f"{(str(a.points) if a.points is not None else '-'):<4} "
              f"{a.status:<8}")


def _print_submissions(rows: list[data.Submission]) -> None:
    if not rows:
        print("  (no submissions)")
        return
    print(f"  {'ID':<5} {'Pupil':<12} {'Submitted':<10} {'Status':<10} "
          f"{'Grade':<8} {'%':<5} {'Feedback':<24}")
    print(f"  {'-'*5} {'-'*12} {'-'*10} {'-'*10} {'-'*8} {'-'*5} {'-'*24}")
    for s in rows:
        print(f"  {s.submission_id:<5} {s.pupil_id:<12} "
              f"{(s.submitted_date or '-'):<10} {s.status:<10} "
              f"{(s.grade or '-'):<8} "
              f"{(f'{s.mark_pct:.0f}' if s.mark_pct is not None else '-'):<5} "
              f"{(s.feedback or '-')[:24]:<24}")


@_safe
def open_homework() -> None:
    logger.debug("CLI: open_homework")
    while True:
        counts = data.assignment_status_counts()
        total = sum(counts.values())
        print("\n  ── Homework ──")
        print(f"  Assignments: {total}   "
              + "   ".join(f"{s}: {counts[s]}" for s in ASSIGNMENT_STATUSES))
        print("\n   1) New assignment")
        print("   2) List assignments")
        print("   3) View assignment")
        print("   4) Edit assignment")
        print("   5) Set assignment status")
        print("   6) Seed submissions (auto-add pupils)")
        print("   7) Record / update a submission")
        print("   8) List submissions for an assignment")
        print("   9) Pupil submission history")
        print("  10) Submission summary")
        print("  11) Delete a submission")
        print("  12) Delete assignment")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _new_assignment,
            "2": _list_assignments,
            "3": _view_assignment,
            "4": _edit_assignment,
            "5": _set_assignment_status,
            "6": _seed_submissions,
            "7": _upsert_submission,
            "8": _list_submissions,
            "9": _pupil_history,
            "10": _summary,
            "11": _delete_submission,
            "12": _delete_assignment,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect_assignment(existing: data.Assignment | None = None
                        ) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")

    f: dict[str, Any] = {}
    f["title"] = ask("Title", existing.title if existing else None)
    if not existing:
        print("  Active subjects:")
        for s in subjects_data.list_all(active_only=True)[:30]:
            print(f"    #{s.subject_id:<4} {s.code:<8} {s.name}")
    f["subject_id"] = ask("Subject ID",
                          existing.subject_id if existing else None)
    f["year_group"] = ask(f"Year ({'/'.join(YEAR_GROUPS)})",
                           existing.year_group if existing else None)
    f["form_group"] = ask("Form (blank = whole year)",
                           existing.form_group if existing else None)
    f["set_by"]     = ask("Set by (teacher)",
                           existing.set_by if existing else None)
    f["set_date"]   = ask("Set date (YYYY-MM-DD)",
                           existing.set_date if existing else None)
    f["due_date"]   = ask("Due date (YYYY-MM-DD)",
                           existing.due_date if existing else None)
    f["points"]     = ask("Points (blank ok)",
                           existing.points if existing else None)
    f["status"]     = ask(f"Status ({'/'.join(ASSIGNMENT_STATUSES)})",
                           existing.status if existing else "Draft")
    f["instructions"] = ask("Instructions",
                             existing.instructions if existing else None)
    f["notes"]      = ask("Notes",
                           existing.notes if existing else None)
    return f


@_safe
def _new_assignment() -> None:
    print("\n  ── New Assignment ──")
    fields = _collect_assignment()
    a = data.create_assignment(fields)
    print(f"  Created assignment #{a.assignment_id} '{a.title}' "
          f"(Yr{a.year_group}, due {a.due_date})")


@_safe
def _list_assignments() -> None:
    print(f"\n  Filter — year ({'/'.join(YEAR_GROUPS)}), blank for all.")
    yg = _prompt("  Year: ") or None
    print(f"  Status ({'/'.join(ASSIGNMENT_STATUSES)}), blank for all.")
    status = _prompt("  Status: ") or None
    teacher = _prompt("  Teacher (blank): ") or None
    rows = data.list_assignments(year_group=yg, status=status,
                                  teacher=teacher)
    print(f"\n  {len(rows)} assignment(s):")
    _print_assignments(rows)
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
def _view_assignment() -> None:
    aid = _ask_id("Assignment ID")
    if aid is None:
        return
    a = data.get_assignment(aid)
    if a is None:
        print("  No assignment with that ID.")
        return
    print(f"\n  ── Assignment #{a.assignment_id} ──")
    print(f"  Title:        {a.title}")
    print(f"  Subject:      {a.subject_code} — {a.subject_name}")
    print(f"  Year/form:    {a.year_group}"
          f"{('/' + a.form_group) if a.form_group else ''}")
    print(f"  Set by:       {a.set_by or '-'}")
    print(f"  Set / due:    {a.set_date}  →  {a.due_date}")
    print(f"  Points:       {a.points if a.points is not None else '-'}")
    print(f"  Status:       {a.status}")
    print(f"  Instructions: {a.instructions or '-'}")
    print(f"  Notes:        {a.notes or '-'}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _edit_assignment() -> None:
    aid = _ask_id("Assignment ID")
    if aid is None:
        return
    existing = data.get_assignment(aid)
    if existing is None:
        print("  No assignment with that ID.")
        return
    print("  Press Enter to keep existing value.")
    fields = _collect_assignment(existing)
    a = data.update_assignment(aid, fields)
    print(f"  Updated assignment #{a.assignment_id} (status {a.status})")


@_safe
def _set_assignment_status() -> None:
    aid = _ask_id("Assignment ID")
    if aid is None:
        return
    a = data.get_assignment(aid)
    if a is None:
        print("  No assignment with that ID.")
        return
    print(f"  Current: {a.status}")
    print(f"  Allowed: {', '.join(ASSIGNMENT_STATUSES)}")
    new = _prompt("  New status: ")
    if not new:
        return
    a = data.set_assignment_status(aid, new)
    print(f"  Status now: {a.status}")


@_safe
def _seed_submissions() -> None:
    aid = _ask_id("Assignment ID")
    if aid is None:
        return
    added = data.seed_submissions(aid)
    print(f"  Added {added} new submission row(s).")


@_safe
def _upsert_submission() -> None:
    aid = _ask_id("Assignment ID")
    if aid is None:
        return
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    print(f"  Status ({'/'.join(SUBMISSION_STATUSES)}):")
    status = _prompt("  Status: ") or "Pending"
    sub_date = _prompt("  Submitted date (YYYY-MM-DD, blank ok): ") or None
    grade = _prompt("  Grade (blank ok): ") or None
    mark = _prompt("  Mark % (0-100, blank ok): ") or None
    feedback = _prompt("  Feedback (blank ok): ") or None
    s = data.upsert_submission(aid, {
        "pupil_id": pid,
        "status": status,
        "submitted_date": sub_date,
        "grade": grade,
        "mark_pct": mark,
        "feedback": feedback,
    })
    print(f"  Saved submission #{s.submission_id}: {s.pupil_id} "
          f"= {s.status}{(' (' + s.grade + ')') if s.grade else ''}")


@_safe
def _list_submissions() -> None:
    aid = _ask_id("Assignment ID")
    if aid is None:
        return
    a = data.get_assignment(aid)
    if a is None:
        print("  No assignment with that ID.")
        return
    rows = data.list_submissions(aid)
    print(f"\n  Submissions for '{a.title}' ({len(rows)}):")
    _print_submissions(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _pupil_history() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    print(f"  Status ({'/'.join(SUBMISSION_STATUSES)}) or blank.")
    status = _prompt("  Status: ") or None
    rows = data.list_for_pupil(pid, status=status)
    print(f"\n  {len(rows)} submission(s) for {pid}:")
    _print_submissions(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _summary() -> None:
    aid = _ask_id("Assignment ID")
    if aid is None:
        return
    s = data.submission_summary(aid)
    a = s["assignment"]
    print(f"\n  ── Summary: {a.title} (Yr{a.year_group}, due {a.due_date}) ──")
    print(f"  Total submissions: {s['total']}    "
          f"Marked: {s['marked']}    "
          f"Avg %: {s['avg_mark_pct'] if s['avg_mark_pct'] is not None else '-'}")
    print("  By status:  "
          + "   ".join(f"{k}: {v}" for k, v in s["by_status"].items()))
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete_submission() -> None:
    sid = _ask_id("Submission ID")
    if sid is None:
        return
    s = data.get_submission(sid)
    if s is None:
        print("  No submission with that ID.")
        return
    confirm = _prompt(
        f"  Delete submission #{sid} ({s.pupil_id} on "
        f"assignment #{s.assignment_id})? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_submission(sid):
        print(f"  Deleted submission #{sid}.")


@_safe
def _delete_assignment() -> None:
    aid = _ask_id("Assignment ID")
    if aid is None:
        return
    a = data.get_assignment(aid)
    if a is None:
        print("  No assignment with that ID.")
        return
    confirm = _prompt(
        f"  Delete assignment #{aid} '{a.title}' and ALL submissions? "
        f"(y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_assignment(aid):
        print(f"  Deleted assignment #{aid}.")


_DISPATCH = {"Homework": open_homework}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching homework CLI label: %s", label)
    handler()
    return True
