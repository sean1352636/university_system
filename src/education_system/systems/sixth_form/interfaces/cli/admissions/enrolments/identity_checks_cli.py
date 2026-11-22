"""CLI: photo and identity-document checks at enrolment.

Only the last four characters of a document number are stored.
"""

from __future__ import annotations

from education_system.systems.sixth_form.domain.admissions import (
    applicant_details as details,
)
from education_system.systems.sixth_form.domain.admissions.enrolments import (
    identity_checks as ic,
)
from education_system.systems.sixth_form.domain.governance.user_management import access
from education_system.systems.sixth_form.interfaces.cli.admissions.enrolments._common import (
    _default_academic_year,
    _offer_csv,
    _prompt_academic_year,
    _input,
    _pause,
    _pick_from,
    _pick_student,
)


def _restricted(value: str | None) -> bool:
    return value == ic.RESTRICTED


def _show(sid: str) -> None:
    c = ic.get_check(sid)
    photo = (f"on file ({c.photo_added_at})" if c and c.has_photo
             else "MISSING")
    ident = (f"{c.id_document_type} ****{c.id_number_last4} checked "
             f"{c.id_checked_on} by {c.id_checked_by}"
             if c and c.id_checked else "NOT CHECKED")
    print(f"\n  {sid}: photo {photo}; ID {ident}")
    if c and any(_restricted(v) for v in (c.right_to_study, c.visa_type,
                                          c.visa_expiry)):
        print("    Right to study / visa: (restricted — needs admissions, "
              "students.manage or safeguarding)")
        c = None
    if c and (c.right_to_study or c.visa_type or c.visa_expiry):
        print(f"    Right to study: {c.right_to_study or '—'}"
              + (f"; visa {c.visa_type or '—'} expires {c.visa_expiry or '—'}"
                 if c.visa_type or c.visa_expiry else "")
              + (f"  (from {c.source})" if c.source else ""))


def view_flow() -> None:
    _show(_pick_student())
    _pause()


def photo_flow() -> None:
    sid = _pick_student()
    path = _input("Photo file path (jpg/png…, max 5 MB)", allow_empty=False)
    try:
        ic.set_photo(sid, path)
        print("  ✓ Photo saved")
    except ValueError as e:
        print(f"  ✗ {e}")
    _pause()


def remove_photo_flow() -> None:
    sid = _pick_student()
    print("  ✓ Photo removed" if ic.remove_photo(sid) else "  No photo on file")
    _pause()


def id_flow() -> None:
    sid = _pick_student()
    doc = _pick_from("Document seen", list(ic.ID_DOCUMENT_TYPES),
                     default="Passport")
    number = _input("Document number (only last 4 kept)", allow_empty=False)
    rts = _pick_from("Right to study", list(details.RIGHT_TO_STUDY),
                     default="Not yet confirmed")
    visa_type = visa_expiry = None
    if rts.startswith("Yes - visa"):
        visa_type = _input("Visa type") or None
        visa_expiry = _input("Visa expiry (YYYY-MM-DD)", allow_empty=False)
    try:
        ic.record_id_check(
            sid, document_type=doc, document_number=number,
            checked_on=_input("Checked on (blank = today)") or None,
            notes=_input("Notes") or None, right_to_study=rts,
            visa_type=visa_type, visa_expiry=visa_expiry)
        print("  ✓ ID check recorded (onboarding item ticked)")
    except ValueError as e:
        print(f"  ✗ {e}")
    _pause()


def history_flow() -> None:
    sid = _pick_student()
    try:
        rows = ic.id_history(sid)
    except access.AccessDenied as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"\n  ID check history — {sid}")
    for h in rows:
        print(f"    {h['id_checked_on'] or h['at'][:10]}  "
              f"{h['id_document_type'] or '—'} ****{h['id_number_last4'] or ''}"
              f"  right to study {h['right_to_study'] or '—'}"
              + (f"  visa to {h['visa_expiry']}" if h["visa_expiry"] else "")
              + f"  by {h['id_checked_by'] or h['recorded_by'] or '—'}"
              + (f"  [{h['source']}]" if h["source"] else ""))
    if not rows:
        print("    (none)")
    _pause()


