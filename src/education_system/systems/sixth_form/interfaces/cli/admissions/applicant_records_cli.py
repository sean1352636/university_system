"""Admissions CLI: list, view, create, edit, delete/archive applicants; presets."""

from __future__ import annotations

from datetime import date as _date
from datetime import timedelta as _timedelta
from typing import Any, Callable
from education_system.systems.sixth_form.domain.admissions import (
    admissions as data,
    applicant_details as details,
    record_safety,
)
from education_system.systems.sixth_form.domain.admissions import (
    applicant_reports as reports,
)
from education_system.systems.sixth_form.domain.admissions.admissions import (
    Applicant,
    DEFAULT_SOURCE,
    DEFAULT_STATUS,
    SOURCES,
    STATUSES,
    ValidationError,
)
from education_system.systems.sixth_form.interfaces.cli.admissions._common import (
    _UserAbort,
    _age,
    _days_in_stage,
    _input,
    _input_validated,
    _pause,
    _pick_applicant,
    _pick_from,
    _pick_subject,
    _print_applicants,
    _yes,
    _attempt,
    _cli_user,
)



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
        intake = _input("Intake year (e.g. 2026/27)") or None
        archived_raw = _input("Include archived? (y/n)", default="n")
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
            intake_year=intake,
            include_archived=archived_raw.lower() in ("y", "yes"),
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
    print(f"    Intake year       : {a.intake_year or '—'}"
          + (f"   (deferred from {a.deferred_from})" if a.deferred_from
             else ""))
    print(f"    Funding           : {details.funding_eligibility(a)}")
    if a.withdrawal_reason:
        print(f"    Withdrawal reason : {a.withdrawal_reason}")
    if a.merged_into:
        print(f"    MERGED into       : {a.merged_into}")
    elif a.is_archived:
        print(f"    ARCHIVED          : {a.archived_at} by "
              f"{a.archived_by or '—'} — {a.archive_reason or ''}")
    concern = reports.gcse_concern(a.predicted_gcses, a.offer_conditions)
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
    if is_edit:
        # Only the moves the workflow allows from here (or stay put).
        options = [existing.status] + [
            s for s in data.allowed_statuses(existing.applicant_id)
            if s != existing.status]
        payload["status"] = _pick_from("Status", options,
                                       default=existing.status)
    else:
        payload["status"] = _pick_from(
            "Status", list(data.INITIAL_STATUSES), default=DEFAULT_STATUS)
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
    a = create_with_duplicate_check(payload)
    if a is None:
        _pause()
        return
    print(f"\n  ✓ Created applicant {a.applicant_id} "
          f"({a.full_name}, {a.status})")
    _pause()


def create_with_duplicate_check(payload: dict[str, Any]) -> Applicant | None:
    """Create the applicant; on a possible duplicate show the matches and
    create only when the user confirms it is a different person."""
    try:
        return data.create_applicant(payload)
    except data.PossibleDuplicate as dup:
        print(f"\n  ⚠ {len(dup.matches)} possible duplicate(s):")
        for d in dup.matches:
            print(f"      {d.applicant_id} — {d.full_name} "
                  f"({d.email or 'no email'}, DOB {d.dob or '—'}) "
                  f"[{d.status}]")
        if not _yes("  This is a different person — create anyway?"):
            print("\n  Cancelled (nothing created).")
            return None
        ok, a = _attempt(data.create_applicant, payload,
                         allow_duplicate=True)
        return a if ok else None
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        return None


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
    try:
        if data.delete_applicant(a.applicant_id):
            print(f"\n  ✓ Deleted {a.applicant_id}")
    except data.HasHistory as e:
        print(f"\n  ✗ {e}")
        if _yes("  Archive it instead (kept, hidden from lists, "
                "restorable)?", default="y"):
            _archive(a)
    _pause()


def _archive(a: Applicant) -> None:
    reason = _input("Reason for archiving", allow_empty=False)
    ok, _ = _attempt(record_safety.archive_applicant, a.applicant_id,
                     reason=reason)
    if ok:
        print(f"  ✓ {a.applicant_id} archived (restore it from "
              "'Archived applicants').")


def archive_applicant_flow() -> None:
    print("\n═══ Archive Applicant ═══")
    a = _pick_applicant()
    blockers = record_safety.delete_blockers(a)
    if blockers:
        print("  Kept because: " + "; ".join(blockers))
    _archive(a)
    _pause()


def _pick_archived() -> Applicant:
    rows = record_safety.list_archived()
    if not rows:
        print("    No archived applicants.")
        raise _UserAbort
    labels = [f"{a.applicant_id}  {a.full_name[:24]:<24} [{a.status}]"
              + (f" merged into {a.merged_into}" if a.merged_into else
                 f" archived {(a.archived_at or '')[:10]}")
              for a in rows]
    return rows[labels.index(_pick_from("Archived applicant", labels))]


def list_archived_flow() -> None:
    print("\n═══ Archived Applicants ═══")
    rows = record_safety.list_archived()
    if not rows:
        print("  (none)")
    for a in rows:
        print(f"    {a.applicant_id}  {a.full_name[:24]:<24} [{a.status}]  "
              f"{(a.archived_at or '')[:16]} by {a.archived_by or '—'}"
              + (f"  → merged into {a.merged_into}" if a.merged_into
                 else f"  — {a.archive_reason or ''}"))
    _pause()


def restore_applicant_flow() -> None:
    print("\n═══ Restore Archived Applicant ═══")
    a = _pick_archived()
    if not _yes(f"Restore {a.applicant_id} ({a.full_name}) to the live "
                "lists?", default="y"):
        raise _UserAbort
    ok, _ = _attempt(record_safety.restore_applicant, a.applicant_id)
    if ok:
        print(f"  ✓ {a.applicant_id} restored by {_cli_user() or 'you'}.")
    _pause()


def summary_flow() -> None:
    print("\n═══ Admissions Summary ═══")
    try:
        win = int(_input("Upcoming interview window (days)", default="14"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    summ = reports.summary(upcoming_window_days=win)
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
