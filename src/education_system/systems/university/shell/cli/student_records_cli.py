"""CLI for the student record: create, edit, transfer, withdraw,
reinstate, change history, erasure requests and the data check.

Every write goes through ``application/students/lifecycle`` (or
``student_erasure`` / ``student_data_quality``), the same rules as the
Student Records window.
"""

from __future__ import annotations

import getpass
import secrets
from contextlib import closing

from education_system.systems.university.application.students import record_rules as rules
from education_system.systems.university.application.students.lifecycle import (
    GENDER_OPTIONS,
    StudentCommand,
    StudentLifecycleService,
    StudentValidationError,
)
from education_system.systems.university.infrastructure.database.db import get_connection


def _actor(auth):
    user = getattr(auth, "current_user", None) or {}
    return str(user.get("username") or user.get("id") or "unknown")


def _key(kind, student_id=""):
    return f"cli:{kind}:{student_id}:{secrets.token_urlsafe(12)}"


def _errors(exc):
    return "; ".join(f"{k}: {v}" for k, v in exc.errors.items())


def _ask(prompt, *, required=False, choices=None, default=""):
    while True:
        hint = f" [{'/'.join(choices)}]" if choices else ""
        hint += f" (default {default})" if default else ""
        value = input(f"{prompt}{hint}: ").strip() or default
        if choices and value:
            match = next((c for c in choices if c.lower() == value.lower()), None)
            if match is None:
                print(f"Choose one of: {', '.join(choices)}")
                continue
            value = match
        if required and not value:
            print("This is required.")
            continue
        return value


def _read(fn, *args, write=False):
    with closing(get_connection(row_factory=False)) as conn:
        result = fn(conn, *args)
        if write:
            conn.commit()
        return result


# ── create ──────────────────────────────────────────────────────────────


def _contact():
    return {
        "preferred_name": _ask("Preferred name (optional)"),
        "phone": _ask("Phone (optional)"),
        "personal_email": _ask("Personal email (optional)"),
        "address_line1": _ask("Address line 1 (optional)"),
        "address_line2": _ask("Address line 2 (optional)"),
        "town": _ask("Town (optional)"),
        "postcode": _ask("Postcode (optional)"),
        "nationality": _ask("Nationality (optional)"),
        "mode_of_study": _ask("Mode of study", choices=rules.MODES, default="full-time"),
        "fee_status": _ask("Fee status", choices=rules.FEE_STATUSES, default="home"),
    }


def _care():
    """Emergency contact (to the health record), medical notes and notes,
    as the other systems' add forms ask. Re-asked until the contact is
    complete or blank."""
    print("\nEmergency contact (name and phone, or leave all blank)")
    while True:
        values = {
            "emergency_contact_name": _ask("  Name"),
            "emergency_contact_phone": _ask("  Phone"),
            "emergency_contact_relationship": _ask(
                "  Relationship", choices=rules.EMERGENCY_RELATIONSHIPS),
        }
        problems = rules.validate_registration(values)
        if not problems:
            break
        print("  " + "; ".join(f"{k.replace('_', ' ')} {v}" for k, v in problems.items()))
    values["medical_notes"] = _ask("Medical notes for the health team (optional)")
    values["notes"] = _ask("Notes (optional)")
    return values


def _entry(select_course_for_applicant, list_courses, pick_course):
    """``(course, route, tariff, qualifications, override)`` or None."""
    routes = list(rules.ENTRY_ROUTES)
    for i, key in enumerate(routes, 1):
        print(f"  {i}. {rules.ENTRY_ROUTES[key]}")
    pick = _ask("Entry route", default="1")
    route = routes[int(pick) - 1] if pick.isdigit() and 0 < int(pick) <= len(routes) else "a_levels"
    if route != "a_levels":
        qualifications = _ask("Qualifications held", required=True)
        course = pick_course(list_courses())
        return (course["code"], route, None, qualifications, "") if course else None
    selection = select_course_for_applicant(allow_override=True)
    if not selection:
        return None
    return (selection["code"], route, selection["tariff"], selection["entry_qualifications"],
            selection.get("override", ""))