def outstanding_flow() -> None:
    """Learners with a live enrolment who still have something to do:
    photo, ID check, right to study, visa."""
    year = _prompt_academic_year(_default_academic_year())
    rows = ic.outstanding_detail(year or None)
    names = _names()
    print(f"\n  {len(rows)} enrolled student(s) with checks outstanding")
    for o in rows:
        print(f"    {o.student_id:<12} {names.get(o.student_id, '—')[:22]:<22} "
              + "; ".join(o.problems))
    if rows and any(o.right_to_study == "restricted" for o in rows):
        print("\n  (Right to study / visa details are restricted for your account.)")
    _offer_csv([{"student_id": o.student_id, "name": names.get(o.student_id, ""),
                 "problems": o.problems} for o in rows], "outstanding_checks.csv")
    _pause()


def visa_expiring_flow() -> None:
    """Live learners whose visa has expired or expires soon (needs
    admissions, students.manage or safeguarding; the read is logged)."""
    try:
        from education_system.systems.sixth_form.domain.admissions.enrolments import (
            course_changes,
        )
        default = course_changes.get_setting(course_changes.VISA_WARNING_DAYS)
    except Exception:  # noqa: BLE001 — the module default still works
        default = ic.VISA_WARNING_DAYS
    raw = _input("Expiring within how many days", default=str(default))
    try:
        days = int(raw)
    except ValueError:
        print("  ✗ Enter a whole number of days.")
        _pause()
        return
    try:
        rows = ic.visa_expiring(within_days=days)
    except access.AccessDenied as e:
        print(f"  ✗ {e}")
        _pause()
        return
    names = _names()
    print(f"\n  {len(rows)} learner(s) with a visa expired or expiring within {days} days")
    for r in rows:
        state = (f"EXPIRED {-r.days_left} day(s) ago" if r.expired
                 else f"{r.days_left} day(s) left")
        print(f"    {r.student_id:<12} {names.get(r.student_id, '—')[:22]:<22} "
              f"{r.visa_type or '—':<14} {r.visa_expiry}  {state}")
    _offer_csv(rows, "visa_expiring.csv")
    _pause()


def _names() -> dict[str, str]:
    try:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as student_data,
        )
        return {s.student_id: s.full_name for s in student_data.list_students()}
    except Exception:  # noqa: BLE001 — names are a nicety
        return {}


def list_all_flow() -> None:
    """Every learner with a check record: photo, ID and right to study."""
    rows = ic.list_checks()
    names = {}
    try:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as student_data,
        )
        names = {s.student_id: s.full_name for s in student_data.list_students()}
    except Exception as exc:  # noqa: BLE001 — names are a nicety
        print(f"  (names not loaded: {exc})")
    print(f"\n  {len(rows)} identity check record(s)")
    print(f"    {'Student':<12}{'Name':<24}{'Photo':<7}{'ID document':<28}"
          f"{'Right to study':<20}")
    for c in rows:
        ident = (f"{c.id_document_type} ****{c.id_number_last4} {c.id_checked_on}"
                 if c.id_checked else "not checked")
        visa = f" (visa to {c.visa_expiry})" if c.visa_expiry else ""
        print(f"    {c.student_id:<12}{names.get(c.student_id, '—')[:23]:<24}"
              f"{'✓' if c.has_photo else '✗':<7}{ident[:27]:<28}"
              f"{(c.right_to_study or '—')}"
              f"{'' if _restricted(c.visa_expiry) else visa}")
    if not rows:
        print("    (none)")
    _pause()


MENU = [
    ("View a student's checks", view_flow),
    ("Add / replace photo", photo_flow),
    ("Remove photo", remove_photo_flow),
    ("Record ID document check", id_flow),
    ("Outstanding photo / ID checks", outstanding_flow),
    ("ID check history", history_flow),
    ("List all checks", list_all_flow),
    ("Visas expiring", visa_expiring_flow),
]
