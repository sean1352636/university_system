"""CLI flows for Sixth Form Admissions."""

from __future__ import annotations

import json
import logging
from datetime import date as _date
from datetime import timedelta as _timedelta
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.students.admissions import (
    admissions as data,
)
from education_system.sixthform_system.modules.domain.students.admissions.admissions import (
    Applicant,
    DECISION_REASONS,
    DEFAULT_OFFER_TYPE,
    DEFAULT_SOURCE,
    DEFAULT_STATUS,
    DOCUMENT_TYPES,
    OFFER_TYPES,
    RECOMMENDATIONS,
    REFERENCE_STATUSES,
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


def _input_validated(prompt: str, validator: Callable[[Any], Any], *,
                     default: str = "") -> str:
    """Prompt, re-prompting until the domain validator accepts (item 19)."""
    while True:
        val = _input(prompt, default=default)
        try:
            validator(val)
            return val
        except ValidationError as e:
            print(f"    ✗ {e} — try again (or 'cancel').")


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


def _yes(prompt: str, *, default: str = "no") -> bool:
    return _input(f"{prompt} (y/n)", default=default).lower() in (
        "y", "yes")


def _pick_many_applicants() -> list[Applicant]:
    """Pick several applicants by comma-separated indices and/or ids."""
    rows = data.list_applicants()
    if not rows:
        print("    No applicants.")
        raise _UserAbort
    print("\n  Applicants:")
    for i, a in enumerate(rows, 1):
        print(f"    {i:>3}) {a.applicant_id}  {a.full_name[:24]:<24}  "
              f"[{a.status}]")
    raw = _input("  Pick numbers/ids (comma-separated)", allow_empty=False)
    picked: dict[str, Applicant] = {}
    for tok in raw.replace(" ", "").split(","):
        if not tok:
            continue
        if tok.isdigit() and 1 <= int(tok) <= len(rows):
            a = rows[int(tok) - 1]
            picked[a.applicant_id] = a
        else:
            m = next((a for a in rows
                       if a.applicant_id.lower() == tok.lower()), None)
            if m:
                picked[m.applicant_id] = m
    if not picked:
        print("    Nothing matched.")
        raise _UserAbort
    return list(picked.values())


def _pick_grade(label: str) -> str:
    grades = ["A*", "A", "B", "C", "D", "E",
              "9", "8", "7", "6", "5", "4"]
    return _pick_from(label, grades)


def _age(dob: str | None) -> int | None:
    if not dob:
        return None
    try:
        d = _date.fromisoformat(dob[:10])
    except ValueError:
        return None
    t = _date.today()
    years = t.year - d.year - ((t.month, t.day) < (d.month, d.day))
    return years if 0 <= years < 130 else None


def _days_in_stage(a: Applicant) -> int | None:
    try:
        d = _date.fromisoformat((a.updated_at or "")[:10])
    except ValueError:
        return None
    return max(0, (_date.today() - d).days)


# ── Print helpers ──────────────────────────────────────────────────

def _print_applicants(rows: list[Applicant], *, sort_by: str = "") -> None:
    if not rows:
        print("\n  (no applicants)")
        return
    rows = _sort_rows(rows, sort_by) if sort_by else rows
    print()
    print(f"  {'ID':<10}  {'Name':<22}  {'Age':>3}  {'Submitted':<10}  "
          f"{'Days':>4}  {'Status':<20}  Subjects")
    print("  " + "-" * 108)
    for a in rows:
        subj = ", ".join(a.subjects)[:28]
        age = _age(a.dob)
        days = _days_in_stage(a)
        flag = "!" if (a.is_open and days is not None and days >= 14) else " "
        print(f"  {a.applicant_id:<10}  {a.full_name[:22]:<22}  "
              f"{(str(age) if age is not None else '—'):>3}  "
              f"{a.submitted_at:<10}  "
              f"{(str(days) if days is not None else '—'):>3}{flag}  "
              f"{a.status:<20}  {subj}")
    # Status-count footer (item 10).
    counts: dict[str, int] = {}
    for a in rows:
        counts[a.status] = counts.get(a.status, 0) + 1
    tally = " · ".join(f"{counts[s]} {s}" for s in STATUSES if s in counts)
    print(f"\n  {len(rows)} shown  —  {tally}")


_SORT_KEYS: dict[str, Callable[[Applicant], Any]] = {
    "id": lambda a: a.applicant_id,
    "name": lambda a: a.full_name.lower(),
    "age": lambda a: _age(a.dob) if _age(a.dob) is not None else -1,
    "submitted": lambda a: a.submitted_at or "",
    "days": lambda a: _days_in_stage(a) if _days_in_stage(a)
    is not None else -1,
    "status": lambda a: a.status,
}


def _sort_rows(rows: list[Applicant], key: str) -> list[Applicant]:
    reverse = key.startswith("-")
    name = key.lstrip("-")
    fn = _SORT_KEYS.get(name)
    if fn is None:
        return rows
    return sorted(rows, key=fn, reverse=reverse)


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
        subject = _input("Subject contains") or None
        search = _input("Search (id/name/email)") or None
        date_from = _input("Submitted from (YYYY-MM-DD)") or None
        date_to = _input("Submitted to (YYYY-MM-DD)") or None
        open_raw = _input("Open only? (y/n)", default="n")
        offer_raw = _input("Has offer? (y/n)", default="n")
        enrolled_raw = _input("Enrolled only? (y/n)", default="n")
        sort_by = _input("Sort by (id/name/age/submitted/days/status; "
                          "prefix '-' for desc)") or ""
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_applicants(
            status=status, source=source, search=search,
            date_from=date_from, date_to=date_to,
            open_only=open_raw.lower() in ("y", "yes"),
            has_offer=offer_raw.lower() in ("y", "yes"),
            enrolled_only=enrolled_raw.lower() in ("y", "yes"),
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    if subject:
        rows = [a for a in rows
                if any(subject.lower() in s.lower() for s in a.subjects)]
    _print_applicants(rows, sort_by=sort_by)
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
    age = _age(a.dob)
    if age is not None:
        print(f"    Age               : {age}")
    print(f"    Reference         : {a.reference_name or '—'}  "
          f"({a.reference_contact or '—'})  [{a.reference_status}]")
    print(f"    Source            : {a.application_source}")
    print(f"    Submitted on      : {a.submitted_at}")
    print(f"    Status            : {a.status}"
          + (f"   (waitlist rank {a.waitlist_rank})"
             if a.waitlist_rank else ""))
    days = _days_in_stage(a)
    if days is not None:
        print(f"    Days in stage     : {days}")
    if a.follow_up:
        print("    Follow-up         : FLAGGED")
    if a.offer_type:
        print(f"    Offer             : {a.offer_type}"
              + (f"   expires {a.offer_expiry}" if a.offer_expiry else ""))
        if a.offer_conditions:
            print(f"      Conditions      : {a.offer_conditions}")
    if a.interview_date or a.interviewer or a.interview_notes:
        print(f"    Interview         : "
              f"{a.interview_date or '—'}  with "
              f"{a.interviewer or '—'}")
        if a.interview_notes:
            print(f"      Notes           : {a.interview_notes}")
    score = data.get_interview_score(a.applicant_id)
    if score:
        print(f"    Scorecard         : motivation {score.motivation or '—'}"
              f" · subject-fit {score.subject_fit or '—'}"
              f" · attainment {score.attainment or '—'}"
              f"  → avg {score.average if score.average is not None else '—'}"
              f"  (rec: {score.recommendation or '—'})")
    if a.decision_by or a.decision_date or a.decision_notes \
            or a.decision_reason:
        print(f"    Decision          : {a.decision_date or '—'} "
              f"by {a.decision_by or '—'}")
        if a.decision_reason:
            print(f"      Reason          : {a.decision_reason}")
        if a.decision_notes:
            print(f"      Notes           : {a.decision_notes}")
    if a.converted_student_id:
        print(f"    Enrolled student  : {a.converted_student_id}")
    concern = data.gcse_concern(a.predicted_gcses, a.offer_conditions)
    if concern:
        print(f"\n    ⚠ GCSE check      : {concern}")
    if a.notes:
        print()
        print("    Notes:")
        for line in a.notes.splitlines():
            print(f"      {line}")
    _pause()


def _input_required_validated(prompt: str, validator: Callable[[Any], Any], *,
                              default: str = "") -> str:
    """Prompt until a non-blank value also passes the domain validator."""
    while True:
        val = _input(prompt, default=default, allow_empty=False)
        try:
            validator(val)
            return val
        except ValidationError as e:
            print(f"    ✗ {e} — try again (or 'cancel').")


def _reprompt_field(key: str, label: str,
                    existing: Applicant | None) -> Any:
    """Re-ask for a single required field, guaranteeing a valid, non-blank
    value. Dispatches by field type (if/elif)."""
    default = (getattr(existing, key, None) or "") if existing else ""
    if key in ("subject_1", "subject_2", "subject_3"):
        while True:
            val = _pick_subject(label, default=default or None)
            if val:
                return val
            print("    This subject is required.")
    elif key == "application_source":
        return _pick_from("Application source", list(SOURCES),
                           default=default or DEFAULT_SOURCE)
    elif key == "email":
        return _input_required_validated(label, data._validate_email,
                                          default=default)
    elif key == "phone":
        return _input_required_validated(label, data._validate_phone,
                                          default=default)
    elif key in ("dob", "submitted_at"):
        return _input_required_validated(
            f"{label} (YYYY-MM-DD)",
            lambda v: data._validate_date(v, label), default=default)
    else:
        return _input(label, default=default, allow_empty=False)


def _ensure_complete(payload: dict[str, Any],
                     existing: Applicant | None) -> None:
    """Block until every required field is filled, listing all that remain."""
    while True:
        missing = data.missing_required(payload)
        if not missing:
            return
        print(f"\n  ⚠ Required field(s) still missing: "
              f"{', '.join(missing)}")
        for key, label in data.REQUIRED_FIELDS:
            if label in missing:
                payload[key] = _reprompt_field(key, label, existing)


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
    payload["dob"] = _input_validated(
        "Date of birth (YYYY-MM-DD)",
        lambda v: data._validate_date(v, "Date of birth"),
        default=(existing.dob or "") if is_edit else "")
    payload["email"] = _input_validated(
        "Email", data._validate_email,
        default=(existing.email or "") if is_edit else "")
    payload["phone"] = _input_validated(
        "Phone", data._validate_phone,
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
    # Block submission until every required field is present (lists all).
    _ensure_complete(payload, existing)
    return payload


def new_applicant() -> None:
    print("\n═══ New Applicant ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    # Duplicate detection (item 15).
    dups = data.find_duplicates(
        email=payload.get("email") or None,
        first_name=payload.get("first_name"),
        last_name=payload.get("last_name"),
        dob=payload.get("dob") or None)
    if dups:
        print(f"\n  ⚠ {len(dups)} possible duplicate(s):")
        for d in dups:
            print(f"      {d.applicant_id} — {d.full_name} "
                  f"({d.email or 'no email'})")
        if not _yes("  Create anyway?"):
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


def _build_conditions(a: Applicant) -> str:
    """Structured per-subject grade builder (item 29)."""
    parts: list[str] = []
    subjects = a.subjects or []
    for i in range(max(3, len(subjects))):
        default = subjects[i] if i < len(subjects) else ""
        subj = _input(f"Condition subject {i + 1} (blank to stop)",
                       default=default)
        if not subj:
            break
        grade = _pick_grade(f"Minimum grade for {subj}")
        parts.append(f"{subj} grade {grade} or above")
    return "; ".join(parts)


def make_offer_flow() -> None:
    print("\n═══ Make Offer ═══")
    try:
        a = _pick_applicant()
        offer_type = _pick_from(
            "Offer type", list(OFFER_TYPES), default=DEFAULT_OFFER_TYPE)
        if _yes("Build conditions from subjects + grades?"):
            conditions = _build_conditions(a)
            print(f"    Conditions: {conditions or '(none)'}")
        else:
            conditions = _input("Conditions",
                                  default=a.offer_conditions or "")
        decided_by = _input("Decided by", default=a.decision_by or "")
        expiry = _input("Offer expiry (YYYY-MM-DD, blank to skip)",
                         default=a.offer_expiry
                         or (_date.today()
                             + _timedelta(days=28)).isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.make_offer(a.applicant_id, offer_type=offer_type,
                          conditions=conditions or None,
                          decided_by=decided_by or None)
        if expiry:
            data.set_offer_expiry(a.applicant_id, expiry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Offer ({offer_type}) made to {a.applicant_id}"
          + (f", expires {expiry}" if expiry else ""))
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
        reason = _pick_from("Reason code", list(DECISION_REASONS))
        decided_by = _input("Decided by")
        notes = _input("Notes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.record_decision(a.applicant_id, "Rejected", reason=reason,
                              decided_by=decided_by or None,
                              notes=notes or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {a.applicant_id} rejected ({reason})")
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
    # Pre-conversion checklist (items 37, 40).
    issues = data.pre_conversion_check(a.applicant_id)
    print("\n  Pre-conversion checklist:")
    if issues:
        for iss in issues:
            print(f"    ✗ {iss}")
        print("\n  Not ready to enrol.")
        _pause()
        return
    print("    ✓ Status is 'Offer Accepted'")
    print("    ✓ Three subjects selected")
    print("    ✓ Email on file")
    print("    ✓ Offer not expired")
    if _input(f"\n  Create a `students` row from {a.applicant_id} "
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


# ── Presets & reports (items 3, 4, 9) ─────────────────────────────

def preset_awaiting() -> None:
    print("\n═══ Awaiting Decision ═══")
    rows = [a for a in data.list_applicants()
            if a.status in ("Under Review", "Interviewed")]
    _print_applicants(rows, sort_by="days")
    _pause()


def preset_offers_outstanding() -> None:
    print("\n═══ Offers Outstanding ═══")
    _print_applicants(data.list_applicants(status="Offer Made"),
                       sort_by="submitted")
    _pause()


def preset_interviews_this_week() -> None:
    print("\n═══ Interviews This Week ═══")
    today = _date.today()
    end = (today + _timedelta(days=7)).isoformat()
    rows = [a for a in data.list_applicants()
            if a.interview_date
            and today.isoformat() <= a.interview_date[:10] <= end]
    _print_applicants(rows, sort_by="submitted")
    _pause()


def stale_report() -> None:
    print("\n═══ Overdue / Stale Applicants (open ≥14 days in stage) ═══")
    rows = [a for a in data.list_applicants(open_only=True)
            if (_days_in_stage(a) or 0) >= 14]
    _print_applicants(rows, sort_by="-days")
    _pause()


# ── Bulk actions (items 2, 39) ────────────────────────────────────

def bulk_status_flow() -> None:
    print("\n═══ Bulk Change Status ═══")
    try:
        picks = _pick_many_applicants()
        new_status = _pick_from("New status for all", list(STATUSES))
    except _UserAbort:
        print("\n  Cancelled.")
        return
    ok, fail = 0, []
    for a in picks:
        try:
            data.set_status(a.applicant_id, new_status)
            ok += 1
        except Exception as e:  # noqa: BLE001
            fail.append(f"{a.applicant_id}: {e}")
    print(f"\n  ✓ {ok} updated → {new_status}")
    for f in fail:
        print(f"  ✗ {f}")
    _pause()


def bulk_enrol_flow() -> None:
    print("\n═══ Bulk Enrol Accepted Offers ═══")
    accepted = data.list_applicants(status="Offer Accepted")
    if not accepted:
        print("\n  No applicants in 'Offer Accepted'.")
        _pause()
        return
    if not _yes(f"Attempt to enrol {len(accepted)} accepted applicant(s)?"):
        print("\n  Cancelled.")
        return
    done, skipped = [], []
    for a in accepted:
        issues = data.pre_conversion_check(a.applicant_id)
        if issues:
            skipped.append(f"{a.applicant_id}: {issues[0]}")
            continue
        try:
            _, sid = data.convert_to_student(a.applicant_id)
            done.append(f"{a.applicant_id} → {sid}")
        except Exception as e:  # noqa: BLE001
            skipped.append(f"{a.applicant_id}: {e}")
    print(f"\n  ✓ Enrolled {len(done)}:")
    for d in done:
        print(f"      {d}")
    if skipped:
        print("  Skipped:")
        for s in skipped:
            print(f"      {s}")
    _pause()


# ── Per-applicant operations (items 12–20, 38, 49, 50) ────────────

def timeline_flow(a: Applicant) -> None:
    print(f"\n═══ Timeline — {a.applicant_id} ═══")
    events = data.list_events(a.applicant_id)
    if not events:
        print("  (no events)")
    for e in events:
        print(f"    {e.at}  [{e.kind}]  {e.detail}")
    _pause()


def notes_flow(a: Applicant) -> None:
    print(f"\n═══ Notes — {a.applicant_id} ═══")
    for n in data.list_notes(a.applicant_id):
        print(f"    {n.at}  —  {n.author or 'unknown'}")
        print(f"      {n.body}")
    if _yes("\n  Add a note?"):
        author = _input("Author")
        body = _input("Note", allow_empty=False)
        data.add_note(a.applicant_id, body, author=author or None)
        print("  ✓ Note added.")
    _pause()


def documents_flow(a: Applicant) -> None:
    while True:
        print(f"\n═══ Documents — {a.applicant_id} ═══")
        docs = data.list_documents(a.applicant_id)
        for d in docs:
            print(f"    {d.id:>4})  [{d.doc_type}]  {d.label or '—'}")
            print(f"           {d.path}")
        if not docs:
            print("  (no documents)")
        choice = _input("\n  (a)dd, (r)emove, or Enter to go back",
                         default="")
        if choice.lower() == "a":
            try:
                path = _input("File path", allow_empty=False)
                doc_type = _pick_from("Type", list(DOCUMENT_TYPES))
                label = _input("Label (optional)")
                data.add_document(a.applicant_id, path, doc_type=doc_type,
                                  label=label or None)
                print("  ✓ Document attached.")
            except (ValidationError, _UserAbort) as e:
                print(f"  ✗ {e}")
        elif choice.lower() == "r":
            did = _input("Document id to remove", allow_empty=False)
            if did.isdigit() and data.remove_document(int(did)):
                print("  ✓ Removed.")
            else:
                print("  ✗ Not found.")
        else:
            return


def reference_flow(a: Applicant) -> None:
    print(f"\n═══ Reference — {a.applicant_id} ═══")
    print(f"    Referee : {a.reference_name or '—'} "
          f"({a.reference_contact or '—'})")
    print(f"    Status  : {a.reference_status}")
    print("\n    1) Set status   2) Chase referee   Enter) back")
    choice = _input("  Select", default="")
    if choice == "1":
        new = _pick_from("Reference status", list(REFERENCE_STATUSES),
                          default=a.reference_status)
        data.set_reference_status(a.applicant_id, new)
        print(f"  ✓ Reference status → {new}")
    elif choice == "2":
        if not a.reference_contact:
            print("  ✗ No referee contact on file.")
        else:
            data.set_reference_status(a.applicant_id, "Requested")
            print(f"\n  Reminder to {a.reference_name or 'referee'} "
                  f"({a.reference_contact}):")
            print(f"    We are still awaiting your reference for "
                  f"{a.full_name}. Status set to 'Requested'.")
    _pause()


def _capture_scorecard(a: Applicant) -> dict[str, Any]:
    existing = data.get_interview_score(a.applicant_id)

    def grade(attr: str) -> str:
        cur = getattr(existing, attr) if existing else None
        return _input(f"{attr.replace('_', ' ').title()} (1-5, blank=skip)",
                       default=str(cur) if cur else "")
    rec = _pick_from("Recommendation", ["(skip)"] + list(RECOMMENDATIONS))
    return {
        "motivation": grade("motivation") or None,
        "subject_fit": grade("subject_fit") or None,
        "attainment": grade("attainment") or None,
        "recommendation": None if rec == "(skip)" else rec,
        "scored_by": _input("Scored by") or None,
        "comments": _input("Comments") or None,
    }


def scorecard_flow(a: Applicant) -> None:
    print(f"\n═══ Interview Scorecard — {a.applicant_id} ═══")
    score = data.get_interview_score(a.applicant_id)
    if score:
        print(f"    Current avg: {score.average}  "
              f"(rec: {score.recommendation or '—'})")
    try:
        vals = _capture_scorecard(a)
        data.save_interview_score(a.applicant_id, **vals)
    except (ValidationError, _UserAbort) as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print("  ✓ Scorecard saved.")
    _pause()


def gcse_check_flow(a: Applicant) -> None:
    print(f"\n═══ GCSE Check — {a.applicant_id} ═══")
    print(f"    Predicted  : {a.predicted_gcses or '—'}")
    print(f"    Conditions : {a.offer_conditions or '—'}")
    concern = data.gcse_concern(a.predicted_gcses, a.offer_conditions)
    print(f"\n    {'⚠ ' + concern if concern else '✓ No obvious concern.'}")
    _pause()


def offer_letter_flow(a: Applicant) -> None:
    print(f"\n═══ Offer Letter — {a.applicant_id} ═══")
    if not a.offer_type:
        print("  ✗ No offer has been made yet.")
        _pause()
        return
    letter = data.render_offer_letter(a.applicant_id)
    print("\n" + "\n".join("    " + ln for ln in letter.splitlines()))
    if _yes("\n  Save to file?"):
        path = _input("Path", default=f"offer_{a.applicant_id}.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(letter)
        print(f"  ✓ Saved to {path}")
    _pause()


def email_flow(a: Applicant) -> None:
    print(f"\n═══ Email — {a.applicant_id} ═══")
    subject, body = data.render_status_email(a.applicant_id)
    print(f"\n    Subject: {subject}\n")
    for ln in body.splitlines():
        print(f"    {ln}")
    if _yes("\n  Save to file?"):
        path = _input("Path", default=f"email_{a.applicant_id}.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"Subject: {subject}\n\n{body}")
        print(f"  ✓ Saved to {path}")
    _pause()


def open_student_flow(a: Applicant) -> None:
    print(f"\n═══ Linked Student — {a.applicant_id} ═══")
    if not a.converted_student_id:
        print("  ✗ This applicant has not been enrolled.")
        _pause()
        return
    from education_system.sixthform_system.modules.domain.students.students import (  # noqa: E501
        students as _students,
    )
    st = _students.get_student(a.converted_student_id)
    if st is None:
        print(f"  ✗ Student {a.converted_student_id} not found.")
    else:
        print(f"    Student ID : {st.student_id}")
        print(f"    Name       : {st.first_name} {st.last_name}")
        print(f"    Email      : {getattr(st, 'email', '—')}")
        print(f"    Subjects   : {getattr(st, 'subject_1', '—')}, "
              f"{getattr(st, 'subject_2', '—')}, "
              f"{getattr(st, 'subject_3', '—')}")
    _pause()


def find_duplicates_flow(a: Applicant) -> None:
    print(f"\n═══ Possible Duplicates — {a.applicant_id} ═══")
    dups = data.find_duplicates(email=a.email, first_name=a.first_name,
                                 last_name=a.last_name, dob=a.dob,
                                 exclude_id=a.applicant_id)
    if not dups:
        print("  ✓ None found.")
    for d in dups:
        print(f"    {d.applicant_id} — {d.full_name} "
              f"({d.email or 'no email'})")
    _pause()


def follow_up_flow(a: Applicant) -> None:
    new = not a.follow_up
    data.set_follow_up(a.applicant_id, new)
    print(f"\n  ✓ Follow-up flag {'set' if new else 'cleared'} for "
          f"{a.applicant_id}")
    _pause()


def manage_subjects_flow(a: Applicant) -> None:
    print(f"\n═══ Subjects — {a.applicant_id} ═══")
    subs = list(a.subjects)
    print(f"    Current: {', '.join(subs) if subs else '—'}")
    new = [
        _pick_subject("Subject 1", default=a.subject_1),
        _pick_subject("Subject 2", default=a.subject_2),
        _pick_subject("Subject 3", default=a.subject_3),
    ]
    try:
        data.update_applicant(a.applicant_id, {
            "subject_1": new[0], "subject_2": new[1], "subject_3": new[2]})
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print("  ✓ Subjects updated.")
    _pause()


def gdpr_export_flow(a: Applicant) -> None:
    print(f"\n═══ GDPR Export — {a.applicant_id} ═══")
    payload = json.dumps(data.gdpr_export(a.applicant_id), indent=2,
                          default=str)
    path = _input("Save JSON to path",
                   default=f"gdpr_{a.applicant_id}.json")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(payload)
    print(f"  ✓ Exported to {path}")
    _pause()


def gdpr_erase_flow(a: Applicant) -> None:
    print(f"\n═══ GDPR Erase — {a.applicant_id} ═══")
    print("  This permanently deletes the applicant and ALL related "
          "records/files.")
    if _input("  Type 'ERASE' to confirm", default="") != "ERASE":
        print("  Cancelled.")
        return
    data.erase_applicant(a.applicant_id)
    print(f"  ✓ All data for {a.applicant_id} erased.")
    _pause()


# ── Per-applicant action menu (item 7 — context-menu analogue) ────

def applicant_actions_flow() -> None:
    print("\n═══ Applicant Actions ═══")
    try:
        a = _pick_applicant()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    actions: list[tuple[str, Callable[[], None]]] = [
        ("View record",        lambda: _view_inline(_fresh(a))),
        ("Timeline",           lambda: timeline_flow(_fresh(a))),
        ("Notes",              lambda: notes_flow(_fresh(a))),
        ("Documents / photo",  lambda: documents_flow(_fresh(a))),
        ("Reference status",   lambda: reference_flow(_fresh(a))),
        ("Interview scorecard", lambda: scorecard_flow(_fresh(a))),
        ("GCSE check",         lambda: gcse_check_flow(_fresh(a))),
        ("Manage subjects",    lambda: manage_subjects_flow(_fresh(a))),
        ("Toggle follow-up",   lambda: follow_up_flow(_fresh(a))),
        ("Offer letter",       lambda: offer_letter_flow(_fresh(a))),
        ("Email applicant",    lambda: email_flow(_fresh(a))),
        ("Open student record", lambda: open_student_flow(_fresh(a))),
        ("Find duplicates",    lambda: find_duplicates_flow(_fresh(a))),
        ("GDPR export",        lambda: gdpr_export_flow(_fresh(a))),
        ("GDPR erase",         lambda: gdpr_erase_flow(_fresh(a))),
    ]
    _run_submenu(f"Actions — {a.applicant_id} {a.full_name}", actions)


def _fresh(a: Applicant) -> Applicant:
    """Re-read the applicant so each action sees the latest state."""
    return data.get_applicant(a.applicant_id) or a


def _view_inline(a: Applicant) -> None:
    print()
    print(f"    {a.applicant_id}  {a.full_name}  [{a.status}]")
    print(f"    Email {a.email or '—'} · Phone {a.phone or '—'} · "
          f"Age {_age(a.dob) if _age(a.dob) is not None else '—'}")
    print(f"    Subjects: {', '.join(a.subjects) or '—'}")
    print(f"    Reference: {a.reference_status} · Follow-up: "
          f"{'yes' if a.follow_up else 'no'}")
    if a.offer_type:
        print(f"    Offer: {a.offer_type} "
              f"(expires {a.offer_expiry or '—'}) — {a.offer_conditions or '—'}")
    _pause()


# ── Interviews (items 21–28) ──────────────────────────────────────

def interviews_agenda_flow() -> None:
    print("\n═══ Interview Agenda ═══")
    rows = [a for a in data.list_applicants() if a.interview_date]
    rows.sort(key=lambda a: (a.interview_date or "",
                              a.interviewer or "", a.full_name))
    if not rows:
        print("  (no scheduled interviews)")
        _pause()
        return
    # Clash detection (item 23): same interviewer + same day.
    from collections import Counter
    slots = Counter((a.interview_date, a.interviewer)
                    for a in rows if a.interviewer)
    clashes = {k for k, n in slots.items() if n > 1}
    current = None
    for a in rows:
        if a.interview_date != current:
            current = a.interview_date
            print(f"\n  ── {a.interview_date} ──")
        flag = "  ⚠CLASH" if (a.interview_date, a.interviewer) in clashes \
            else ""
        print(f"      {a.applicant_id}  {a.full_name[:24]:<24}  "
              f"{a.interviewer or '—':<16}  [{a.status}]{flag}")
    # Interviewer workload (item 22).
    print("\n  Interviewer load:")
    load = Counter(a.interviewer or "(unassigned)" for a in rows)
    for who, n in sorted(load.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"      {who:<20} {n}")
    _pause()


def record_outcome_flow() -> None:
    print("\n═══ Record Interview Outcome ═══")
    try:
        a = _pick_applicant()
        notes = _input("Interview notes", default=a.interview_notes or "")
        do_score = _yes("Add a scorecard?", default="y")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.record_interview(a.applicant_id, interview_notes=notes or None)
        if do_score:
            vals = _capture_scorecard(a)
            data.save_interview_score(a.applicant_id, **vals)
    except (ValidationError, _UserAbort) as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Outcome recorded for {a.applicant_id}")
    _pause()


def reschedule_flow() -> None:
    print("\n═══ Reschedule Interview ═══")
    try:
        a = _pick_applicant()
        new_date = _input("New date (YYYY-MM-DD)",
                           default=a.interview_date or "", allow_empty=False)
        reason = _input("Reason (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    # Clash warning (item 23).
    clash = [x for x in data.list_applicants()
             if x.interviewer and x.interviewer == a.interviewer
             and x.interview_date == new_date
             and x.applicant_id != a.applicant_id]
    if clash and not _yes(
            f"  {a.interviewer} already has "
            f"{', '.join(x.full_name for x in clash)} on {new_date}. "
            f"Proceed?"):
        print("\n  Cancelled.")
        return
    try:
        data.reschedule_interview(a.applicant_id, new_date=new_date,
                                   reason=reason or None,
                                   interviewer=a.interviewer)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Rescheduled {a.applicant_id} to {new_date}")
    _pause()


def cancel_interview_flow() -> None:
    print("\n═══ Cancel Interview ═══")
    try:
        a = _pick_applicant()
        reason = _input("Reason (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    data.cancel_interview(a.applicant_id, reason=reason or None)
    print(f"\n  ✓ Interview cancelled for {a.applicant_id} "
          f"(returned to Under Review)")
    _pause()


def no_show_flow() -> None:
    print("\n═══ Record No-Show ═══")
    try:
        a = _pick_applicant()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    data.mark_no_show(a.applicant_id, follow_up=True)
    print(f"\n  ✓ {a.applicant_id} marked no-show (flagged for follow-up)")
    _pause()


def export_ics_flow() -> None:
    print("\n═══ Export Interview (.ics) ═══")
    try:
        a = _pick_applicant()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        ics = data.interview_to_ics(a.applicant_id)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    path = _input("Save to path", default=f"interview_{a.applicant_id}.ics")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(ics)
    print(f"  ✓ Saved to {path}")
    _pause()


# ── Waitlist & decision day (items 34, 35) ────────────────────────

def waitlist_flow() -> None:
    while True:
        print("\n═══ Waitlist ═══")
        wl = data.get_waitlist()
        if not wl:
            print("  (waitlist empty)")
        for i, a in enumerate(wl, 1):
            print(f"    {i:>2}) rank {a.waitlist_rank or '—':<3}  "
                  f"{a.applicant_id}  {a.full_name[:24]:<24}  "
                  f"{', '.join(a.subjects)[:30]}")
        print("\n    (u)p / (d)own <n>, (o)ffer <n>, (r)emove <n>, "
              "Enter) back")
        raw = _input("  Action", default="")
        if not raw:
            return
        parts = raw.split()
        cmd = parts[0].lower()
        idx = int(parts[1]) - 1 if len(parts) > 1 and parts[1].isdigit() \
            else None
        if cmd in ("u", "d") and idx is not None and 0 <= idx < len(wl):
            data.move_waitlist(wl[idx].applicant_id,
                                -1 if cmd == "u" else 1)
        elif cmd == "o" and idx is not None and 0 <= idx < len(wl):
            make_offer_for(wl[idx])
        elif cmd == "r" and idx is not None and 0 <= idx < len(wl):
            data.set_waitlist_rank(wl[idx].applicant_id, None)
        else:
            print("  ✗ Unrecognised action.")


def make_offer_for(a: Applicant) -> None:
    try:
        offer_type = _pick_from("Offer type", list(OFFER_TYPES),
                                 default=DEFAULT_OFFER_TYPE)
        conditions = _input("Conditions", default=a.offer_conditions or "")
        data.make_offer(a.applicant_id, offer_type=offer_type,
                          conditions=conditions or None)
        print(f"  ✓ Offer made to {a.applicant_id}")
    except (ValidationError, _UserAbort) as e:
        print(f"  ✗ {e}")


def decision_day_flow() -> None:
    print("\n═══ Decision Day (Interviewed queue) ═══")
    queue = data.list_applicants(status="Interviewed")
    if not queue:
        print("  No applicants awaiting a decision.")
        _pause()
        return
    for n, a in enumerate(queue, 1):
        a = data.get_applicant(a.applicant_id)
        if a is None:
            continue
        score = data.get_interview_score(a.applicant_id)
        print(f"\n  [{n}/{len(queue)}] {a.applicant_id} — {a.full_name}")
        print(f"      Subjects: {', '.join(a.subjects) or '—'}")
        print(f"      Predicted: {a.predicted_gcses or '—'}")
        if score:
            print(f"      Scorecard avg {score.average}  "
                  f"(rec: {score.recommendation or '—'})")
        print("      1) Make offer  2) Waitlist  3) Reject  "
              "4) Skip  0) Finish")
        choice = _input("  Decision", default="4")
        decided_by = ""
        try:
            if choice == "0":
                break
            if choice == "1":
                cond = _input("Conditions")
                decided_by = _input("Decided by")
                data.make_offer(a.applicant_id, conditions=cond or None,
                                 decided_by=decided_by or None)
                print("      ✓ Offer made.")
            elif choice == "2":
                data.set_status(a.applicant_id, "Waitlisted")
                data.set_waitlist_rank(a.applicant_id,
                                        len(data.get_waitlist()))
                print("      ✓ Waitlisted.")
            elif choice == "3":
                reason = _pick_from("Reason", list(DECISION_REASONS))
                data.record_decision(a.applicant_id, "Rejected",
                                      reason=reason)
                print("      ✓ Rejected.")
        except (ValidationError, _UserAbort) as e:
            print(f"      ✗ {e}")
    print("\n  Decision day complete.")
    _pause()


def expiring_offers_flow() -> None:
    print("\n═══ Expiring Offers ═══")
    try:
        days = int(_input("Within how many days?", default="7"))
    except (ValueError, _UserAbort):
        return
    rows = data.list_expiring_offers(within_days=days)
    if not rows:
        print(f"  No offers expiring within {days} days.")
    for a in rows:
        print(f"    {a.applicant_id}  {a.full_name[:24]:<24}  "
              f"expires {a.offer_expiry}")
    _pause()


# ── Analytics (items 41–46) ───────────────────────────────────────

def analytics_flow() -> None:
    print("\n═══ Admissions Analytics ═══")
    fn = data.funnel()
    top = fn[0][1] if fn else 0
    print("\n  Conversion funnel:")
    for stage, n in fn:
        bar = "█" * (round(30 * n / top) if top else 0)
        pct = f"{round(100 * n / top)}%" if top else "—"
        print(f"    {stage:<20} {n:>4} {pct:>4}  {bar}")

    print("\n  Source effectiveness:")
    print(f"    {'Source':<18}{'Total':>6}{'Offers':>8}"
          f"{'Enrolled':>10}{'Conv%':>8}")
    for d in data.source_effectiveness():
        print(f"    {d['source']:<18}{d['total']:>6}{d['offers']:>8}"
              f"{d['enrolled']:>10}{d['conversion']:>7}%")

    ttd = data.time_to_decision_stats()
    print("\n  Time to decision (days):")
    if ttd["count"]:
        print(f"    n={ttd['count']}  avg={ttd['avg']}  "
              f"median={ttd['median']}  min={ttd['min']}  max={ttd['max']}")
    else:
        print("    (no decisions yet)")

    print("\n  Applications by week:")
    weeks = data.applications_by_week()[-10:]
    wmax = max((n for _, n in weeks), default=0)
    for wk, n in weeks:
        print(f"    {wk:<10} {n:>4} {'█' * (round(20 * n / wmax) if wmax else 0)}")
    if not weeks:
        print("    (none)")

    print("\n  Subject demand:")
    for subj, n in data.subject_demand()[:15]:
        print(f"    {subj:<28} {n:>4}")

    # Drill-down (item 46).
    if _yes("\n  Drill down into a status?"):
        status = _pick_from("Status", list(STATUSES))
        _print_applicants(data.list_applicants(status=status))
    _pause()


# ── CSV import / export (items 47, 48) ────────────────────────────

def export_csv_flow() -> None:
    print("\n═══ Export Applicants to CSV ═══")
    path = _input("Save to path", default="applicants.csv")
    try:
        n = data.export_csv(path)
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"  ✓ Exported {n} applicant(s) to {path}")
    _pause()


def import_csv_flow() -> None:
    print("\n═══ Import Applicants from CSV ═══")
    path = _input("CSV path", allow_empty=False)
    try:
        created, errors = data.import_csv(path)
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"  ✓ Imported {created} applicant(s).")
    for err in errors[:12]:
        print(f"    ✗ {err}")
    if len(errors) > 12:
        print(f"    … and {len(errors) - 12} more.")
    _pause()


# ── Menus ─────────────────────────────────────────────────────────

def _run_submenu(title: str,
                 items: list[tuple[str, Callable[[], None]]]) -> None:
    while True:
        print(f"\n── {title} ──")
        for i, (label, _) in enumerate(items, 1):
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
        if not choice.isdigit() or not (1 <= int(choice) <= len(items)):
            print("  Invalid selection.")
            continue
        label, handler = items[int(choice) - 1]
        if label.startswith("─"):
            continue
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:  # noqa: BLE001
            logger.exception("Admissions CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


_BROWSE_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List All",                 list_all),
    ("List Open",                list_open),
    ("Filter (sort/subject/…)",  filter_applicants),
    ("Preset: Awaiting decision", preset_awaiting),
    ("Preset: Offers outstanding", preset_offers_outstanding),
    ("Preset: Interviews this week", preset_interviews_this_week),
    ("Report: Overdue / stale",  stale_report),
]

_APPLICANT_MENU: list[tuple[str, Callable[[], None]]] = [
    ("View",                     view_applicant),
    ("New Applicant",            new_applicant),
    ("Edit Applicant",           edit_applicant),
    ("Actions… (per applicant)", applicant_actions_flow),
    ("─" * 6,                    lambda: None),
    ("Bulk change status",       bulk_status_flow),
    ("Delete Applicant",         delete_applicant_flow),
]

_INTERVIEW_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Agenda (with clashes/load)", interviews_agenda_flow),
    ("Schedule Interview",       schedule_interview_flow),
    ("Record outcome (+ score)", record_outcome_flow),
    ("Record interview notes",   record_interview_flow),
    ("Reschedule",               reschedule_flow),
    ("Cancel",                   cancel_interview_flow),
    ("No-show",                  no_show_flow),
    ("Export .ics",              export_ics_flow),
]

_OFFER_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Make Offer (+ builder/expiry)", make_offer_flow),
    ("Accept Offer",             accept_offer_flow),
    ("Decline Offer",            decline_offer_flow),
    ("Reject (with reason)",     reject_flow),
    ("Withdraw",                 withdraw_flow),
    ("Change Status",            set_status_flow),
    ("─" * 6,                    lambda: None),
    ("Waitlist (rank/promote)",  waitlist_flow),
    ("Decision day",             decision_day_flow),
    ("Expiring offers",          expiring_offers_flow),
]

_CONVERSION_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Convert to Student (checklist)", convert_flow),
    ("Bulk enrol accepted",      bulk_enrol_flow),
]

_DATA_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Summary",                  summary_flow),
    ("Analytics (funnel/…)",     analytics_flow),
    ("─" * 6,                    lambda: None),
    ("Export CSV",               export_csv_flow),
    ("Import CSV",               import_csv_flow),
]

_MAIN_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Browse & search…",   lambda: _run_submenu("Browse", _BROWSE_MENU)),
    ("Applicants…",        lambda: _run_submenu("Applicants",
                                                 _APPLICANT_MENU)),
    ("Interviews…",        lambda: _run_submenu("Interviews",
                                                 _INTERVIEW_MENU)),
    ("Offers & decisions…", lambda: _run_submenu("Offers & Decisions",
                                                  _OFFER_MENU)),
    ("Conversion…",        lambda: _run_submenu("Conversion",
                                                 _CONVERSION_MENU)),
    ("Reports & data…",    lambda: _run_submenu("Reports & Data",
                                                 _DATA_MENU)),
]


def run() -> None:
    _run_submenu("Admissions", _MAIN_MENU)


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
