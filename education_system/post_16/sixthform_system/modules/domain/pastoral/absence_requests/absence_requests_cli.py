"""CLI flows for Sixth Form Absence Requests."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.post_16.sixthform_system.modules.domain.pastoral.absence_requests import (
    absence_requests as data,
)
from education_system.post_16.sixthform_system.modules.domain.students.students import (
    students as student_data,
)
from education_system.post_16.sixthform_system.modules.domain.pastoral.absence_requests.absence_requests import (
    AbsenceRequest,
    DECIDED_STATUSES,
    DEFAULT_REASON,
    DEFAULT_STATUS,
    DEFAULT_SUBMITTER,
    REASONS,
    STATUSES,
    SUBMITTERS,
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

def _print_requests(rows: list[AbsenceRequest]) -> None:
    if not rows:
        print("\n  (no absence requests)")
        return
    print()
    print(f"  {'#':>4}  {'Student':<10}  {'From':<10}  {'To':<10}  "
          f"{'Days':>4}  {'Reason':<26}  {'Status':<10}")
    print("  " + "-" * 90)
    for r in rows:
        print(f"  {r.request_id:>4}  {r.student_id:<10}  "
              f"{r.start_date:<10}  {r.end_date:<10}  "
              f"{r.day_count:>4}  {r.reason[:26]:<26}  {r.status:<10}")
    print(f"\n  {len(rows)} request(s).")


# ── Flows ──────────────────────────────────────────────────────────

def list_pending() -> None:
    print("\n═══ Pending Absence Requests ═══")
    rows = data.list_requests(pending_only=True)
    _print_requests(rows)
    _row_action_loop(rows)


def list_all() -> None:
    print("\n═══ All Absence Requests ═══")
    rows = data.list_requests()
    _print_requests(rows)
    _row_action_loop(rows)


def filter_requests() -> None:
    print("\n═══ Filter Requests ═══")
    print("  (blank to skip; 'cancel' to abort)\n")
    try:
        sid = _input("Student ID") or None
        status = _input(f"Status ({'/'.join(STATUSES)})") or None
        reason = _input("Reason (exact)") or None
        date_from = _input("Submitted from (YYYY-MM-DD)") or None
        date_to = _input("Submitted to (YYYY-MM-DD)") or None
        ov_from = _input("Overlaps from (YYYY-MM-DD)") or None
        ov_to = _input("Overlaps to (YYYY-MM-DD)") or None
        pending_raw = _input("Pending only? (y/n)", default="n")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    pending_only = pending_raw.lower() in ("y", "yes")
    try:
        rows = data.list_requests(
            student_id=sid, status=status, reason=reason,
            pending_only=pending_only,
            date_from=date_from, date_to=date_to,
            overlaps_from=ov_from, overlaps_to=ov_to,
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_requests(rows)
    _row_action_loop(rows)


def per_student() -> None:
    print("\n═══ Per-Student Absence Requests ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.requests_for_student(sid)
    s = student_data.get_student(sid)
    print(f"\n  {s.student_id}  {s.full_name}")
    _print_requests(rows)
    _row_action_loop(rows)


def view_request(request_id: int | None = None) -> None:
    print("\n═══ View Request ═══")
    try:
        rid = request_id if request_id is not None else int(
            _input("Request ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    r = data.get_request(rid)
    if r is None:
        print(f"  ✗ No request #{rid}")
        _pause()
        return
    print()
    print(f"    Request ID     : #{r.request_id}")
    print(f"    Student        : {r.student_id}")
    print(f"    Submitted on   : {r.request_date}")
    print(f"    Submitted by   : {r.submitted_by or '—'}"
          f" ({r.submitter_type or '—'})")
    print(f"    Contact phone  : {r.contact_phone or '—'}")
    print(f"    Dates absent   : {r.start_date} → {r.end_date} "
          f"({r.day_count} day{'s' if r.day_count != 1 else ''})")
    print(f"    Reason         : {r.reason}")
    print(f"    Status         : {r.status}")
    if r.is_decided:
        print(f"    Decision date  : {r.decision_date or '—'}")
        print(f"    Decided by     : {r.decided_by or '—'}")
        if r.decision_notes:
            print("    Decision notes :")
            for line in r.decision_notes.splitlines() or [""]:
                print(f"      {line}")
    print(f"    Supporting doc : {r.supporting_doc or '—'}")
    if r.description:
        print("\n    Description:")
        for line in r.description.splitlines() or [""]:
            print(f"      {line}")
    if r.notes:
        print("\n    Notes:")
        for line in r.notes.splitlines() or [""]:
            print(f"      {line}")
    _pause()


def _collect_form(existing: AbsenceRequest | None) -> dict[str, Any]:
    is_edit = existing is not None
    payload: dict[str, Any] = {}
    today = _date.today().isoformat()
    if is_edit:
        print(f"\n  Editing request #{existing.request_id} "
              f"for {existing.student_id}")
        payload["student_id"] = existing.student_id
    else:
        print("\n  ── Student ──")
        payload["student_id"] = _pick_student()

    payload["request_date"] = _input(
        "Request date (YYYY-MM-DD)",
        default=(existing.request_date if is_edit else today),
        allow_empty=False,
    )
    payload["start_date"] = _input(
        "Start date (YYYY-MM-DD)",
        default=(existing.start_date if is_edit else today),
        allow_empty=False,
    )
    payload["end_date"] = _input(
        "End date (YYYY-MM-DD)",
        default=(existing.end_date if is_edit
                  else payload["start_date"]),
        allow_empty=False,
    )
    payload["reason"] = _pick_from(
        "Reason", list(REASONS),
        default=(existing.reason if is_edit else DEFAULT_REASON))
    payload["description"] = _input(
        "Description",
        default=(existing.description or "") if is_edit else "")
    payload["submitter_type"] = _pick_from(
        "Submitted by (type)", list(SUBMITTERS),
        default=(existing.submitter_type
                  if is_edit and existing.submitter_type
                  else DEFAULT_SUBMITTER))
    payload["submitted_by"] = _input(
        "Submitted by (name)",
        default=(existing.submitted_by or "") if is_edit else "")
    payload["contact_phone"] = _input(
        "Contact phone",
        default=(existing.contact_phone or "") if is_edit else "")
    payload["supporting_doc"] = _input(
        "Supporting document (filename / link)",
        default=(existing.supporting_doc or "") if is_edit else "")
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    if payload["status"] in DECIDED_STATUSES:
        payload["decision_date"] = _input(
            "Decision date",
            default=(existing.decision_date if is_edit and existing.decision_date
                      else today))
        payload["decided_by"] = _input(
            "Decided by",
            default=(existing.decided_by or "") if is_edit else "")
        payload["decision_notes"] = _input(
            "Decision notes",
            default=(existing.decision_notes or "") if is_edit else "")
    payload["notes"] = _input(
        "Notes (optional)",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_request() -> None:
    print("\n═══ New Absence Request ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.create_request(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created request #{r.request_id} "
          f"({r.start_date}..{r.end_date}, {r.status})")
    _pause()


def edit_request(request_id: int | None = None) -> None:
    print("\n═══ Edit Request ═══")
    try:
        rid = request_id if request_id is not None else int(
            _input("Request ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_request(rid)
    if existing is None:
        print(f"  ✗ No request #{rid}")
        _pause()
        return
    try:
        payload = _collect_form(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_request(rid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated request #{rid}")
    _pause()


def _decide_flow(request_id: int | None, *, approve: bool) -> None:
    verb = "Approve" if approve else "Deny"
    print(f"\n═══ {verb} Request ═══")
    try:
        rid = request_id if request_id is not None else int(
            _input("Request ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    r = data.get_request(rid)
    if r is None:
        print(f"  ✗ No request #{rid}")
        _pause()
        return
    print(f"\n  Request #{rid} — {r.student_id} "
          f"{r.start_date}..{r.end_date} ({r.reason})")
    try:
        decided_by = _input(f"{verb}d by")
        notes = _input("Decision notes (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        if approve:
            data.approve(rid, decided_by=decided_by or None,
                          decision_notes=notes or None)
        else:
            data.deny(rid, decided_by=decided_by or None,
                       decision_notes=notes or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Request #{rid} {verb.lower()}d.")
    _pause()


def approve_request(request_id: int | None = None) -> None:
    _decide_flow(request_id, approve=True)


def deny_request(request_id: int | None = None) -> None:
    _decide_flow(request_id, approve=False)


def set_status_flow(request_id: int | None = None) -> None:
    print("\n═══ Change Status ═══")
    try:
        rid = request_id if request_id is not None else int(
            _input("Request ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_request(rid)
    if existing is None:
        print(f"  ✗ No request #{rid}")
        _pause()
        return
    try:
        new_status = _pick_from("New status", list(STATUSES),
                                  default=existing.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(rid, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{rid} → {new_status}")
    _pause()


def delete_request_flow(request_id: int | None = None) -> None:
    print("\n═══ Delete Request ═══")
    try:
        rid = request_id if request_id is not None else int(
            _input("Request ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_request(rid) is None:
        print(f"  ✗ No request #{rid}")
        _pause()
        return
    if _input(f"Delete request #{rid}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_request(rid):
        print(f"\n  ✓ Deleted #{rid}")
    _pause()


# ── Summary ───────────────────────────────────────────────────────

def summary() -> None:
    print("\n═══ Absence Requests Summary ═══")
    try:
        window = int(_input("Upcoming window (days)", default="14"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    summ = data.summary(upcoming_window_days=window)
    print(f"\n  Total requests        : {summ.total}")
    print("\n  Alerts:")
    print(f"    Pending             : {summ.pending_count}")
    print(f"    Overdue pending     : {summ.overdue_pending}")
    print(f"    In progress today   : {summ.in_progress}")
    print(f"    Upcoming ({window}d)    : {summ.upcoming_approved}")
    print("\n  By status:")
    for st in STATUSES:
        print(f"    {st:<12} : {summ.by_status.get(st, 0)}")
    print("\n  By reason:")
    for r in REASONS:
        n = summ.by_reason.get(r, 0)
        if n:
            print(f"    {r:<30} : {n}")
    _pause()


# ── Row-action loop ───────────────────────────────────────────────

def _row_action_loop(rows: list[AbsenceRequest]) -> None:
    if not rows:
        _pause()
        return
    print()
    print("  Actions:  V) View   A) Approve   N) Deny   "
          "E) Edit   S) Status   D) Delete   (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("v", "a", "n", "e", "s", "d"):
            print("    Pick V, A, N, E, S, D, or Enter.")
            continue
        try:
            raw = _input("Request ID", allow_empty=False)
        except _UserAbort:
            return
        try:
            rid = int(raw)
        except ValueError:
            print("    Request ID must be a whole number.")
            continue
        if choice == "v":
            view_request(rid)
        elif choice == "a":
            approve_request(rid)
        elif choice == "n":
            deny_request(rid)
        elif choice == "e":
            edit_request(rid)
        elif choice == "s":
            set_status_flow(rid)
        elif choice == "d":
            delete_request_flow(rid)
        return


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List Pending Requests",   list_pending),
    ("List All Requests",       list_all),
    ("Filter Requests",         filter_requests),
    ("Per-Student",             per_student),
    ("View Request",            view_request),
    ("New Request",             new_request),
    ("Edit Request",            edit_request),
    ("Approve Request",         approve_request),
    ("Deny Request",            deny_request),
    ("Change Status",           set_status_flow),
    ("Delete Request",          delete_request_flow),
    ("Summary",                 summary),
]


def run() -> None:
    while True:
        print("\n── Absence Requests ──")
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
            logger.exception("Absence-requests CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Absence Requests":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Absence-requests CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
