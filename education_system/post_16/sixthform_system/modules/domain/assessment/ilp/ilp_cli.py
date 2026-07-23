"""CLI flows for Sixth Form ILP (Individual Learning Plans)."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.post_16.sixthform_system.modules.domain.assessment.ilp import (
    ilp as data,
)
from education_system.post_16.sixthform_system.modules.domain.students.students import (
    students as student_data,
)
from education_system.post_16.sixthform_system.modules.domain.assessment.ilp.ilp import (
    DEFAULT_GOAL_CATEGORY,
    DEFAULT_GOAL_STATUS,
    DEFAULT_PLAN_STATUS,
    DEFAULT_PLAN_TYPE,
    DEFAULT_REVIEW_FREQUENCY,
    GOAL_CATEGORIES,
    GOAL_STATUSES,
    Goal,
    PLAN_STATUSES,
    PLAN_TYPES,
    PROGRESS_TAGS,
    Plan,
    REVIEW_FREQUENCIES,
    Review,
    ValidationError,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


# ── Prompt helpers ─────────────────────────────────────────────────

def _input(prompt: str, *, default: str = "",
            allow_empty: bool = True) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    s = raw.strip()
    if s.lower() == "cancel":
        raise _UserAbort
    if not s:
        if default:
            return default
        if not allow_empty:
            print("    Value is required.")
            return _input(prompt, default=default, allow_empty=False)
        return ""
    return s


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _multiline(prompt: str, *, default: str = "") -> str:
    print(f"\n  {prompt} (end with '.' on its own line; "
          f"ENTER for default)")
    if default:
        for line in default.splitlines():
            print(f"    | {line}")
    lines: list[str] = []
    try:
        while True:
            ln = input("  > ")
            if ln.strip() == ".":
                break
            if not lines and not ln:
                return default
            lines.append(ln)
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    return "\n".join(lines)


def _pick_from(label: str, options: list[str],
                default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}",
                      default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number (or 'cancel' to abort).")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _pick_student() -> str:
    rows = student_data.list_students()
    if not rows:
        print("    No students.")
        raise _UserAbort
    print("\n  Students:")
    for i, s in enumerate(rows, 1):
        print(f"    {i:>3}) {s.student_id}  {s.full_name}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or student id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1].student_id
            continue
        match = next((s for s in rows
                       if s.student_id.lower() == raw.lower()), None)
        if match:
            return match.student_id
        print("    No matching student.")


def _pick_plan() -> Plan:
    rows = data.list_plans()
    if not rows:
        print("    No plans yet.")
        raise _UserAbort
    names = {s.student_id: s.full_name
              for s in student_data.list_students()}
    print("\n  Plans:")
    for i, p in enumerate(rows, 1):
        print(f"    {i:>3}) #{p.plan_id}  {p.student_id}  "
              f"{names.get(p.student_id, '?')[:14]:<14}  "
              f"{p.title[:30]:<30}  [{p.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((p for p in rows if p.plan_id == n), None)
            if match:
                return match
        print("    No matching plan.")


def _pick_goal(plan_id: int) -> Goal:
    rows = data.list_goals(plan_id=plan_id)
    if not rows:
        print("    No goals on this plan.")
        raise _UserAbort
    print("\n  Goals:")
    for i, g in enumerate(rows, 1):
        mark = "✓" if g.is_done else " "
        print(f"    {i:>3}) [{mark}] #{g.goal_id}  "
              f"{g.category[:14]:<14}  {g.title[:34]:<34}  "
              f"[{g.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((g for g in rows if g.goal_id == n), None)
            if match:
                return match
        print("    No matching goal.")


def _pick_review(plan_id: int) -> Review:
    rows = data.list_reviews(plan_id=plan_id)
    if not rows:
        print("    No reviews on this plan.")
        raise _UserAbort
    print("\n  Reviews:")
    for i, r in enumerate(rows, 1):
        print(f"    {i:>3}) #{r.review_id}  {r.review_date}  "
              f"by {r.reviewer or '—'}  ({r.progress or '—'})")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows if r.review_id == n), None)
            if match:
                return match
        print("    No matching review.")


# ── Print helpers ──────────────────────────────────────────────────

def _print_plans(rows: list[Plan]) -> None:
    if not rows:
        print("\n  (no plans)")
        return
    names = {s.student_id: s.full_name
              for s in student_data.list_students()}
    print()
    print(f"  {'#':>4}  {'Student':<10}  {'Name':<20}  "
          f"{'Type':<12}  {'Status':<11}  {'Next due':<10}  Title")
    print("  " + "-" * 110)
    for p in rows:
        flag = "!" if p.review_overdue else " "
        print(f"  {p.plan_id:>4}{flag}{p.student_id:<10}  "
              f"{names.get(p.student_id, '?')[:20]:<20}  "
              f"{p.plan_type[:12]:<12}  "
              f"{p.status:<11}  "
              f"{p.next_review_due or '—':<10}  "
              f"{p.title[:34]}")
    print(f"\n  {len(rows)} plan(s).")


def _print_plan_full(p: Plan) -> None:
    detail = data.get_plan_detail(p.plan_id)
    assert detail is not None
    done, total = detail.goal_progress
    print()
    print(f"    #{p.plan_id}  {p.title}")
    print(f"    Student        : {p.student_id} — "
          f"{detail.student_name}")
    print(f"    Type           : {p.plan_type}")
    print(f"    Status         : {p.status}")
    print(f"    Lead           : {p.lead_staff or '—'}")
    print(f"    Range          : "
          f"{p.start_date or '—'} → {p.end_date or '—'}")
    print(f"    Review every   : {p.review_frequency}")
    print(f"    Last reviewed  : {p.last_reviewed or '—'}")
    print(f"    Next review due: {p.next_review_due or '—'}"
          + ("  (overdue)" if p.review_overdue else ""))
    print(f"    Goals          : {done}/{total} achieved")
    for label, val in (
            ("Strengths",            p.strengths),
            ("Barriers",             p.barriers),
            ("Strategies",           p.strategies),
            ("Support provided",     p.support_provided),
            ("Parental involvement", p.parental_involvement),
            ("Success criteria",     p.success_criteria),
            ("Notes",                p.notes),
    ):
        if val:
            print()
            print(f"    {label}:")
            for line in val.splitlines():
                print(f"      {line}")
    if detail.goals:
        print()
        print("    Goals:")
        for g in detail.goals:
            mark = "✓" if g.is_done else "·"
            due = f"  due {g.target_date}" if g.target_date else ""
            print(f"      [{mark}] #{g.goal_id}  "
                  f"{g.category}  {g.title}  ({g.status}){due}")
    if detail.reviews:
        print()
        print("    Reviews:")
        for r in detail.reviews:
            print(f"      #{r.review_id}  {r.review_date}  "
                  f"by {r.reviewer or '—'}  "
                  f"({r.progress or '—'})")
            if r.comments:
                for line in r.comments.splitlines():
                    print(f"        {line}")


# ── Plan flows ────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All ILPs ═══")
    _print_plans(data.list_plans())
    _pause()


def list_open() -> None:
    print("\n═══ Open ILPs ═══")
    _print_plans(data.list_plans(open_only=True))
    _pause()


def list_overdue() -> None:
    print("\n═══ Review Overdue ═══")
    _print_plans(data.list_plans(review_overdue=True))
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter ILPs ═══")
    try:
        sid = _input("Student id") or None
        ptype = _input(f"Type ({'/'.join(PLAN_TYPES)})") or None
        status = _input(f"Status ({'/'.join(PLAN_STATUSES)})") or None
        lead = _input("Lead contains") or None
        title = _input("Title contains") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_plans(
            student_id=sid, plan_type=ptype, status=status,
            lead_like=lead, title_like=title,
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_plans(rows)
    _pause()


def per_student_flow() -> None:
    print("\n═══ Per-Student ILPs ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_plans(data.list_plans(student_id=sid))
    _pause()


def view_flow() -> None:
    print("\n═══ View ILP ═══")
    try:
        p = _pick_plan()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_plan_full(p)
    _pause()


def _collect_plan_form(existing: Plan | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    if is_edit:
        payload["student_id"] = existing.student_id
        print(f"\n  Editing plan for {existing.student_id}")
    else:
        payload["student_id"] = _pick_student()
    payload["title"] = _input(
        "Title",
        default=(existing.title if is_edit else ""),
        allow_empty=False)
    payload["plan_type"] = _pick_from(
        "Plan type", list(PLAN_TYPES),
        default=(existing.plan_type if is_edit
                  else DEFAULT_PLAN_TYPE))
    payload["status"] = _pick_from(
        "Status", list(PLAN_STATUSES),
        default=(existing.status if is_edit
                  else DEFAULT_PLAN_STATUS))
    payload["lead_staff"] = _input(
        "Lead staff",
        default=(existing.lead_staff or "") if is_edit else "")
    payload["start_date"] = _input(
        "Start date (YYYY-MM-DD)",
        default=(existing.start_date if is_edit
                  else _date.today().isoformat()))
    payload["end_date"] = _input(
        "End date (YYYY-MM-DD)",
        default=(existing.end_date or "") if is_edit else "")
    payload["review_frequency"] = _pick_from(
        "Review frequency", list(REVIEW_FREQUENCIES),
        default=(existing.review_frequency if is_edit
                  else DEFAULT_REVIEW_FREQUENCY))
    payload["next_review_due"] = _input(
        "Next review due (YYYY-MM-DD)",
        default=(existing.next_review_due or "") if is_edit else "")
    try:
        payload["strengths"] = _multiline(
            "Strengths",
            default=(existing.strengths or "") if is_edit else "")
        payload["barriers"] = _multiline(
            "Barriers",
            default=(existing.barriers or "") if is_edit else "")
        payload["strategies"] = _multiline(
            "Strategies",
            default=(existing.strategies or "") if is_edit else "")
        payload["support_provided"] = _multiline(
            "Support provided",
            default=(existing.support_provided or "")
            if is_edit else "")
        payload["parental_involvement"] = _multiline(
            "Parental involvement",
            default=(existing.parental_involvement or "")
            if is_edit else "")
        payload["success_criteria"] = _multiline(
            "Success criteria",
            default=(existing.success_criteria or "")
            if is_edit else "")
    except _UserAbort:
        raise
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_plan() -> None:
    print("\n═══ New ILP ═══")
    try:
        payload = _collect_plan_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        p = data.create_plan(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created plan #{p.plan_id} {p.title!r}")
    _pause()


def edit_plan() -> None:
    print("\n═══ Edit ILP ═══")
    try:
        p = _pick_plan()
        payload = _collect_plan_form(p)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_plan(p.plan_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{p.plan_id}")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Plan Status ═══")
    try:
        p = _pick_plan()
        new_status = _pick_from("New status", list(PLAN_STATUSES),
                                  default=p.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_plan_status(p.plan_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{p.plan_id} → {new_status}")
    _pause()


def delete_plan_flow() -> None:
    print("\n═══ Delete ILP ═══")
    try:
        p = _pick_plan()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete plan #{p.plan_id}? "
              "Goals + reviews go too. Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_plan(p.plan_id):
        print(f"\n  ✓ Deleted #{p.plan_id}")
    _pause()


# ── Goal flows ────────────────────────────────────────────────────

def new_goal_flow() -> None:
    print("\n═══ New Goal ═══")
    try:
        p = _pick_plan()
        title = _input("Title", allow_empty=False)
        category = _pick_from("Category", list(GOAL_CATEGORIES),
                                 default=DEFAULT_GOAL_CATEGORY)
        target_date = _input("Target date")
        success = _multiline("Success criteria")
        notes = _input("Notes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        g = data.create_goal({
            "plan_id":          p.plan_id,
            "title":            title,
            "category":         category,
            "target_date":      target_date or None,
            "success_criteria": success or None,
            "notes":            notes or None,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Added goal #{g.goal_id}")
    _pause()


def edit_goal_flow() -> None:
    print("\n═══ Edit Goal ═══")
    try:
        p = _pick_plan()
        g = _pick_goal(p.plan_id)
        title = _input("Title", default=g.title, allow_empty=False)
        category = _pick_from("Category", list(GOAL_CATEGORIES),
                                 default=g.category)
        target_date = _input("Target date",
                                 default=g.target_date or "")
        status = _pick_from("Status", list(GOAL_STATUSES),
                              default=g.status)
        success = _multiline("Success criteria",
                                 default=g.success_criteria or "")
        notes = _input("Notes", default=g.notes or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_goal(g.goal_id, {
            "title": title, "category": category,
            "target_date": target_date or None,
            "status": status,
            "success_criteria": success or None,
            "notes": notes or None,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{g.goal_id}")
    _pause()


def achieve_goal_flow() -> None:
    print("\n═══ Achieve Goal ═══")
    try:
        p = _pick_plan()
        g = _pick_goal(p.plan_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.achieve_goal(g.goal_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{g.goal_id} → Achieved")
    _pause()


def set_goal_status_flow() -> None:
    print("\n═══ Change Goal Status ═══")
    try:
        p = _pick_plan()
        g = _pick_goal(p.plan_id)
        new_status = _pick_from("New status", list(GOAL_STATUSES),
                                  default=g.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_goal_status(g.goal_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{g.goal_id} → {new_status}")
    _pause()


def delete_goal_flow() -> None:
    print("\n═══ Delete Goal ═══")
    try:
        p = _pick_plan()
        g = _pick_goal(p.plan_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete goal #{g.goal_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_goal(g.goal_id):
        print(f"\n  ✓ Deleted #{g.goal_id}")
    _pause()


# ── Review flows ──────────────────────────────────────────────────

def add_review_flow() -> None:
    print("\n═══ Add Review ═══")
    try:
        p = _pick_plan()
        review_date = _input("Review date",
                                default=_date.today().isoformat())
        reviewer = _input("Reviewer", default=p.lead_staff or "")
        progress = _pick_from("Progress",
                                  [""] + list(PROGRESS_TAGS),
                                  default="")
        comments = _multiline("Comments")
        next_steps = _multiline("Next steps")
        next_due = _input("Next review due (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.add_review(
            p.plan_id, review_date=review_date,
            reviewer=reviewer or None,
            progress=progress or None,
            comments=comments or None,
            next_steps=next_steps or None,
            next_review_due=next_due or None,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Added review #{r.review_id}")
    _pause()


def list_reviews_flow() -> None:
    print("\n═══ Reviews for Plan ═══")
    try:
        p = _pick_plan()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.list_reviews(plan_id=p.plan_id)
    if not rows:
        print("\n  (no reviews)")
    else:
        print()
        print(f"  {'#':>4}  {'Date':<10}  {'Progress':<14}  Reviewer")
        for r in rows:
            print(f"  {r.review_id:>4}  {r.review_date:<10}  "
                  f"{(r.progress or '—')[:14]:<14}  "
                  f"{r.reviewer or '—'}")
            if r.comments:
                for line in r.comments.splitlines()[:3]:
                    print(f"      {line}")
    _pause()


def edit_review_flow() -> None:
    print("\n═══ Edit Review ═══")
    try:
        p = _pick_plan()
        r = _pick_review(p.plan_id)
        date_str = _input("Date", default=r.review_date,
                            allow_empty=False)
        reviewer = _input("Reviewer", default=r.reviewer or "")
        progress = _pick_from("Progress",
                                  [""] + list(PROGRESS_TAGS),
                                  default=r.progress or "")
        comments = _multiline("Comments", default=r.comments or "")
        next_steps = _multiline("Next steps",
                                    default=r.next_steps or "")
        next_due = _input("Next review due",
                            default=r.next_review_due or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_review(r.review_id, {
            "review_date": date_str,
            "reviewer": reviewer or None,
            "progress": progress or None,
            "comments": comments or None,
            "next_steps": next_steps or None,
            "next_review_due": next_due or None,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{r.review_id}")
    _pause()


def delete_review_flow() -> None:
    print("\n═══ Delete Review ═══")
    try:
        p = _pick_plan()
        r = _pick_review(p.plan_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete review #{r.review_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_review(r.review_id):
        print(f"\n  ✓ Deleted #{r.review_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ ILP Summary ═══")
    try:
        win = int(_input("Upcoming review window (days)",
                            default="14"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    summ = data.summary(upcoming_window_days=win)
    print(f"\n  Total plans         : {summ.total_plans}")
    print(f"  Open                : {summ.open_count}")
    print(f"  Distinct students   : {summ.distinct_students}")
    print(f"  Total goals         : {summ.total_goals}")
    print(f"  Goals achieved      : {summ.goals_achieved}")
    print(f"  Reviews overdue     : {summ.review_overdue}")
    print(f"  Reviews due ({win}d)   : {summ.upcoming_review}")
    print("\n  By status:")
    for s in PLAN_STATUSES:
        n = summ.by_status.get(s, 0)
        if n:
            print(f"    {s:<14} : {n}")
    print("\n  By type:")
    for t in PLAN_TYPES:
        n = summ.by_type.get(t, 0)
        if n:
            print(f"    {t:<14} : {n}")
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",            list_all),
    ("List open",           list_open),
    ("Review overdue",      list_overdue),
    ("Filter",              filter_flow),
    ("Per-student",         per_student_flow),
    ("View plan",           view_flow),
    ("New plan",            new_plan),
    ("Edit plan",           edit_plan),
    ("Change plan status",  set_status_flow),
    ("Delete plan",         delete_plan_flow),
    ("─" * 6,               lambda: None),
    ("New goal",            new_goal_flow),
    ("Edit goal",           edit_goal_flow),
    ("Achieve goal",        achieve_goal_flow),
    ("Change goal status",  set_goal_status_flow),
    ("Delete goal",         delete_goal_flow),
    ("─" * 6,               lambda: None),
    ("Add review",          add_review_flow),
    ("List reviews",        list_reviews_flow),
    ("Edit review",         edit_review_flow),
    ("Delete review",       delete_review_flow),
    ("─" * 6,               lambda: None),
    ("Summary",             summary_flow),
]


def run() -> None:
    while True:
        print("\n── ILP ──")
        for i, (label, _) in enumerate(_MENU, 1):
            if label.startswith("─"):
                print(f"      {label * 3}")
            else:
                print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        label, handler = _MENU[int(choice) - 1]
        if label.startswith("─"):
            continue
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("ILP CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "ILP":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("ILP CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
