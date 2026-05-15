"""CLI flows for Sixth Form Admissions."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.students.admissions import (
    admissions as data,
)
from education_system.sixthform_system.modules.domain.students.admissions.admissions import (
    Applicant,
    DEFAULT_OFFER_TYPE,
    DEFAULT_SOURCE,
    DEFAULT_STATUS,
    OFFER_TYPES,
    SOURCES,
    STATUSES,
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


def _pick_subject(label: str, default: str | None = None) -> str | None:
    """Pick from the live subjects catalogue. Empty = skip."""
    try:
        from education_system.sixthform_system.modules.domain.academics.subjects import (
            subjects as _subjects,
        )
        names = [s.name for s in _subjects.list_subjects()]
    except Exception:
        names = []
    if not names:
        return _input(label, default=default or "") or None
    return _pick_from(label, names, default=default)


def _pick_applicant() -> Applicant:
    rows = data.list_applicants()
    if not rows:
        print("    No applicants.")
        raise _UserAbort
    print("\n  Applicants:")
    for i, a in enumerate(rows, 1):
        print(f"    {i:>3}) {a.applicant_id}  {a.full_name[:24]:<24}  "
              f"[{a.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or applicant id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            continue
        match = next((a for a in rows
                       if a.applicant_id.lower() == raw.lower()), None)
        if match:
            return match
        print("    No matching applicant.")


# ── Print helpers ──────────────────────────────────────────────────

def _print_applicants(rows: list[Applicant]) -> None:
    if not rows:
        print("\n  (no applicants)")
        return
    print()
    print(f"  {'ID':<10}  {'Name':<24}  {'Submitted':<10}  "
          f"{'Status':<22}  Subjects")
    print("  " + "-" * 100)
    for a in rows:
        subj = ", ".join(a.subjects)[:32]
        print(f"  {a.applicant_id:<10}  {a.full_name[:24]:<24}  "
              f"{a.submitted_at:<10}  {a.status:<22}  {subj}")
    print(f"\n  {len(rows)} applicant(s).")


# ── Flows ──────────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Applicants ═══")
    _print_applicants(data.list_applicants())
    _pause()


def list_open() -> None:
    print("\n═══ Open Applicants ═══")
    _print_applicants(data.list_applicants(open_only=True))
    _pause()


def filter_applicants() -> None:
    print("\n═══ Filter Applicants ═══")
    print("  (blank to skip; 'cancel' to abort)\n")
    try:
        status = _input(f"Status ({'/'.join(STATUSES)})") or None
        source = _input(f"Source ({'/'.join(SOURCES)})") or None
        search = _input("Search (id/name/email)") or None
        date_from = _input("Submitted from (YYYY-MM-DD)") or None
        date_to = _input("Submitted to (YYYY-MM-DD)") or None
        open_raw = _input("Open only? (y/n)", default="n")
        offer_raw = _input("Has offer? (y/n)", default="n")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_applicants(
            status=status, source=source, search=search,
            date_from=date_from, date_to=date_to,
            open_only=open_raw.lower() in ("y", "yes"),
            has_offer=offer_raw.lower() in ("y", "yes"),
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_applicants(rows)
    _pause()


def view_applicant() -> None:
    print("\n═══ View Applicant ═══")
    try:
        a = _pick_applicant()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    print()
    print(f"    ID                : {a.applicant_id}")
    print(f"    Name              : {a.full_name}")
    print(f"    DOB               : {a.dob or '—'}")
    print(f"    Email             : {a.email or '—'}")
    print(f"    Phone             : {a.phone or '—'}")
    print(f"    Address           : {a.address or '—'}")
    print(f"    Previous school   : {a.previous_school or '—'}")
    print(f"    Predicted GCSEs   : {a.predicted_gcses or '—'}")
    print(f"    Subjects          : "
          f"{', '.join(a.subjects) if a.subjects else '—'}")
    print(f"    Reference         : {a.reference_name or '—'}  "
          f"({a.reference_contact or '—'})")
    print(f"    Source            : {a.application_source}")
    print(f"    Submitted on      : {a.submitted_at}")
    print(f"    Status            : {a.status}")
    if a.offer_type:
        print(f"    Offer             : {a.offer_type}")
        if a.offer_conditions:
            print(f"      Conditions      : {a.offer_conditions}")
    if a.interview_date or a.interviewer or a.interview_notes:
        print(f"    Interview         : "
              f"{a.interview_date or '—'}  with "
              f"{a.interviewer or '—'}")
        if a.interview_notes:
            print(f"      Notes           : {a.interview_notes}")
    if a.decision_by or a.decision_date or a.decision_notes:
        print(f"    Decision          : {a.decision_date or '—'} "
              f"by {a.decision_by or '—'}")
        if a.decision_notes:
            print(f"      Notes           : {a.decision_notes}")
    if a.converted_student_id:
        print(f"    Enrolled student  : {a.converted_student_id}")
    if a.notes:
        print()
        print("    Notes:")
        for line in a.notes.splitlines():
            print(f"      {line}")
    _pause()


def _collect_form(existing: Applicant | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    if is_edit:
        print(f"\n  Editing applicant {existing.applicant_id}")
    payload["first_name"] = _input(
        "First name",
        default=(existing.first_name if is_edit else ""),
        allow_empty=False)
    payload["last_name"] = _input(
        "Last name",
        default=(existing.last_name if is_edit else ""),
        allow_empty=False)
    payload["dob"] = _input(
        "Date of birth (YYYY-MM-DD)",
        default=(existing.dob or "") if is_edit else "")
    payload["email"] = _input(
        "Email",
        default=(existing.email or "") if is_edit else "")
    payload["phone"] = _input(
        "Phone",
        default=(existing.phone or "") if is_edit else "")
    payload["address"] = _input(
        "Address",
        default=(existing.address or "") if is_edit else "")
    payload["previous_school"] = _input(
        "Previous school",
        default=(existing.previous_school or "") if is_edit else "")
    payload["predicted_gcses"] = _input(
        "Predicted GCSEs",
        default=(existing.predicted_gcses or "") if is_edit else "")
    payload["subject_1"] = _pick_subject(
        "Subject 1",
        default=(existing.subject_1 if is_edit else None))
    payload["subject_2"] = _pick_subject(
        "Subject 2",
        default=(existing.subject_2 if is_edit else None))
    payload["subject_3"] = _pick_subject(
        "Subject 3",
        default=(existing.subject_3 if is_edit else None))
    payload["reference_name"] = _input(
        "Reference name",
        default=(existing.reference_name or "") if is_edit else "")
    payload["reference_contact"] = _input(
        "Reference contact",
        default=(existing.reference_contact or "") if is_edit else "")
    payload["application_source"] = _pick_from(
        "Application source", list(SOURCES),
        default=(existing.application_source if is_edit
                  else DEFAULT_SOURCE))
    payload["submitted_at"] = _input(
        "Submitted on (YYYY-MM-DD)",
        default=(existing.submitted_at if is_edit
                  else _date.today().isoformat()),
        allow_empty=False)
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_applicant() -> None:
    print("\n═══ New Applicant ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        a = data.create_applicant(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created applicant {a.applicant_id} "
          f"({a.full_name}, {a.status})")
    _pause()


def edit_applicant() -> None:
    print("\n═══ Edit Applicant ═══")
    try:
        a = _pick_applicant()
        payload = _collect_form(a)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_applicant(a.applicant_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated {a.applicant_id}")
    _pause()


def schedule_interview_flow() -> None:
    print("\n═══ Schedule Interview ═══")
    try:
        a = _pick_applicant()
        date_str = _input("Interview date (YYYY-MM-DD)",
                            default=a.interview_date or "",
                            allow_empty=False)
        interviewer = _input("Interviewer",
                              default=a.interviewer or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.schedule_interview(a.applicant_id,
                                  interview_date=date_str,
                                  interviewer=interviewer or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Interview scheduled for {a.applicant_id} on {date_str}")
    _pause()


def record_interview_flow() -> None:
    print("\n═══ Record Interview Notes ═══")
    try:
        a = _pick_applicant()
        notes = _input("Interview notes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.record_interview(a.applicant_id, interview_notes=notes)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Interview recorded for {a.applicant_id}")
    _pause()


def make_offer_flow() -> None:
    print("\n═══ Make Offer ═══")
    try:
        a = _pick_applicant()
        offer_type = _pick_from(
            "Offer type", list(OFFER_TYPES), default=DEFAULT_OFFER_TYPE)
        conditions = _input("Conditions",
                              default=a.offer_conditions or "")
        decided_by = _input("Decided by",
                              default=a.decision_by or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.make_offer(a.applicant_id, offer_type=offer_type,
                          conditions=conditions or None,
                          decided_by=decided_by or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Offer ({offer_type}) made to {a.applicant_id}")
    _pause()


def accept_offer_flow() -> None:
    print("\n═══ Accept Offer ═══")
    try:
        a = _pick_applicant()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.accept_offer(a.applicant_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {a.applicant_id} accepted offer")
    _pause()


def decline_offer_flow() -> None:
    print("\n═══ Decline Offer ═══")
    try:
        a = _pick_applicant()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.decline_offer(a.applicant_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {a.applicant_id} declined offer")
    _pause()


def reject_flow() -> None:
    print("\n═══ Reject Applicant ═══")
    try:
        a = _pick_applicant()
        decided_by = _input("Decided by")
        notes = _input("Reason / notes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.reject(a.applicant_id,
                     decided_by=decided_by or None,
                     notes=notes or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {a.applicant_id} rejected")
    _pause()


def withdraw_flow() -> None:
    print("\n═══ Withdraw Applicant ═══")
    try:
        a = _pick_applicant()
        notes = _input("Notes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.withdraw(a.applicant_id, notes=notes or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {a.applicant_id} withdrawn")
    _pause()


def convert_flow() -> None:
    print("\n═══ Convert to Student ═══")
    try:
        a = _pick_applicant()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Create a `students` row from {a.applicant_id} "
              f"({a.full_name})? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        updated, sid = data.convert_to_student(a.applicant_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Applicant {a.applicant_id} enrolled as student {sid}")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        a = _pick_applicant()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=a.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(a.applicant_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {a.applicant_id} → {new_status}")
    _pause()


def delete_applicant_flow() -> None:
    print("\n═══ Delete Applicant ═══")
    try:
        a = _pick_applicant()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete applicant {a.applicant_id} ({a.full_name})? "
              f"Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_applicant(a.applicant_id):
        print(f"\n  ✓ Deleted {a.applicant_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Admissions Summary ═══")
    try:
        win = int(_input("Upcoming interview window (days)", default="14"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    summ = data.summary(upcoming_window_days=win)
    print(f"\n  Total applicants     : {summ.total}")
    print(f"  Open                 : {summ.open_count}")
    print(f"  Awaiting decision    : {summ.awaiting_decision}")
    print(f"  Pending offers       : {summ.pending_offers}")
    print(f"  Converted to student : {summ.converted}")
    print(f"  Rejected             : {summ.rejected}")
    print(f"  Upcoming interviews  : {summ.upcoming_interviews}  "
          f"(next {win} days)")
    print("\n  By status:")
    for s in STATUSES:
        n = summ.by_status.get(s, 0)
        if n:
            print(f"    {s:<22} : {n}")
    print("\n  By source:")
    for s in SOURCES:
        n = summ.by_source.get(s, 0)
        if n:
            print(f"    {s:<22} : {n}")
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List All",                 list_all),
    ("List Open",                list_open),
    ("Filter",                   filter_applicants),
    ("View",                     view_applicant),
    ("New Applicant",            new_applicant),
    ("Edit Applicant",           edit_applicant),
    ("─" * 6,                    lambda: None),
    ("Schedule Interview",       schedule_interview_flow),
    ("Record Interview",         record_interview_flow),
    ("Make Offer",               make_offer_flow),
    ("Accept Offer",             accept_offer_flow),
    ("Decline Offer",            decline_offer_flow),
    ("Reject",                   reject_flow),
    ("Withdraw",                 withdraw_flow),
    ("Convert to Student",       convert_flow),
    ("Change Status",            set_status_flow),
    ("─" * 6,                    lambda: None),
    ("Delete Applicant",         delete_applicant_flow),
    ("Summary",                  summary_flow),
]


def run() -> None:
    while True:
        print("\n── Admissions ──")
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
            logger.exception("Admissions CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Admissions":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Admissions CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