def create_student(auth, *, select_course_for_applicant, list_courses, pick_course):
    first = _ask("First name", required=True)
    middle = _ask("Middle name (optional)")
    last = _ask("Last name", required=True)
    gender = _ask("Gender", choices=GENDER_OPTIONS, required=True)
    title = _ask("Title (Mr/Ms/Mrs/Dr/Mx, optional)")
    dob = _ask("Date of birth (YYYY-MM-DD)", required=True)
    details = _contact()
    details.update(_care())
    entry = _entry(select_course_for_applicant, list_courses, pick_course)
    if entry is None:
        print("Student creation cancelled.")
        return None
    course, route, tariff, qualifications, override = entry
    command = StudentCommand(first_name=first, middle_name=middle, last_name=last, title=title,
                             gender=gender, dob=dob, course=course,
                             entry_qualifications=qualifications, ucas_tariff=tariff,
                             entry_route=route, entry_override_reason=override or "", **details)
    lifecycle = StudentLifecycleService()
    created = _create_checked(lifecycle, command, auth)
    if created is None:
        return None
    provisioned = lifecycle.provision(created.student_id, auth=auth)
    if _ask("Is the student on a Student-route visa? (y/n)", default="n").lower() == "y":
        _visa(created.student_id, first, details["nationality"])
    print(f"\nStudent ID: {created.student_id}")
    print("Provisioning pending: " + provisioned.provisioning_error
          if provisioned.provisioning_error else
          "Created and provisioned; an activation link was sent to their university email.")
    return created.student_id


def _create_checked(lifecycle, command, auth):
    from dataclasses import replace
    try:
        return lifecycle.create(command, actor_id=_actor(auth), idempotency_key=_key("create"))
    except StudentValidationError as exc:
        if "duplicate" in exc.errors and _ask(
                f"Possible duplicate: {exc.errors['duplicate']}. Create anyway? (y/n)",
                default="n").lower() == "y":
            return _create_checked(lifecycle, replace(command, allow_duplicate=True), auth)
        print(f"Not created: {_errors(exc)}")
        return None


def _visa(student_id, first_name, nationality):
    from education_system.systems.university.services.student_provisioning import (
        create_visa_record,
    )
    with closing(get_connection(row_factory=False)) as conn:
        email = conn.execute("SELECT email_address FROM students WHERE student_id = ?",
                             (student_id,)).fetchone()
        modules = [r[0] for r in conn.execute(
            "SELECT module_code FROM student_modules WHERE student_id = ?", (student_id,))]
    try:
        create_visa_record(student_id, email[0] if email else None, first_name,
                           nationality or _ask("Nationality"), _ask("Passport number"),
                           _ask("Visa expiry (YYYY-MM-DD)") or None, _ask("BRP number"),
                           modules)
        print("Visa record created (pending the right-to-study check).")
    except Exception as exc:
        print(f"The visa record could not be created: {exc}")


# ── edit, transfer, withdraw, reinstate ─────────────────────────────────

EDITABLE = (("first_name", "First name"), ("middle_name", "Middle name"),
            ("last_name", "Last name"), ("title", "Title"), ("gender", "Gender"),
            ("dob", "Date of birth (YYYY-MM-DD)"), ("pronouns", "Pronouns"),
            ("emergency_contact", "Emergency contact"), ("phone", "Phone"),
            ("personal_email", "Personal email"), ("address_line1", "Address line 1"),
            ("address_line2", "Address line 2"), ("town", "Town"),
            ("postcode", "Postcode"), ("preferred_name", "Preferred name"),
            ("nationality", "Nationality"), ("mode_of_study", "Mode of study"),
            ("fee_status", "Fee status"), ("notes", "Notes"))


def update_student(auth, student_id, *, allowed=None):
    fields = [f for f in EDITABLE if allowed is None or f[0] in allowed]
    for i, (_key_name, label) in enumerate(fields, 1):
        print(f"  {i}. {label}")
    pick = _ask("Field to change", required=True)
    if not pick.isdigit() or not 0 < int(pick) <= len(fields):
        print("Invalid selection.")
        return
    field = fields[int(pick) - 1][0]
    value = _ask("New value (blank clears it)")
    reason = _ask("Reason for the change", required=True)
    try:
        StudentLifecycleService().update(student_id, {field: value or None},
                                         actor_id=_actor(auth), reason=reason,
                                         idempotency_key=_key("update", student_id))
        print("Updated.")
    except StudentValidationError as exc:
        print(f"Not updated: {_errors(exc)}")


