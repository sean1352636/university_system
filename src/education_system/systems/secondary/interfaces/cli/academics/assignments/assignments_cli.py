"""CLI handlers for assessed assignments."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.systems.secondary.domain.academics.assignments import (
    assignments as data,
)
from education_system.systems.secondary.domain.academics.assignments.assignments import (
    ASSIGNMENT_TYPES, ASSIGNMENT_STATUSES, SUBMISSION_STATUSES,
    MODERATION_STATUSES,
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


def _print_assignments(rows: list[data.Assignment]) -> None:
    if not rows:
        print("  (no assignments)")
        return
    print(f"  {'ID':<4} {'Due':<10} {'Yr':<3} {'Subj':<6} {'Type':<12} "
          f"{'Title':<28} {'Max':<5} {'W%':<5} {'Status':<11}")
    print(f"  {'-'*4} {'-'*10} {'-'*3} {'-'*6} {'-'*12} {'-'*28} "
          f"{'-'*5} {'-'*5} {'-'*11}")
    for a in rows:
        print(f"  {a.assignment_id:<4} {a.due_date:<10} {a.year_group:<3} "
              f"{(a.subject_code or '?'):<6} {a.type[:12]:<12} "
              f"{a.title[:28]:<28} "
              f"{(str(int(a.max_marks)) if a.max_marks else '-'):<5} "
              f"{(f'{a.weight_pct:.0f}' if a.weight_pct else '-'):<5} "
              f"{a.status:<11}")


def _print_submissions(rows: list[data.AssignmentSubmission],
                        max_marks: float | None) -> None:
    if not rows:
        print("  (no submissions)")
        return
    print(f"  {'ID':<5} {'Pupil':<12} {'Sub':<10} {'Status':<10} "
          f"{'Marks':<7} {'%':<5} {'Grade':<6} {'Mod':<14}")
    print(f"  {'-'*5} {'-'*12} {'-'*10} {'-'*10} {'-'*7} {'-'*5} "
          f"{'-'*6} {'-'*14}")
    for s in rows:
        pct = s.mark_pct(max_marks)
        print(f"  {s.submission_id:<5} {s.pupil_id:<12} "
              f"{(s.submitted_date or '-'):<10} {s.status:<10} "
              f"{(str(s.marks_awarded) if s.marks_awarded is not None else '-'):<7} "
              f"{(f'{pct:.0f}' if pct is not None else '-'):<5} "
              f"{(s.grade or '-'):<6} "
              f"{(s.moderation_status or '-')[:14]:<14}")


@_safe
def open_assignments() -> None:
    logger.debug("CLI: open_assignments")
    while True:
        counts = data.status_counts()
        total = sum(counts.values())
        print("\n  ── Assignments ──")
        print(f"  Total: {total}   "
              + "   ".join(f"{s}: {counts[s]}" for s in ASSIGNMENT_STATUSES))
        print("\n   1) New assignment")
        print("   2) List assignments")
        print("   3) View assignment")
        print("   4) Edit assignment")
        print("   5) Set assignment status")
        print("   6) Seed submissions")
        print("   7) Record / mark a submission")
        print("   8) List submissions")
        print("   9) Submission summary")
        print("  10) Delete submission")
        print("  11) Delete assignment")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _new, "2": _list, "3": _view, "4": _edit,
            "5": _set_status, "6": _seed, "7": _upsert_sub,
            "8": _list_subs, "9": _summary,
            "10": _delete_sub, "11": _delete,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect(existing: data.Assignment | None = None) -> dict[str, Any]:
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
    f["type"]       = ask(f"Type ({'/'.join(ASSIGNMENT_TYPES)})",
                           existing.type if existing else "Coursework")
    f["weight_pct"] = ask("Weight % (0-100, blank ok)",
                           existing.weight_pct if existing else None)
    f["max_marks"]  = ask("Max marks (blank ok)",
                           existing.max_marks if existing else None)
    f["set_date"]   = ask("Set date (YYYY-MM-DD)",
                           existing.set_date if existing else None)
    f["due_date"]   = ask("Due date (YYYY-MM-DD)",
                           existing.due_date if existing else None)
    f["set_by"]     = ask("Set by",
                           existing.set_by if existing else None)
    f["status"]     = ask(f"Status ({'/'.join(ASSIGNMENT_STATUSES)})",
                           existing.status if existing else "Draft")
    f["description"] = ask("Description",
                            existing.description if existing else None)
    f["criteria"]   = ask("Criteria",
                           existing.criteria if existing else None)
    f["notes"]      = ask("Notes",
                           existing.notes if existing else None)
    return f


@_safe
def _new() -> None:
    print("\n  ── New Assignment ──")
    fields = _collect()
    a = data.create_assignment(fields)
    print(f"  Created #{a.assignment_id} {a.title} ({a.type}, "
          f"Yr{a.year_group}, due {a.due_date})")


@_safe
def _list() -> None:
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank for all): ") or None
    status = _prompt(f"  Status ({'/'.join(ASSIGNMENT_STATUSES)}, blank for all): ") or None
    atype = _prompt(f"  Type ({'/'.join(ASSIGNMENT_TYPES)}, blank for all): ") or None
    rows = data.list_assignments(year_group=yg, status=status, type=atype)
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
def _view() -> None:
    aid = _ask_id("Assignment ID")
    if aid is None:
        return
    a = data.get_assignment(aid)
    if a is None:
        print("  No assignment with that ID.")
        return
    print(f"\n  ── Assignment #{a.assignment_id} ──")
    print(f"  Title:      {a.title}")
    print(f"  Subject:    {a.subject_code} — {a.subject_name}")
    print(f"  Year/form:  {a.year_group}"
          f"{('/' + a.form_group) if a.form_group else ''}")
    print(f"  Type:       {a.type}")
    print(f"  Weight %:   {a.weight_pct if a.weight_pct is not None else '-'}")
    print(f"  Max marks:  {a.max_marks if a.max_marks is not None else '-'}")
    print(f"  Set / due:  {a.set_date}  →  {a.due_date}")
    print(f"  Set by:     {a.set_by or '-'}")
    print(f"  Status:     {a.status}")
    print(f"\n  Description:\n    {a.description or '-'}")
    print(f"\n  Criteria:\n    {a.criteria or '-'}")
    print(f"\n  Notes:\n    {a.notes or '-'}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _edit() -> None:
    aid = _ask_id("Assignment ID")
    if aid is None:
        return
    existing = data.get_assignment(aid)
    if existing is None:
        print("  No assignment with that ID.")
        return
    print("  Press Enter to keep existing value.")
    fields = _collect(existing)
    a = data.update_assignment(aid, fields)
    print(f"  Updated #{a.assignment_id} (status {a.status})")


@_safe
def _set_status() -> None:
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
    a = data.set_status(aid, new)
    print(f"  Status now: {a.status}")


@_safe
def _seed() -> None:
    aid = _ask_id("Assignment ID")
    if aid is None:
        return
    print(f"  Added {data.seed_submissions(aid)} row(s).")


@_safe
def _upsert_sub() -> None:
    aid = _ask_id("Assignment ID")
    if aid is None:
        return
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    fields: dict[str, Any] = {"pupil_id": pid}
    fields["status"] = _prompt(
        f"  Status ({'/'.join(SUBMISSION_STATUSES)}): ") or "Pending"
    fields["submitted_date"] = _prompt(
        "  Submitted date (YYYY-MM-DD, blank ok): ") or None
    fields["marks_awarded"] = _prompt(
        "  Marks awarded (blank ok): ") or None
    fields["grade"] = _prompt("  Grade (blank ok): ") or None
    fields["moderation_status"] = _prompt(
        f"  Moderation ({'/'.join(MODERATION_STATUSES)}, blank ok): "
    ) or None
    fields["moderator"] = _prompt("  Moderator (blank ok): ") or None
    fields["feedback"] = _prompt("  Feedback (blank ok): ") or None
    s = data.upsert_submission(aid, fields)
    print(f"  Saved submission #{s.submission_id}: {s.pupil_id} "
          f"= {s.status} marks={s.marks_awarded}")


@_safe
def _list_subs() -> None:
    aid = _ask_id("Assignment ID")
    if aid is None:
        return
    a = data.get_assignment(aid)
    if a is None:
        print("  No assignment with that ID.")
        return
    rows = data.list_submissions(aid)
    print(f"\n  {len(rows)} submission(s) for '{a.title}':")
    _print_submissions(rows, a.max_marks)
    _prompt("\n  Press Enter to continue...")


@_safe
def _summary() -> None:
    aid = _ask_id("Assignment ID")
    if aid is None:
        return
    s = data.submission_summary(aid)
    a = s["assignment"]
    print(f"\n  ── Summary: {a.title} (Yr{a.year_group}, "
          f"max {a.max_marks or '-'}) ──")
    print(f"  Total submissions: {s['total']}    "
          f"Marked: {s['marked']}    "
          f"Avg marks: {s['avg_marks'] if s['avg_marks'] is not None else '-'}    "
          f"Avg %: {s['avg_pct'] if s['avg_pct'] is not None else '-'}")
    print("  By status: "
          + "   ".join(f"{k}: {v}" for k, v in s["by_status"].items()))
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete_sub() -> None:
    sid = _ask_id("Submission ID")
    if sid is None:
        return
    s = data.get_submission(sid)
    if s is None:
        print("  No submission with that ID.")
        return
    confirm = _prompt(
        f"  Delete submission #{sid} ({s.pupil_id})? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete_submission(sid)
    print(f"  Deleted submission #{sid}.")


@_safe
def _delete() -> None:
    aid = _ask_id("Assignment ID")
    if aid is None:
        return
    a = data.get_assignment(aid)
    if a is None:
        print("  No assignment with that ID.")
        return
    confirm = _prompt(
        f"  Delete '{a.title}' and all submissions? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete_assignment(aid)
    print(f"  Deleted assignment #{aid}.")


_DISPATCH = {"Assignments": open_assignments}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching assignments CLI label: %s", label)
    handler()
    return True
