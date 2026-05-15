"""CLI flows for Sixth Form Progress Tracking."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.reports.progress import progress
from education_system.sixthform_system.modules.domain.reports.progress import progress as data
from education_system.sixthform_system.modules.domain.students.students import students as student_data
from education_system.sixthform_system.modules.domain.reports.progress.progress import (
    DEFAULT_PERIOD,
    DEFAULT_RATING,
    DEFAULT_RISK,
    DEFAULT_REVIEW_STATUS,
    DEFAULT_TARGET_AREA,
    DEFAULT_TARGET_STATUS,
    RATINGS,
    REVIEW_PERIODS,
    REVIEW_STATUSES,
    RISK_LEVELS,
    Review,
    TARGET_AREAS,
    TARGET_STATUSES,
    Target,
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


def _pick_from(label: str, options: list[str],
                default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}", default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number (or 'cancel').")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _pick_student() -> str:
    students = student_data.list_students()
    if not students:
        print("    No students.")
        raise _UserAbort
    print("\n  Students:")
    for i, s in enumerate(students, 1):
        print(f"    {i:>3}) {s.student_id}  {s.full_name}")
    while True:
        raw = _input(f"  Pick #1..{len(students)} (or student ID)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(students):
                return students[n - 1].student_id
            continue
        m = next((s for s in students
                   if s.student_id.lower() == raw.lower()), None)
        if m:
            return m.student_id
        print("    No matching student.")


# ── Print helpers ──────────────────────────────────────────────────

def _print_reviews(rows: list[Review]) -> None:
    if not rows:
        print("\n  (no reviews)")
        return
    names = {s.student_id: s.full_name
              for s in student_data.list_students()}
    print()
    print(f"  {'#':>4}  {'Student':<10}  {'Name':<22}  "
          f"{'Date':<10}  {'Period':<22}  "
          f"{'Status':<10}  {'Risk':<8}  Overall")
    print("  " + "-" * 110)
    for r in rows:
        print(f"  {r.review_id:>4}  {r.student_id:<10}  "
              f"{names.get(r.student_id, '?')[:22]:<22}  "
              f"{r.review_date:<10}  "
              f"{r.period[:22]:<22}  "
              f"{r.status:<10}  {r.risk_level:<8}  "
              f"{r.overall}")
    print(f"\n  {len(rows)} review(s).")


def _print_targets(rows: list[Target]) -> None:
    if not rows:
        print("\n  (no targets)")
        return
    print()
    print(f"  {'#':>4}  {'Rev':>4}  {'Area':<12}  {'Due':<10}  "
          f"{'Status':<10}  Description")
    print("  " + "-" * 96)
    for t in rows:
        print(f"  {t.target_id:>4}  {t.review_id:>4}  "
              f"{t.area[:12]:<12}  "
              f"{(t.due_date or '—'):<10}  {t.status:<10}  "
              f"{t.description[:48]}")
    print(f"\n  {len(rows)} target(s).")


# ── Review flows ──────────────────────────────────────────────────

def list_active() -> None:
    print("\n═══ Active Reviews ═══")
    _print_reviews(data.list_reviews(active_only=True))
    _review_action_loop()


def list_all() -> None:
    print("\n═══ All Reviews ═══")
    _print_reviews(data.list_reviews())
    _review_action_loop()


def list_drafts() -> None:
    print("\n═══ Draft Reviews ═══")
    _print_reviews(data.list_reviews(status="Draft"))
    _review_action_loop()


def filter_reviews() -> None:
    print("\n═══ Filter Reviews ═══")
    try:
        sid = _input("Student ID") or None
        period = _input("Period") or None
        year = _input("Academic year") or None
        status = _input(f"Status ({'/'.join(REVIEW_STATUSES)})") or None
        risk = _input(f"Risk ({'/'.join(RISK_LEVELS)})") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_reviews(student_id=sid, period=period,
                                    academic_year=year,
                                    status=status,
                                    risk_level=risk)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_reviews(rows)
    _review_action_loop()


def per_student() -> None:
    print("\n═══ Per-Student Reviews ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    s = student_data.get_student(sid)
    print(f"\n  {s.student_id}  {s.full_name}")
    _print_reviews(data.reviews_for_student(sid))
    _review_action_loop()


def view_review(review_id: int | None = None) -> None:
    print("\n═══ View Review ═══")
    try:
        rid = review_id if review_id is not None else int(
            _input("Review ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    rv = data.view_review(rid)
    if rv is None:
        print(f"  ✗ No review #{rid}")
        _pause()
        return
    r = rv.review
    print()
    print(f"    Review #{r.review_id}")
    print(f"    Student        : {r.student_id}  ({rv.student_name})")
    print(f"    Date           : {r.review_date}")
    print(f"    Period         : {r.period}"
          + (f"  ({r.academic_year})"
              if r.academic_year else ""))
    print(f"    Reviewer       : "
          f"{rv.reviewer_name or r.reviewer_staff_id or '—'}")
    print(f"    Status         : {r.status}"
          + (f"  (shared {r.shared_at})" if r.shared_at else ""))
    print(f"    Risk           : {r.risk_level}")
    print(f"    Overall        : {r.overall}")
    print(f"    Attitude       : {r.attitude}")
    print(f"    Homework       : {r.homework}")
    print(f"    Attendance %   : "
          f"{r.attendance_pct if r.attendance_pct is not None else '—'}")
    if r.academic_summary:
        print("\n    Academic summary:")
        for line in r.academic_summary.splitlines():
            print(f"      {line}")
    if r.behaviour_summary:
        print("\n    Behaviour summary:")
        for line in r.behaviour_summary.splitlines():
            print(f"      {line}")
    if r.next_steps:
        print("\n    Next steps:")
        for line in r.next_steps.splitlines():
            print(f"      {line}")
    if r.notes:
        print("\n    Notes:")
        for line in r.notes.splitlines():
            print(f"      {line}")
    print(f"\n  Targets ({len(rv.targets)} — "
          f"{rv.open_targets} open, {rv.met_targets} met):")
    _print_targets(rv.targets)
    _pause()


def _collect_form(existing: Review | None,
                     prefill: dict | None = None) -> dict[str, Any]:
    is_edit = existing is not None
    p: dict[str, Any] = {}
    if is_edit:
        print(f"\n  Editing review #{existing.review_id} "
              f"for {existing.student_id}")
        p["student_id"] = existing.student_id
    else:
        p["student_id"] = _pick_student()

    p["review_date"] = _input(
        "Review date (YYYY-MM-DD)",
        default=existing.review_date if is_edit
        else _date.today().isoformat(), allow_empty=False)
    p["period"] = _pick_from(
        "Period", list(REVIEW_PERIODS),
        default=existing.period if is_edit else DEFAULT_PERIOD)
    p["academic_year"] = _input(
        "Academic year (optional)",
        default=(existing.academic_year or "") if is_edit else "")
    p["reviewer_staff_id"] = _input(
        "Reviewer (staff ID, optional)",
        default=(existing.reviewer_staff_id or "") if is_edit else "")

    p["overall"]  = _pick_from(
        "Overall", list(RATINGS),
        default=existing.overall if is_edit else DEFAULT_RATING)
    p["attitude"] = _pick_from(
        "Attitude", list(RATINGS),
        default=existing.attitude if is_edit else DEFAULT_RATING)
    p["homework"] = _pick_from(
        "Homework", list(RATINGS),
        default=existing.homework if is_edit else DEFAULT_RATING)

    seed_att = ""
    if is_edit and existing.attendance_pct is not None:
        seed_att = f"{existing.attendance_pct:.1f}"
    elif prefill and prefill.get("attendance_pct") is not None:
        seed_att = f"{prefill['attendance_pct']:.1f}"
    p["attendance_pct"] = _input(
        "Attendance % (optional, 0-100)", default=seed_att)

    p["risk_level"] = _pick_from(
        "Risk level", list(RISK_LEVELS),
        default=existing.risk_level if is_edit else DEFAULT_RISK)
    p["status"] = _pick_from(
        "Status", list(REVIEW_STATUSES),
        default=existing.status if is_edit else DEFAULT_REVIEW_STATUS)

    seed_acad = ((existing.academic_summary or "")
                  if is_edit else (prefill or {}).get(
                      "academic_summary", ""))
    p["academic_summary"] = _input(
        "Academic summary (single line)", default=seed_acad)
    p["behaviour_summary"] = _input(
        "Behaviour summary (single line)",
        default=(existing.behaviour_summary or "") if is_edit else "")
    p["next_steps"] = _input(
        "Next steps (single line)",
        default=(existing.next_steps or "") if is_edit else "")
    seed_notes = ((existing.notes or "") if is_edit
                   else (prefill or {}).get("notes", ""))
    p["notes"] = _input("Notes", default=seed_notes)
    return p


def new_review() -> None:
    print("\n═══ New Review ═══")
    try:
        sid_pick = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    prefill_choice = _input(
        "Auto-fill attendance % and academic summary from "
        "current data? (y/n)", default="y")
    prefill = data.populate_from_data(sid_pick) \
        if prefill_choice.lower() in ("y", "yes") else None
    if prefill:
        att = prefill.get("attendance_pct")
        if att is not None:
            print(f"  Auto-filled attendance: {att:.1f}%")
        if prefill.get("academic_summary"):
            print(f"  Auto-filled academic summary "
                  f"(edit during prompt if needed)")

    fake = type("F", (), {})()
    fake.student_id = sid_pick
    fake.review_date = _date.today().isoformat()
    fake.period = DEFAULT_PERIOD
    fake.academic_year = None
    fake.reviewer_staff_id = None
    fake.overall = DEFAULT_RATING
    fake.attitude = DEFAULT_RATING
    fake.homework = DEFAULT_RATING
    fake.attendance_pct = (prefill or {}).get("attendance_pct")
    fake.risk_level = DEFAULT_RISK
    fake.status = DEFAULT_REVIEW_STATUS
    fake.academic_summary = (prefill or {}).get("academic_summary")
    fake.behaviour_summary = None
    fake.next_steps = None
    fake.notes = (prefill or {}).get("notes")
    try:
        payload = _collect_form(None, prefill=prefill)
        # Override student_id (collect_form picks a fresh one in
        # non-edit branch; we want our pre-picked one).
        payload["student_id"] = sid_pick
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.create_review(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created review #{r.review_id} "
          f"({r.period}, {r.status})")
    _pause()


def edit_review(review_id: int | None = None) -> None:
    print("\n═══ Edit Review ═══")
    try:
        rid = review_id if review_id is not None else int(
            _input("Review ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_review(rid)
    if existing is None:
        print(f"  ✗ No review #{rid}")
        _pause()
        return
    try:
        payload = _collect_form(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_review(rid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{rid}")
    _pause()


def set_review_status_flow(review_id: int | None = None) -> None:
    print("\n═══ Change Review Status ═══")
    try:
        rid = review_id if review_id is not None else int(
            _input("Review ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_review(rid)
    if existing is None:
        print(f"  ✗ No review #{rid}")
        _pause()
        return
    try:
        new = _pick_from("New status", list(REVIEW_STATUSES),
                            default=existing.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_review_status(rid, new)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{rid} → {new}")
    _pause()


def delete_review_flow(review_id: int | None = None) -> None:
    print("\n═══ Delete Review ═══")
    print("  Only Draft reviews can be hard-deleted. Others should "
          "be archived.")
    try:
        rid = review_id if review_id is not None else int(
            _input("Review ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_review(rid)
    if existing is None:
        print(f"  ✗ No review #{rid}")
        _pause()
        return
    if _input(f"Delete review #{rid}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        if data.delete_review(rid):
            print(f"\n  ✓ Deleted #{rid}")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    _pause()


# ── Target flows ─────────────────────────────────────────────────

def add_target_flow(review_id: int | None = None) -> None:
    print("\n═══ Add Target ═══")
    try:
        rid = review_id if review_id is not None else int(
            _input("Review ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_review(rid) is None:
        print(f"  ✗ No review #{rid}")
        _pause()
        return
    try:
        area = _pick_from("Area", list(TARGET_AREAS),
                            default=DEFAULT_TARGET_AREA)
        desc = _input("Description (SMART)", allow_empty=False)
        measure = _input("Measure (how we'll check, optional)")
        due = _input("Due date (optional)")
        status = _pick_from("Status", list(TARGET_STATUSES),
                              default=DEFAULT_TARGET_STATUS)
        note = _input("Progress note (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        t = data.add_target(rid, {
            "area": area, "description": desc, "measure": measure,
            "due_date": due, "status": status, "progress_note": note,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Target #{t.target_id} added to review #{rid}")
    _pause()


def list_targets_flow() -> None:
    print("\n═══ List Targets ═══")
    try:
        sid = _input("Student ID (optional)") or None
        status = _input(f"Status ({'/'.join(TARGET_STATUSES)})") or None
        open_only = _input("Open only? (y/n)",
                              default="y").lower() in ("y", "yes")
        due_before = _input("Due before (YYYY-MM-DD, optional)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_targets(
            student_id=sid, status=status,
            open_only=open_only, due_before=due_before)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_targets(rows)
    _pause()


def edit_target_flow() -> None:
    print("\n═══ Edit Target ═══")
    try:
        tid = int(_input("Target ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_target(tid)
    if existing is None:
        print(f"  ✗ No target #{tid}")
        _pause()
        return
    try:
        area = _pick_from("Area", list(TARGET_AREAS),
                            default=existing.area)
        desc = _input("Description", default=existing.description,
                        allow_empty=False)
        measure = _input("Measure", default=existing.measure or "")
        due = _input("Due date", default=existing.due_date or "")
        status = _pick_from("Status", list(TARGET_STATUSES),
                              default=existing.status)
        note = _input("Progress note",
                        default=existing.progress_note or "")
        closed = _input("Closed on (auto on Met/Missed if blank)",
                          default=existing.closed_on or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_target(tid, {
            "area": area, "description": desc, "measure": measure,
            "due_date": due, "status": status,
            "progress_note": note, "closed_on": closed,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated target #{tid}")
    _pause()


def set_target_status_flow() -> None:
    print("\n═══ Change Target Status ═══")
    try:
        tid = int(_input("Target ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_target(tid)
    if existing is None:
        print(f"  ✗ No target #{tid}")
        _pause()
        return
    try:
        new = _pick_from("New status", list(TARGET_STATUSES),
                            default=existing.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_target_status(tid, new)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{tid} → {new}")
    _pause()


def delete_target_flow() -> None:
    print("\n═══ Delete Target ═══")
    try:
        tid = int(_input("Target ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_target(tid) is None:
        print(f"  ✗ No target #{tid}")
        _pause()
        return
    if _input(f"Delete target #{tid}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_target(tid):
        print(f"\n  ✓ Deleted #{tid}")
    _pause()


def overdue_flow() -> None:
    print("\n═══ Overdue Open Targets ═══")
    today = _date.today().isoformat()
    rows = [t for t in data.list_targets(open_only=True,
                                              due_before=today)
            if t.due_date and t.due_date < today]
    if not rows:
        print("\n  (no overdue targets)")
        _pause()
        return
    print(f"\n  {len(rows)} overdue:")
    _print_targets(rows)
    _pause()


def summary_flow() -> None:
    print("\n═══ Progress Summary ═══")
    s = data.summary()
    print(f"\n  Reviews: {s.total_reviews}")
    print(f"    Drafts    : {s.drafts}")
    print(f"    Published : {s.published}")
    print(f"    Shared    : {s.shared}")
    print(f"    Archived  : {s.archived}")
    print(f"  High/Critical risk (active): "
          f"{s.students_at_high_risk}")
    print("\n  Reviews by period:")
    for p in REVIEW_PERIODS:
        n = s.by_period.get(p, 0)
        if n:
            print(f"    {p:<24} : {n}")
    print("\n  Reviews by risk:")
    for r in RISK_LEVELS:
        n = s.by_risk.get(r, 0)
        if n:
            print(f"    {r:<10} : {n}")
    print("\n  Reviews by overall rating:")
    for r in RATINGS:
        n = s.by_overall.get(r, 0)
        if n:
            print(f"    {r:<26} : {n}")
    print(f"\n  Targets: {s.total_targets}")
    print(f"    Open       : {s.open_targets}")
    print(f"    Met        : {s.met_targets}")
    print(f"    Missed     : {s.missed_targets}")
    print(f"    Overdue (open): {s.overdue_open_targets}")
    print("\n  Targets by area:")
    for a in TARGET_AREAS:
        n = s.by_target_area.get(a, 0)
        if n:
            print(f"    {a:<18} : {n}")
    _pause()


# ── Row-action loop ───────────────────────────────────────────────

def _review_action_loop() -> None:
    print()
    print("  Actions:  V) View   E) Edit   T) Add target   "
          "S) Status   D) Delete   (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("v", "e", "t", "s", "d"):
            print("    Pick V, E, T, S, D, or Enter.")
            continue
        try:
            raw = _input("Review ID", allow_empty=False)
        except _UserAbort:
            return
        try:
            rid = int(raw)
        except ValueError:
            print("    Review ID must be a whole number.")
            continue
        if choice == "v":
            view_review(rid)
        elif choice == "e":
            edit_review(rid)
        elif choice == "t":
            add_target_flow(rid)
        elif choice == "s":
            set_review_status_flow(rid)
        elif choice == "d":
            delete_review_flow(rid)
        return


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Active Reviews",        list_active),
    ("All Reviews",           list_all),
    ("Drafts",                list_drafts),
    ("Filter",                filter_reviews),
    ("Per-Student",           per_student),
    ("View Review",           view_review),
    ("New Review",            new_review),
    ("Edit Review",           edit_review),
    ("Change Review Status",  set_review_status_flow),
    ("Delete Review",         delete_review_flow),
    ("Add Target",            add_target_flow),
    ("List Targets",          list_targets_flow),
    ("Edit Target",           edit_target_flow),
    ("Change Target Status",  set_target_status_flow),
    ("Delete Target",         delete_target_flow),
    ("Overdue Open Targets",  overdue_flow),
    ("Summary",               summary_flow),
]


def run() -> None:
    while True:
        print("\n── Progress Tracking ──")
        for i, (label, _) in enumerate(_MENU, 1):
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
        _, handler = _MENU[int(choice) - 1]
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Progress CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Progress Tracking":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Progress CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
