"""CLI flows for Sixth Form Attendance Concerns."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.systems.sixth_form.domain.pastoral.attendance_concerns import attendance_concerns
from education_system.systems.sixth_form.domain.pastoral.attendance_concerns import attendance_concerns as data
from education_system.systems.sixth_form.domain.learners.students import students as student_data
from education_system.systems.sixth_form.domain.pastoral.attendance_concerns.attendance_concerns import (
    CONCERN_LEVELS,
    Concern,
    DEFAULT_LEVEL,
    DEFAULT_REASON,
    DEFAULT_STATUS,
    OPEN_STATUSES,
    REASONS,
    STATUSES,
    ValidationError,
    WatchlistThresholds,
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
            print("    Enter a number (or 'cancel' to abort).")
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
        match = next((s for s in students
                       if s.student_id.lower() == raw.lower()), None)
        if match:
            return match.student_id
        print("    No matching student.")


# ── Print helpers ──────────────────────────────────────────────────

def _print_concerns(rows: list[Concern]) -> None:
    if not rows:
        print("\n  (no concerns)")
        return
    print()
    print(f"  {'#':>4}  {'Student':<10}  {'Raised':<10}  "
          f"{'Reason':<26}  {'Level':<8}  {'Status':<18}  Obs%")
    print("  " + "-" * 92)
    for c in rows:
        obs = "—" if c.observed_pct is None else f"{c.observed_pct:.1f}"
        print(f"  {c.concern_id:>4}  {c.student_id:<10}  "
              f"{c.raised_date:<10}  {c.reason[:26]:<26}  "
              f"{c.level:<8}  {c.status:<18}  {obs:>5}")
    print(f"\n  {len(rows)} concern(s).")


# ── Concern flows ──────────────────────────────────────────────────

def list_open() -> None:
    print("\n═══ Open Attendance Concerns ═══")
    rows = data.list_concerns(open_only=True)
    _print_concerns(rows)
    _row_action_loop(rows)


def list_all() -> None:
    print("\n═══ All Attendance Concerns ═══")
    rows = data.list_concerns()
    _print_concerns(rows)
    _row_action_loop(rows)


def filter_concerns() -> None:
    print("\n═══ Filter Concerns ═══")
    print("  (blank to skip; 'cancel' to abort)\n")
    try:
        sid = _input("Student ID") or None
        lvl = _input(f"Level ({'/'.join(CONCERN_LEVELS)})") or None
        status = _input(f"Status ({'/'.join(STATUSES)})") or None
        reason = _input("Reason (exact)") or None
        assigned = _input("Assigned-to contains") or None
        date_from = _input("From (YYYY-MM-DD)") or None
        date_to = _input("To (YYYY-MM-DD)") or None
        open_only_raw = _input("Open only? (y/n)", default="y")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    open_only = open_only_raw.lower() in ("y", "yes")
    try:
        rows = data.list_concerns(
            student_id=sid, level=lvl, status=status, reason=reason,
            assigned_to=assigned, date_from=date_from, date_to=date_to,
            open_only=open_only,
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_concerns(rows)
    _row_action_loop(rows)


def per_student() -> None:
    print("\n═══ Per-Student Concerns ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.concerns_for_student(sid)
    student = student_data.get_student(sid)
    print(f"\n  {student.student_id}  {student.full_name}")
    _print_concerns(rows)
    _row_action_loop(rows)


def view_concern(concern_id: int | None = None) -> None:
    print("\n═══ View Concern ═══")
    try:
        cid = concern_id if concern_id is not None else int(
            _input("Concern ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    c = data.get_concern(cid)
    if c is None:
        print(f"  ✗ No concern #{cid}")
        _pause()
        return
    print()
    print(f"    Concern ID     : #{c.concern_id}")
    print(f"    Student        : {c.student_id}")
    print(f"    Raised date    : {c.raised_date}")
    print(f"    Raised by      : {c.raised_by or '—'}")
    print(f"    Reason         : {c.reason}")
    print(f"    Level          : {c.level}")
    print(f"    Status         : {c.status}")
    print(f"    Assigned to    : {c.assigned_to or '—'}")
    print(f"    Threshold %    : "
          f"{c.threshold_pct if c.threshold_pct is not None else '—'}")
    print(f"    Observed %     : "
          f"{c.observed_pct if c.observed_pct is not None else '—'}")
    print(f"    Window (days)  : {c.window_days or '—'}")
    print(f"    Follow-up      : {c.follow_up_date or '—'}")
    if c.description:
        print("\n    Description:")
        for line in c.description.splitlines() or [""]:
            print(f"      {line}")
    if c.action_taken:
        print("\n    Action taken:")
        for line in c.action_taken.splitlines() or [""]:
            print(f"      {line}")
    if c.notes:
        print("\n    Notes:")
        for line in c.notes.splitlines() or [""]:
            print(f"      {line}")
    _pause()


def _collect_form(existing: Concern | None) -> dict[str, Any]:
    is_edit = existing is not None
    payload: dict[str, Any] = {}
    today = _date.today().isoformat()
    if is_edit:
        print(f"\n  Editing concern #{existing.concern_id} "
              f"for {existing.student_id}")
        payload["student_id"] = existing.student_id
    else:
        print("\n  ── Student ──")
        payload["student_id"] = _pick_student()

    payload["raised_date"] = _input(
        "Raised date (YYYY-MM-DD)",
        default=(existing.raised_date if is_edit else today),
        allow_empty=False,
    )
    payload["reason"] = _pick_from(
        "Reason", list(REASONS),
        default=(existing.reason if is_edit else DEFAULT_REASON))
    payload["level"] = _pick_from(
        "Level", list(CONCERN_LEVELS),
        default=(existing.level if is_edit else DEFAULT_LEVEL))
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    payload["raised_by"] = _input(
        "Raised by",
        default=(existing.raised_by or "") if is_edit else "")
    payload["assigned_to"] = _input(
        "Assigned to",
        default=(existing.assigned_to or "") if is_edit else "")
    payload["threshold_pct"] = _input(
        "Threshold % (optional, 0-100)",
        default=(str(existing.threshold_pct)
                  if is_edit and existing.threshold_pct is not None
                  else ""))
    payload["observed_pct"] = _input(
        "Observed % (optional, 0-100)",
        default=(str(existing.observed_pct)
                  if is_edit and existing.observed_pct is not None
                  else ""))
    payload["window_days"] = _input(
        "Window (days)",
        default=(str(existing.window_days)
                  if is_edit and existing.window_days is not None
                  else "28"))
    payload["follow_up_date"] = _input(
        "Follow-up date (optional)",
        default=(existing.follow_up_date or "") if is_edit else "")
    payload["description"] = _input(
        "Description (single line)",
        default=(existing.description or "") if is_edit else "")
    payload["action_taken"] = _input(
        "Action taken (optional)",
        default=(existing.action_taken or "") if is_edit else "")
    payload["notes"] = _input(
        "Notes (optional)",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_concern() -> None:
    print("\n═══ New Attendance Concern ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        c = data.create_concern(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created concern #{c.concern_id} "
          f"({c.reason}, level={c.level})")
    _pause()


def edit_concern(concern_id: int | None = None) -> None:
    print("\n═══ Edit Concern ═══")
    try:
        cid = concern_id if concern_id is not None else int(
            _input("Concern ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_concern(cid)
    if existing is None:
        print(f"  ✗ No concern #{cid}")
        _pause()
        return
    try:
        payload = _collect_form(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_concern(cid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{cid}")
    _pause()


def set_status_flow(concern_id: int | None = None) -> None:
    print("\n═══ Change Status ═══")
    try:
        cid = concern_id if concern_id is not None else int(
            _input("Concern ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_concern(cid)
    if existing is None:
        print(f"  ✗ No concern #{cid}")
        _pause()
        return
    try:
        new_status = _pick_from("New status", list(STATUSES),
                                  default=existing.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(cid, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{cid} → {new_status}")
    _pause()


def delete_concern_flow(concern_id: int | None = None) -> None:
    print("\n═══ Delete Concern ═══")
    try:
        cid = concern_id if concern_id is not None else int(
            _input("Concern ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_concern(cid) is None:
        print(f"  ✗ No concern #{cid}")
        _pause()
        return
    if _input(f"Delete concern #{cid}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_concern(cid):
        print(f"\n  ✓ Deleted #{cid}")
    _pause()


# ── Watchlist ─────────────────────────────────────────────────────

def watchlist() -> None:
    print("\n═══ Attendance Watchlist ═══")
    print("  (live: computed from attendance records — not stored)")
    try:
        window = int(_input("Window (days)", default="28"))
        min_pct = float(_input("Min attendance %", default="90"))
        max_lates = int(_input("Max lates", default="5"))
        max_abs = int(_input("Max absences", default="3"))
        max_unauth = int(_input("Max unauthorised", default="1"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    t = WatchlistThresholds(window_days=window, min_pct=min_pct,
                              max_lates=max_lates,
                              max_absences=max_abs,
                              max_unauth=max_unauth)
    entries = data.watchlist(t)
    if not entries:
        print("\n  (no students breach the thresholds)")
        _pause()
        return
    print()
    print(f"  {'Student':<10}  {'Name':<22}  {'%':>5}  "
          f"{'P':>3}  {'L':>3}  {'A':>3}  {'Au':>3}  "
          f"{'Sev':<8}  {'Open?':<6}  Reasons")
    print("  " + "-" * 110)
    for e in entries:
        pct = "—" if e.percentage is None else f"{e.percentage:.1f}"
        open_flag = "yes" if e.has_open_concern else "no"
        reasons = "; ".join(e.reasons)[:50]
        print(f"  {e.student_id:<10}  {e.student_name[:22]:<22}  "
              f"{pct:>5}  {e.present:>3}  {e.late:>3}  "
              f"{e.absent:>3}  {e.authorised:>3}  "
              f"{e.severity:<8}  {open_flag:<6}  {reasons}")
    print(f"\n  {len(entries)} student(s) on watchlist.")
    raw = _input(
        "Raise concern for one of these students? "
        "Enter student ID or blank to skip")
    if not raw:
        return
    target = next((e for e in entries
                    if e.student_id.lower() == raw.lower()), None)
    if target is None:
        print("  ✗ Not on watchlist.")
        _pause()
        return
    _raise_from_watchlist(target, t)


def _raise_from_watchlist(entry, thresholds: WatchlistThresholds) -> None:
    print(f"\n  Raising concern for {entry.student_id} "
          f"({entry.student_name})")
    today = _date.today().isoformat()
    try:
        reason = _pick_from("Reason", list(REASONS),
                              default=DEFAULT_REASON)
        level = _pick_from("Level", list(CONCERN_LEVELS),
                              default=entry.severity)
        assigned = _input("Assigned to")
        raised_by = _input("Raised by")
        desc = _input("Description",
                       default="; ".join(entry.reasons))
        action = _input("Action taken (optional)")
        follow = _input("Follow-up date (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        c = data.create_concern({
            "student_id": entry.student_id,
            "raised_date": today,
            "reason": reason, "level": level,
            "status": DEFAULT_STATUS,
            "threshold_pct": thresholds.min_pct,
            "observed_pct": entry.percentage,
            "window_days": thresholds.window_days,
            "description": desc, "action_taken": action,
            "follow_up_date": follow,
            "assigned_to": assigned, "raised_by": raised_by,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created concern #{c.concern_id}")
    _pause()


# ── Summary ──────────────────────────────────────────────────────

def summary() -> None:
    print("\n═══ Attendance Concerns Summary ═══")
    try:
        upcoming = int(_input("Follow-up window (days)", default="14"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    summ = data.summary(upcoming_window_days=upcoming)
    print(f"\n  Total concerns        : {summ.total}")
    print(f"  Open                  : {summ.open_count}")
    print("\n  Alerts:")
    print(f"    High/Critical open  : {summ.high_critical_open}")
    print(f"    Overdue follow-ups  : {summ.overdue_follow_ups}")
    print(f"    Upcoming ({upcoming}d)  : {summ.upcoming_follow_ups}")
    print(f"    Unassigned open     : {summ.unassigned_open}")
    print("\n  Watchlist (live):")
    print(f"    Students breaching  : {summ.watchlist_size}")
    print(f"    …without open concern: {summ.watchlist_without_concern}")
    print("\n  By level:")
    for lvl in CONCERN_LEVELS:
        print(f"    {lvl:<10} : {summ.by_level.get(lvl, 0)}")
    print("\n  By status:")
    for st in STATUSES:
        print(f"    {st:<22} : {summ.by_status.get(st, 0)}")
    print("\n  By reason:")
    for r in REASONS:
        n = summ.by_reason.get(r, 0)
        if n:
            print(f"    {r:<30} : {n}")
    _pause()


# ── Row-action loop ───────────────────────────────────────────────

def _row_action_loop(rows: list[Concern]) -> None:
    if not rows:
        _pause()
        return
    print()
    print("  Actions:  V) View   E) Edit   S) Status   "
          "D) Delete   (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("v", "e", "s", "d"):
            print("    Pick V, E, S, D, or Enter.")
            continue
        try:
            raw = _input("Concern ID", allow_empty=False)
        except _UserAbort:
            return
        try:
            cid = int(raw)
        except ValueError:
            print("    Concern ID must be a whole number.")
            continue
        if choice == "v":
            view_concern(cid)
        elif choice == "e":
            edit_concern(cid)
        elif choice == "s":
            set_status_flow(cid)
        elif choice == "d":
            delete_concern_flow(cid)
        return


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Watchlist (live)",        watchlist),
    ("List Open Concerns",      list_open),
    ("List All Concerns",       list_all),
    ("Filter Concerns",         filter_concerns),
    ("Per-Student",             per_student),
    ("View Concern",            view_concern),
    ("New Concern",             new_concern),
    ("Edit Concern",            edit_concern),
    ("Change Status",           set_status_flow),
    ("Delete Concern",          delete_concern_flow),
    ("Summary",                 summary),
]


def run() -> None:
    while True:
        print("\n── Attendance Concerns ──")
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
            logger.exception("Attendance-concerns CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Attendance Concerns":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Attendance-concerns CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
