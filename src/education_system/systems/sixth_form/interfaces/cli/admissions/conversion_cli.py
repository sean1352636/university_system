"""Admissions CLI: converting applicants to students, and the intake log."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.admissions import (
    admissions as data,
    college_intake,
    conversion,
)
from education_system.systems.sixth_form.domain.admissions.admissions import (
    Applicant,
    ValidationError,
)
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)
from education_system.systems.sixth_form.interfaces.cli.admissions._common import (
    _UserAbort,
    _attempt,
    _can,
    _cli_user,
    _input,
    _pause,
    _pick_applicant,
    _pick_from,
    _yes,
)


def _pick_year_group() -> int:
    """Year 12 (a new start) or Year 13 (a transfer-in to the second year)."""
    got = _pick_from("Year group", ["12 — new start", "13 — Year 13 transfer-in"],
                     default="12 — new start")
    return int(got[:2])


def _pick_tutor_group(default: str = "", year_group: int = 12) -> str | None:
    """Tutor groups for the year group from the tutor-group register
    (blank = none)."""
    try:
        from education_system.systems.sixth_form.domain.pastoral.tutor_groups import (
            tutor_groups,
        )
        names = [g.name for g in tutor_groups.list_groups(year_group=year_group)]
    except Exception:  # noqa: BLE001 — the register is optional here
        names = []
    if not names:
        return _input("Tutor group (blank = none)", default=default) or None
    got = _pick_from("Tutor group", ["(none)"] + names, default="(none)")
    return None if got == "(none)" else got


def _pick_existing_student(a: Applicant) -> str | None:
    """Find a student already on file (internal Year 11, secondary intake)."""
    from education_system.systems.sixth_form.domain.learners.students import (
        students,
    )
    q = _input("Search students (name / email / ULN)",
               default=a.email or a.full_name, allow_empty=False)
    rows = students.search_students(q)[:20]
    if not rows:
        print("    No student matched.")
        return None
    labels = [f"{s.student_id}  {s.first_name} {s.last_name}  "
              f"DOB {getattr(s, 'date_of_birth', None) or '—'}" for s in rows]
    got = _pick_from("Link to", ["(none — create a new student)"] + labels,
                     default="(none — create a new student)")
    return None if got.startswith("(none") else got.split()[0]


def _print_steps(aid: str) -> None:
    rec = data.get_conversion(aid)
    for st in (rec.steps if rec else []):
        print(f"    [{st['result']:>6}] {st['step']}: {st['detail']}")


def convert_flow() -> None:
    print("\n═══ Convert to Student ═══")
    if not _can(access.STUDENTS_MANAGE):
        print("  ✗ Converting needs the students.manage permission as well "
              "as admissions.")
        _pause()
        return
    try:
        a = _pick_applicant()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    # Pre-conversion checklist (items 37, 40) + conversion gates.
    issues = data.pre_conversion_check(a.applicant_id)
    gates = conversion.conversion_gates(a.applicant_id)
    print("\n  Pre-conversion checklist:")
    if issues:
        for iss in issues:
            print(f"    ✗ {iss}")
        print("\n  Not ready to enrol.")
        _pause()
        return
    print("    ✓ Status is 'Offer Accepted'")
    print("    ✓ Programme choices recorded (any qualification mix)")
    print("    ✓ Email on file")
    print("    ✓ Offer not expired")
    for g in gates:
        print(f"    ⚠ {g}")
    journey = college_intake.pending_journey(a.applicant_id)
    if journey:
        print(f"    ↪ Secondary-school journey {journey} will be linked")
    try:
        year = _input("Academic year", default=conversion.default_academic_year(),
                      allow_empty=False)
        start = _input("Start date (YYYY-MM-DD; blank = start of year or "
                       "today for a mid-year joiner)") or None
        year_group = _pick_year_group()
        tutor = _pick_tutor_group(year_group=year_group)
        existing = None
        if _yes("Is this applicant already on file as a student (link "
                "instead of creating a second record)?"):
            existing = _pick_existing_student(a)
        override = None
        if gates:
            print("\n  The gates above block conversion.")
            if not _yes("Override them (reason is recorded)?"):
                raise _UserAbort
            override = _input("Override reason", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    what = (f"link {a.applicant_id} to student {existing}" if existing
            else f"create a student record from {a.applicant_id}")
    if _input(f"\n  {what} ({a.full_name})? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    _convert(a, academic_year=year, start_date=start, tutor_group=tutor,
             existing_student_id=existing, override_reason=override,
             year_group=year_group)
    _pause()


def _convert(a: Applicant, **kwargs) -> bool:
    try:
        _, sid = conversion.convert_to_student(
            a.applicant_id, converted_by=_cli_user(), **kwargs)
    except conversion.ConversionBlocked as e:
        print("\n  ✗ Blocked:")
        for g in e.gates:
            print(f"      • {g}")
        if _yes("  Override with a reason?"):
            kwargs["override_reason"] = _input("Override reason",
                                               allow_empty=False)
            return _convert(a, **kwargs)
        return False
    except (ValidationError, access.AccessDenied) as e:
        print(f"\n  ✗ {e}")
        return False
    print(f"\n  ✓ Applicant {a.applicant_id} enrolled as student {sid}")
    _print_steps(a.applicant_id)
    return True


def bulk_enrol_flow() -> None:
    print("\n═══ Bulk Enrol Accepted Offers ═══")
    if not _can(access.STUDENTS_MANAGE):
        print("  ✗ Converting needs the students.manage permission.")
        _pause()
        return
    accepted = [a for a in data.list_applicants(status="Offer Accepted")
                if not a.converted_student_id]
    if not accepted:
        print("\n  No applicants in 'Offer Accepted'.")
        _pause()
        return
    year = _input("Academic year for all",
                  default=conversion.default_academic_year(),
                  allow_empty=False)
    start = _input("Start date for all (blank = default)") or None
    year_group = _pick_year_group()
    if not _yes(f"Attempt to enrol {len(accepted)} accepted applicant(s)? "
                "Anyone with an open gate is skipped and listed."):
        print("\n  Cancelled.")
        return
    done, problems = [], []
    user = _cli_user()
    for a in accepted:
        issues = data.pre_conversion_check(a.applicant_id)
        if issues:
            problems.append(f"{a.applicant_id} {a.full_name}: "
                            + "; ".join(issues))
            continue
        try:
            _, sid = conversion.convert_to_student(
                a.applicant_id, academic_year=year, start_date=start,
                converted_by=user, year_group=year_group)
        except conversion.ConversionBlocked as e:
            problems.append(f"{a.applicant_id} {a.full_name}: gates — "
                            + "; ".join(e.gates))
            continue
        except (ValidationError, access.AccessDenied) as e:
            problems.append(f"{a.applicant_id} {a.full_name}: {e}")
            continue
        rec = data.get_conversion(a.applicant_id)
        failed = [st["step"] for st in (rec.steps if rec else [])
                  if st["result"] != "ok"]
        done.append(f"{a.applicant_id} → {sid}"
                    + (f"  (steps needing attention: {', '.join(failed)})"
                       if failed else ""))
    print(f"\n  ✓ Enrolled {len(done)}:")
    for d in done:
        print(f"      {d}")
    if problems:
        print(f"  Not enrolled ({len(problems)}) — convert each one "
              "individually to override:")
        for s in problems:
            print(f"      {s}")
    _pause()


def intake_log_flow() -> None:
    """What the secondary-school intake did with each progression event."""
    print("\n═══ Intake Log (from secondary) ═══")
    rows = college_intake.list_intake_log()
    if not rows:
        print("  (nothing received yet)")
    for e in rows:
        print(f"    {e.at[:16]}  {e.action:<17} journey {e.journey_id}  "
              f"applicant {e.applicant_id or '—'}  student "
              f"{e.student_id or '—'}"
              + (f"  [{e.matched_on}]" if e.matched_on else "")
              + (f"\n        {e.detail}" if e.detail else ""))
    _pause()


def conversion_preview_flow() -> None:
    """Show the gates for one applicant without converting."""
    a = _pick_applicant()
    issues = data.pre_conversion_check(a.applicant_id)
    gates = conversion.conversion_gates(a.applicant_id)
    print(f"\n  {a.applicant_id} {a.full_name} [{a.status}]")
    for i in issues:
        print(f"    ✗ {i}")
    for g in gates:
        print(f"    ⚠ {g}")
    if not issues and not gates:
        print("    ✓ Ready to convert")
    ok, journey = _attempt(college_intake.pending_journey, a.applicant_id)
    if ok and journey:
        print(f"    ↪ Pending secondary journey {journey}")
    _pause()