def transfer_student(auth, student_id, course, reason=None):
    reason = reason or _ask("Reason for the transfer", required=True)
    try:
        StudentLifecycleService().transfer_course(student_id, course, actor_id=_actor(auth),
                                                  reason=reason,
                                                  idempotency_key=_key("transfer", student_id))
        print(f"{student_id} moved to {course}; old modules kept as 'Transferred'.")
    except StudentValidationError as exc:
        print(f"Not transferred: {_errors(exc)}")


def withdraw_student(auth, student_id):
    reason = _ask("Reason for the withdrawal", required=True)
    try:
        StudentLifecycleService().deactivate(student_id, actor_id=_actor(auth), reason=reason,
                                             idempotency_key=_key("withdraw", student_id))
        print(f"{student_id} withdrawn; records kept and sign-in switched off.")
    except StudentValidationError as exc:
        print(f"Not withdrawn: {_errors(exc)}")


def reinstate_student(auth, student_id):
    reason = _ask("Reason for reinstating", required=True)
    try:
        StudentLifecycleService().restore(student_id, actor_id=_actor(auth), reason=reason,
                                          idempotency_key=_key("reinstate", student_id))
        print(f"{student_id} is Active again and can sign in.")
    except StudentValidationError as exc:
        print(f"Not reinstated: {_errors(exc)}")


def show_history(student_id):
    rows = _read(rules.change_history, student_id)
    if not rows:
        print("No changes recorded.")
    for r in rows:
        print(f"  {str(r['when'])[:16]}  {r['what']:<22} {r['old'] or '—'} → {r['new'] or '—'}"
              f"  ({r['reason'] or ''}; {r['by'] or ''})")


# ── erasure and data check ──────────────────────────────────────────────


def _erasure():
    from education_system.systems.university.application.students import erasure as student_erasure
    return student_erasure


def _guarded(fn, *args, write=True):
    try:
        return _read(fn, *args, write=write)
    except ValueError as exc:
        print(f"Refused: {exc}")
        return None


def erasure_menu(auth):
    er = _erasure()
    for r in _read(er.requests):
        print(f"  #{r['request_id']} {r['student_id']} {r['status']} case {r['case_reference']} "
              f"(by {r['requested_by']})")
    choice = _ask("1. Request  2. Approve  3. Reject  4. Carry out  0. Back", default="0")
    if choice == "1":
        rid = _guarded(er.request, _ask("Student ID", required=True),
                       _ask("Case reference", required=True), _ask("Reason", required=True),
                       _actor(auth))
        if rid:
            print(f"Request #{rid} recorded; someone else must approve it.")
    elif choice in ("2", "3"):
        _decide(auth, er, approve=choice == "2")
    elif choice == "4":
        _carry_out(auth, er)


def _decide(auth, er, approve):
    from education_system.systems.university.services.student_provisioning import (
        verify_staff_password,
    )
    rid = _ask("Request number", required=True)
    ok = verify_staff_password(_actor(auth), getpass.getpass("Re-enter your password: "))
    if _guarded(lambda conn: er.decide(conn, int(rid), approve, _actor(auth),
                                       reauthenticated=ok, note=_ask("Note (optional)"))):
        print("Approved." if approve else "Rejected.")


def _carry_out(auth, er):
    from education_system.systems.university.services.student_provisioning import (
        erase_student_login,
    )
    rid = _ask("Request number", required=True)
    if _ask("This permanently erases personal data. Type ERASE to continue") != "ERASE":
        return
    result = _guarded(er.execute, int(rid), _actor(auth))
    if result:
        erase_student_login(result["login"])
        print(f"Done; the record is now {result['anonymous_id']}.")


def data_check(auth):
    from education_system.systems.university.application.students import data_quality as dq
    found = _read(dq.issues)
    for i, issue in enumerate(found, 1):
        fix = ", ".join(f"{k} → {v}" for k, v in (issue["fix"] or {}).items()) or "needs a person"
        print(f"  {i}. {issue['student_id']} {issue['name']}: {issue['detail']} [{fix}]")
    if not found:
        print("No problems found.")
        return
    picks = _ask("Fix which (numbers separated by commas, 'all' for every fixable, blank = none)")
    if not picks:
        return
    chosen = [f["key"] for f in found if f["fix"]] if picks == "all" else [
        found[int(p) - 1]["key"] for p in picks.split(",")
        if p.strip().isdigit() and 0 < int(p) <= len(found)]
    changed = _read(lambda conn: dq.apply_fixes(conn, chosen, _actor(auth)), write=True)
    print(f"{changed} record(s) corrected.")
