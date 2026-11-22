"""Conversion of an accepted applicant into a student.

Split out of :mod:`admissions` (file-size limit); ``admissions`` re-exports
``convert_to_student``, ``get_conversion``, ``conversion_for_student`` and
``default_academic_year`` so existing callers are unchanged.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from typing import Any

from education_system.systems.sixth_form.domain.admissions import (
    _guard,
    status_rules,
)
from education_system.systems.sixth_form.domain.admissions.admissions import (
    Applicant,
    ConversionRecord,
    ValidationError,
    _connect,
    _log_event,
    _validate_date,
    _validate_subject,
    get_applicant,
    get_photo,
    init_db,
    update_applicant,
)
from education_system.systems.sixth_form.domain.admissions.programme_choices import (
    ONE_YEAR_TYPES,
    _a_level_types,
    list_programme_choices,
)
from education_system.systems.sixth_form.infrastructure import database as db

logger = logging.getLogger(__name__)


# ── Conversion to a Student ────────────────────────────────────────

def default_academic_year(today: _dt.date | None = None) -> str:
    """The sixth-form year a converted applicant joins.

    January–July converts are joining in the coming September; August–
    December converts are joining the year that started this September.
    Either way that is the year beginning in September of this calendar
    year. A mid-year joiner passes ``academic_year`` explicitly.
    """
    y = (today or _dt.date.today()).year
    return f"{y}/{str(y + 1)[-2:]}"


def _year_start(academic_year: str) -> _dt.date:
    m = re.match(r"^(\d{4})/\d{2}$", (academic_year or "").strip())
    if not m:
        raise ValidationError("Academic year must look like '2025/26'")
    return _dt.date(int(m.group(1)), 9, 1)


def _planned_end(qualification_type: str, academic_year: str,
                 year_group: int = 12) -> str:
    """End of the course: a two-year qualification started in Year 12
    ends after two years; a Year 13 transfer-in finishes it this year."""
    first = _year_start(academic_year).year
    years = 1 if (qualification_type in ONE_YEAR_TYPES
                  or year_group == 13) else 2
    return _dt.date(first + years, 6, 30).isoformat()


def _student_columns(conn: db.Connection) -> set[str]:
    return {r["name"] for r in conn.execute(
        "PRAGMA table_info(students)").fetchall()}


#: A claim older than this is treated as a crashed conversion.
CLAIM_TIMEOUT_MINUTES = 15


class ConversionBlocked(ValidationError):
    """A gate (conditions, ID / right to study) stops the conversion.
    ``gates`` lists each reason; pass ``override_reason`` to proceed."""

    def __init__(self, gates: list[str]):
        self.gates = gates
        super().__init__("Cannot enrol yet: " + "; ".join(gates)
                         + ". Give an override reason to enrol anyway.")


def conversion_gates(applicant_id: str) -> list[str]:
    """Reasons the applicant should not be enrolled yet (empty = clear):
    a conditional offer whose conditions are not confirmed, or no ID /
    right-to-study check."""
    a = get_applicant(applicant_id)
    if a is None:
        return ["Applicant not found"]
    gates: list[str] = []
    if a.offer_type == "Conditional":
        from education_system.systems.sixth_form.domain.admissions import (
            entry_requirements as _er,
        )
        if _er.list_conditions(applicant_id) or (a.offer_conditions or "").strip():
            gates.append("the offer is still conditional (confirm it on "
                         "results day first)")
    from education_system.systems.sixth_form.domain.admissions import (
        applicant_details as _details,
    )
    ok, why = _details.identity_ok(applicant_id)
    if not ok:
        gates.append(why)
    return gates


def _claim(applicant_id: str) -> None:
    """Mark the applicant as being converted, so a second click or a
    second user cannot create a second student."""
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE admissions_applicants SET converting_at = datetime('now') "
            "WHERE applicant_id = ? AND converted_student_id IS NULL AND "
            "(converting_at IS NULL OR converting_at < "
            f"datetime('now', '-{int(CLAIM_TIMEOUT_MINUTES)} minutes'))",
            (applicant_id,))
        conn.commit()
    if cur.rowcount != 1:
        raise ValidationError(
            f"{applicant_id} is already being converted (or was just "
            "converted). Refresh and check before trying again.")


def _release(applicant_id: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE admissions_applicants SET converting_at = NULL "
                     "WHERE applicant_id = ?", (applicant_id,))
        conn.commit()


def convert_to_student(applicant_id: str, *,
                       academic_year: str | None = None,
                       start_date: str | None = None,
                       tutor_group: str | None = None,
                       converted_by: str | None = None,
                       existing_student_id: str | None = None,
                       override_reason: str | None = None,
                       year_group: int = 12,
                       ) -> tuple[Applicant, str]:
    """Create a `students` row from the applicant and set them up.

    Returns the updated applicant and the new student_id. Beyond the
    student record itself (name, date of birth, phone, personal email,
    ULN and — where the student record has the columns — address and
    previous school) this

    * creates the enrolment for ``academic_year`` — Year 12, or Year 13
      for a learner transferring in to finish their course
      (``year_group=13``; their two-year aims then end this year);
    * creates a learning aim for every programme choice, whatever the
      mix (A levels, a fourth A level, BTEC, T Level, EPQ, resits);
    * copies the applicant's actual GCSE results into prior attainment;
    * carries the applicant photo into the enrolment identity record;
    * opens the onboarding checklist (plus "record GCSE results" when
      none were confirmed and "contact the DSL" when a feeder reference
      asked for it);
    * copies the admissions ID / right-to-study check into the enrolment
      identity record (``enrolment_identity_checks`` + its history);
    * carries every parent/carer contact into the parent contacts store;
    * hands sensitive information to its own register — LLDD / EHCP /
      SEND details to the SEND register, medical details to the medical
      profile, safeguarding handover to the safeguarding log as a concern
      for the DSL (run as ``system:admissions-conversion`` with the
      safeguarding capability);
    * looked after / care leaver, young carer and free-meals flags become
      onboarding tasks for the designated teacher, pastoral team and
      finance (their registers need detail the application does not
      hold, so nothing is invented), and bursary interest becomes a
      Draft bursary application;
    * links the platform journey when the secondary intake attached the
      pupil to this application.

    Sensitive text is never copied into the conversion record: when a
    register refuses it, ``carried`` says it is still held on the
    application.

    Only the student record is all-or-nothing; every later step is
    attempted, and its outcome is kept in ``admissions_conversions``
    (see :func:`get_conversion`) so a failure is visible, not silent.

    ``existing_student_id`` links the applicant to a student who is
    already on file (an internal Year 11 pupil, or one created by the
    secondary intake) instead of creating a second record; the remaining
    steps run against that student.

    Requires:
      - the ``admissions`` and ``students.manage`` capabilities
      - status is Offer Accepted (an already-converted applicant is a
        no-op)
      - at least one programme choice
      - email present (kept as the student's personal email)
      - no open gate (:func:`conversion_gates`) unless ``override_reason``

    The applicant is claimed first (``converting_at``) so two clicks
    cannot create two students, and the student link is written as soon
    as the student exists, so a failure in a later step never leaves an
    applicant that a retry would convert again.
    """
    init_db()
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access as _access,
    )
    try:
        year_group = int(year_group)
    except (TypeError, ValueError):
        raise ValidationError("Year group must be 12 or 13") from None
    if year_group not in (12, 13):
        raise ValidationError("Year group must be 12 or 13")
    _guard.require("converting applicants")
    _guard.require("creating students", _access.STUDENTS_MANAGE)
    converted_by = converted_by or _guard.actor()
    a = get_applicant(applicant_id)
    if a is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    if a.converted_student_id:
        logger.info(
            "Applicant %s already enrolled as %s — no-op",
            applicant_id, a.converted_student_id)
        return a, a.converted_student_id
    if a.is_archived:
        raise ValidationError(f"{applicant_id} is archived.")
    if a.status != "Offer Accepted":
        raise ValidationError(
            "Applicant must be in 'Offer Accepted' status to convert "
            "(current: " + a.status + ")")
    gates = conversion_gates(applicant_id)
    override_reason = (override_reason or "").strip() or None
    if gates and not override_reason:
        raise ConversionBlocked(gates)
    choices = list_programme_choices(applicant_id)
    if not choices:
        raise ValidationError(
            "Set at least one programme choice (subject or qualification) "
            "before conversion")
    if not a.email:
        raise ValidationError(
            "Applicant must have an email address to convert to a "
            "student record")
    year = (academic_year or "").strip() or default_academic_year()
    year_start = _year_start(year)
    year_end = _dt.date(year_start.year + 1, 8, 31)
    start = _validate_date(start_date, "Start date") or max(
        year_start, _dt.date.today()).isoformat()
    # A mid-year joiner starts within the year; the enrolment and the
    # learning aims all take this date.
    if not (year_start.isoformat() <= start <= year_end.isoformat()):
        raise ValidationError(
            f"Start date {start} is outside the {year} academic year "
            f"({year_start.isoformat()} to {year_end.isoformat()})")

    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    alevel_types = _a_level_types()
    # The three slots take the first three A Level choices that the
    # subject catalogue knows (the student module turns them into A Level
    # aims); every other choice, AS levels included, becomes an aim below.
    slot_subjects: list[str] = []
    for c in choices:
        if c.qualification_type == "A Level" and len(slot_subjects) < 3:
            try:
                _validate_subject(c.subject, "Subject")
                slot_subjects.append(c.subject)
            except ValidationError:
                pass
    slots = (slot_subjects + ["", "", ""])[:3]
    steps: list[dict[str, str]] = []
    carried: dict[str, Any] = {}

    def step(name: str, ok: bool, detail: str) -> None:
        steps.append({"step": name, "result": "ok" if ok else "failed",
                      "detail": detail})
        (logger.info if ok else logger.warning)(
            "convert %s: %s — %s", applicant_id, name, detail)

    payload: dict[str, Any] = {
        "first_name":     a.first_name,
        "last_name":      a.last_name,
        "date_of_birth":  a.dob,
        "phone":          a.phone,
        "personal_email": a.email,
        "subject_1":      slots[0],
        "subject_2":      slots[1],
        "subject_3":      slots[2],
        "status":         "Active",
    }
    for key, value in (("address", a.address),
                       ("previous_school", a.previous_school),
                       ("uln", a.uln)):
        if value:
            payload[key] = value
    # A mistyped UPN must not stop the learner being enrolled: it is kept
    # in the conversion record and reported, like a refused phone number.
    if a.upn:
        try:
            from education_system.systems.sixth_form.domain.learners.students import (
                student_profile,
            )
            payload["upn"] = student_profile.validate_upn(a.upn)
        except _students.ValidationError as e:
            carried["upn"] = a.upn
            step("UPN", False, f"UPN {a.upn!r} not accepted ({e}); "
                 "kept in the conversion record")
    _profile_payload(a, payload, carried, step)
    if gates:
        step("override", True, f"Enrolled despite: {'; '.join(gates)} — "
             f"reason: {override_reason}")
    _claim(applicant_id)
    try:
        if existing_student_id:
            student = _link_existing(applicant_id, existing_student_id.strip())
            step("student record", True,
                 f"Linked to existing student {student.student_id}")
        else:
            try:
                student = _students.create_student(payload)
            except _students.ValidationError as e:
                if "phone" not in str(e).lower() or not a.phone:
                    raise ValidationError(
                        f"Student record not created: {e}") from e
                payload["phone"] = None
                student = _students.create_student(payload)
                carried["phone"] = a.phone
                step("phone", False,
                     f"Phone {a.phone!r} not accepted by the student record "
                     f"({e}); kept in the conversion record")
            step("student record", True, f"Created {student.student_id}")
        sid = student.student_id
        with status_rules.converting():
            update_applicant(applicant_id, {
                "status": "Enrolled",
                "converted_student_id": sid,
                "decision_date": _dt.date.today().isoformat(),
            })
    finally:
        _release(applicant_id)

    # Fields the student record has no column for are kept here (and in
    # the applicant row) rather than dropped.
    with _connect() as conn:
        cols = _student_columns(conn)
    for key, value in (("address", a.address),
                       ("previous_school", a.previous_school)):
        if value and key not in cols:
            carried[key] = value
    if payload.get("upn") and _students.get_upn(sid) != payload["upn"]:
        carried["upn"] = a.upn
        step("UPN", False, f"UPN {payload['upn']} is held by another student")
    if a.dob and student.date_of_birth != a.dob:
        carried["date_of_birth"] = a.dob

    # ULN (LRS check digit enforced by the student module).
    if a.uln and getattr(student, "uln", None) != a.uln:
        try:
            _students.set_identifiers(sid, uln=a.uln)
            step("ULN", True, f"ULN {a.uln} set")
        except Exception as e:  # noqa: BLE001 — reported per step
            carried["uln"] = a.uln
            step("ULN", False, str(e))

    # Enrolment.
    enrolment_id: int | None = None
    try:
        from education_system.systems.sixth_form.domain.admissions.enrolments import (
            enrolments as _enrolments,
        )
        enr = _enrolments.create_enrolment({
            "student_id": sid, "academic_year": year,
            "year_group": year_group,
            "tutor_group": tutor_group, "start_date": start,
            "status": "Enrolled",
            "notes": f"From admissions applicant {applicant_id}",
        })
        enrolment_id = enr.enrolment_id
        step("enrolment", True,
             f"Year {year_group} {year} (#{enrolment_id})"
             + (" — transfer-in" if year_group == 13 else ""))
    except Exception as e:  # noqa: BLE001
        step("enrolment", False, str(e))

    # Learning aims: fix the dates of the A-level aims the student module
    # created from the slots, then add every other choice.
    try:
        from education_system.systems.sixth_form.domain.academics.qualifications import (
            learning_aims as _aims,
        )
        existing = {(x.qualification_type, x.subject): x
                    for x in _aims.list_aims(sid, status="Active")}
        for order, c in enumerate(choices):
            planned_end = _planned_end(c.qualification_type, year,
                                       year_group)
            aim = existing.get((c.qualification_type, c.subject))
            try:
                if aim is not None:
                    _aims.update_aim(aim.aim_id, {
                        "start_date": start, "planned_end_date": planned_end,
                        "academic_year": year, "display_order": order,
                    }, recorded_by=converted_by)
                    step("learning aim", True,
                         f"{aim.label}: dated {start} to {planned_end}")
                else:
                    new = _aims.add_aim(sid, {
                        "qualification_type": c.qualification_type,
                        "subject": c.subject, "start_date": start,
                        "planned_end_date": planned_end,
                        "academic_year": year, "display_order": order,
                        "notes": c.notes,
                    }, recorded_by=converted_by,
                        reason=f"Programme choice on admissions applicant "
                               f"{applicant_id}")
                    step("learning aim", True, f"{new.label} added")
            except Exception as e:  # noqa: BLE001
                step("learning aim", False,
                     f"{c.qualification_type} {c.subject}: {e}")
    except Exception as e:  # noqa: BLE001
        step("learning aims", False, str(e))

    # Prior attainment: confirmed (actual) GCSE results only.
    copied = 0
    try:
        from education_system.systems.sixth_form.domain.admissions import (
            entry_requirements as _er,
        )
        from education_system.systems.sixth_form.domain.academics.qualifications import (
            prior_attainment as _prior,
        )
        for g in _er.list_gcses(applicant_id, result_type="Actual"):
            try:
                _prior.add_result(sid, {
                    "subject": g.subject, "grade": g.grade,
                    "grade_system": g.grade_system, "kind": g.kind,
                    "year": g.year, "exam_board": g.exam_board,
                    "notes": f"From admissions applicant {applicant_id} "
                             f"({g.source})",
                })
                copied += 1
            except Exception as e:  # noqa: BLE001
                step("prior attainment", False, f"{g.subject} {g.grade}: {e}")
        step("prior attainment", True, f"{copied} GCSE result(s) copied")
    except Exception as e:  # noqa: BLE001
        step("prior attainment", False, str(e))

    # Photo into the enrolment identity record.
    photo = get_photo(applicant_id)
    if photo is not None:
        try:
            from education_system.systems.sixth_form.domain.admissions.enrolments import (
                identity_checks as _idc,
            )
            _idc.set_photo(sid, photo.path, by=converted_by)
            step("photo", True, "Applicant photo carried to enrolment record")
        except Exception as e:  # noqa: BLE001
            carried["photo_path"] = photo.path
            step("photo", False, str(e))

    # Parent/carer contacts, sensitive information and welfare flags.
    _carry_contacts(applicant_id, sid, step, carried)
    _carry_sensitive(a, sid, converted_by, step, carried)
    links: dict[str, Any] = {}
    welfare_tasks = _carry_welfare(a, sid, year, step, carried, links)

    # Onboarding checklist.
    checklist_id: int | None = None
    try:
        from education_system.systems.sixth_form.domain.admissions.onboarding import (
            onboarding as _onboarding,
        )
        extra: list[tuple[str, str, bool]] = list(welfare_tasks)
        if not copied:
            extra.append(("Record GCSE results (prior attainment)",
                          "Academic", True))
        if not slot_subjects and not any(
                c.qualification_type not in alevel_types for c in choices):
            extra.append((_onboarding.CHOOSE_SUBJECTS_TASK, "Academic", True))
        try:
            from education_system.systems.sixth_form.domain.admissions import (
                references as _refs,
            )
            if _refs.dsl_contact_requested(applicant_id):
                extra.append((_onboarding.CONTACT_DSL_TASK,
                              "Wellbeing & Pastoral", True))
        except Exception:
            logger.exception("convert %s: reference check failed",
                             applicant_id)
        # The template follows the learner: Year 13 transfer-in,
        # international, mid-year joiner or new starter, plus the SEND /
        # care add-ons (workflow.choose_template).
        from education_system.systems.sixth_form.domain.admissions.onboarding import (
            workflow as _ob_workflow,
        )
        opened = _ob_workflow.open_for_learner(
            sid, enrolment=enrolment_id, applicant=a, extra_tasks=extra,
            academic_year=year,
            due_date=(_dt.date.fromisoformat(start)
                      + _dt.timedelta(days=14)).isoformat(),
            notes=f"Opened on conversion of admissions applicant "
                  f"{applicant_id}")
        checklist_id = opened.checklist.checklist_id
        step("onboarding", not opened.problems,
             f"Checklist #{checklist_id} ({opened.checklist.template_name}; "
             f"{opened.choice.label})"
             + "".join(f"; {x}" for x in opened.problems))
        if links.get("bursary_application_id"):
            from education_system.systems.sixth_form.domain.admissions.onboarding import (
                bursary_link as _bursary_link,
            )
            try:
                _bursary_link.link_application(
                    checklist_id, links["bursary_application_id"])
                step("bursary task", True, "Onboarding task linked to "
                     f"bursary application #{links['bursary_application_id']}")
            except Exception as e:  # noqa: BLE001 — reported per step
                step("bursary task", False, str(e))
    except Exception as e:  # noqa: BLE001
        step("onboarding", False, str(e))

    # ID / right to study (after the checklist, so the ID item ticks).
    _carry_identity(applicant_id, sid, step, carried)

    # Platform journey attached by the secondary intake.
    try:
        from education_system.systems.sixth_form.domain.admissions import (
            college_intake as _intake,
        )
        journey = _intake.link_pending_journey(applicant_id, sid)
        if journey:
            step("linked record", True,
                 f"Secondary transfer journey {journey} linked to {sid}")
            from education_system.systems.sixth_form.domain.admissions import (
                secondary_handover as _sh,
            )
            if _sh.report_enrolled(applicant_id, sid, journey):
                step("secondary school", True, "School told the pupil has enrolled "
                     "(they come off the school roll)")
    except Exception as e:  # noqa: BLE001
        step("linked record", False, str(e))

    updated = get_applicant(applicant_id)
    assert updated is not None
    import json as _json
    with _connect() as conn:
        conn.execute(
            """INSERT INTO admissions_conversions
                   (applicant_id, student_id, converted_by, academic_year,
                    enrolment_id, checklist_id, carried_json, steps_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(applicant_id) DO UPDATE SET
                   student_id = excluded.student_id,
                   converted_at = datetime('now'),
                   converted_by = excluded.converted_by,
                   academic_year = excluded.academic_year,
                   enrolment_id = excluded.enrolment_id,
                   checklist_id = excluded.checklist_id,
                   carried_json = excluded.carried_json,
                   steps_json = excluded.steps_json""",
            (applicant_id, sid, converted_by, year, enrolment_id,
             checklist_id, _json.dumps(carried), _json.dumps(steps)))
        failed = [s for s in steps if s["result"] != "ok"]
        _log_event(conn, applicant_id,
                   f"Converted to student {sid}"
                   + (f" — {len(failed)} step(s) need attention"
                      if failed else "")
                   + (f" — gates overridden: {override_reason}"
                      if gates else ""), kind="conversion")
        conn.commit()
    logger.info("Converted applicant %s → student %s",
                applicant_id, sid)
    return updated, sid


def _profile_payload(a: Applicant, payload: dict[str, Any],
                     carried: dict[str, Any], step: Any) -> None:
    """Carry the applicant profile and first emergency contact into the
    new student record."""
    from education_system.systems.sixth_form.domain.admissions import (
        applicant_details as _details,
    )
    for src, dst in (("sex", "gender"), ("ethnicity", "ethnicity"),
                     ("nationality", "nationality"),
                     ("first_language", "first_language")):
        value = getattr(a, src)
        if value:
            payload[dst] = value
    try:
        ec = _details.emergency_contact(a.applicant_id)
    except Exception:  # noqa: BLE001 — reported as a step
        logger.warning("convert %s: contacts not read", a.applicant_id,
                       exc_info=True)
        ec = None
    if ec is not None:
        payload["emergency_contact_name"] = ec.name
        if ec.phone:
            payload["emergency_contact_phone"] = ec.phone
        if ec.relationship:
            payload["emergency_contact_relation"] = ec.relationship
    elif not a.converted_student_id:
        step("emergency contact", False,
             "No parent/carer or emergency contact on the application")


# ── Carry steps (each one a step entry; nothing dropped silently) ──

#: Applicant contact relationship -> parent contacts relationship.
_REL_TO_PARENT: dict[str, str] = {
    "Mother": "Mother", "Father": "Father", "Parent": "Parent",
    "Carer": "Carer", "Foster carer": "Foster Carer", "Sibling": "Sibling",
    "Social worker": "Social Worker",
}


def _carry_identity(applicant_id: str, sid: str, step: Any,
                    carried: dict[str, Any]) -> None:
    from education_system.systems.sixth_form.domain.admissions import (
        applicant_details as _details,
    )
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        identity_checks as _idc,
    )
    try:
        rec = _details.get_identity(applicant_id)
    except Exception as e:  # noqa: BLE001
        step("ID check", False, f"Admissions ID check not read: {e}")
        return
    if rec is None or not rec.document_type:
        step("ID check", False, "No ID check on the application — record "
             "it on the enrolment identity screen")
        return
    try:
        _idc.record_from_admissions(sid, rec, applicant_id)
        step("ID check", True,
             f"{rec.document_type} (…{rec.id_number_last4}) checked "
             f"{rec.checked_on} by {rec.checked_by or '?'}; right to study: "
             f"{rec.right_to_study}"
             + (f", visa expires {rec.visa_expiry}" if rec.visa_expiry
                else ""))
    except Exception as e:  # noqa: BLE001
        carried["identity"] = {
            "document_type": rec.document_type,
            "id_number_last4": rec.id_number_last4,
            "right_to_study": rec.right_to_study,
            "visa_expiry": rec.visa_expiry, "checked_by": rec.checked_by,
            "checked_on": rec.checked_on}
        step("ID check", False, str(e))


def _split_name(name: str) -> tuple[str, str] | None:
    parts = (name or "").split()
    if len(parts) < 2:
        return None
    return " ".join(parts[:-1]), parts[-1]


def _carry_contacts(applicant_id: str, sid: str, step: Any,
                    carried: dict[str, Any]) -> None:
    """Every applicant contact into the parent contacts store (names the
    student already has there are skipped)."""
    from education_system.systems.sixth_form.domain.admissions import (
        applicant_details as _details,
    )
    try:
        contacts = _details.list_contacts(applicant_id)
    except Exception as e:  # noqa: BLE001
        step("contacts", False, f"Applicant contacts not read: {e}")
        return
    if not contacts:
        return
    try:
        from education_system.systems.sixth_form.domains.communications.domain.parent_contacts import (
            parent_contacts as _pc,
        )
        have = {(c.first_name.lower(), c.last_name.lower())
                for c in _pc.contacts_for_student(sid)}
        has_primary = any(c.is_primary for c in _pc.contacts_for_student(sid))
    except Exception as e:  # noqa: BLE001
        carried["contacts"] = [c.name for c in contacts]
        step("contacts", False, f"Parent contacts store unavailable: {e}")
        return
    missed: list[str] = []
    for c in contacts:
        names = _split_name(c.name)
        if names is None:
            missed.append(c.name)
            step("contact", False, f"{c.name}: give a first and last name "
                 "to add them to the parent contacts")
            continue
        first, last = names
        if (first.lower(), last.lower()) in have:
            continue
        rel = _REL_TO_PARENT.get(c.relationship or "", "Other")
        note = "; ".join(x for x in (
            f"From admissions applicant {applicant_id}",
            f"relationship on application: {c.relationship}"
            if c.relationship and rel == "Other" else None) if x)
        try:
            _pc.create_contact({
                "student_id": sid, "relationship": rel,
                "first_name": first, "last_name": last, "email": c.email,
                "primary_phone": c.phone, "address": c.address,
                "preferred_method": "Email" if c.email else "Phone (primary)",
                "is_primary": not has_primary,
                "is_emergency_contact": c.is_emergency,
                "has_parental_responsibility": c.parental_responsibility,
                "receives_communications": c.receives_correspondence,
                "notes": note,
            })
            has_primary = True
            have.add((first.lower(), last.lower()))
            step("contact", True, f"{c.name} ({rel}) added to parent contacts")
        except Exception as e:  # noqa: BLE001
            missed.append(c.name)
            step("contact", False, f"{c.name}: {e}")
    if missed:
        carried["contacts"] = missed


def _held_note(area: str, applicant_id: str, why: Any) -> str:
    return (f"{area} held on admissions applicant {applicant_id} (not "
            f"copied here): {why}")


def _carry_sensitive(a: Applicant, sid: str, converted_by: str | None,
                     step: Any, carried: dict[str, Any]) -> None:
    """SEND, medical and safeguarding text to their own registers."""
    from education_system.systems.sixth_form.domain.admissions import (
        applicant_details as _details,
    )
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access as _access,
    )
    aid = a.applicant_id
    try:
        raw = _details.sensitive_for_conversion(aid)
    except Exception as e:  # noqa: BLE001
        step("sensitive information", False, f"Not read: {e}")
        return
    today = _dt.date.today().isoformat()

    send_text = (raw.get("send") or "").strip()
    if send_text or a.lldd or a.ehcp:
        try:
            from education_system.systems.sixth_form.domain.pastoral.send import (
                send as _send,
            )
            from education_system.systems.sixth_form.domain.admissions import (
                secondary_handover as _sh,
            )
            # Structured SEN details from a secondary school handover give
            # the need and register status; anything else is for the SENCO.
            school = _sh.register_fields(send_text)
            notes = (f"From admissions applicant {aid}"
                     + (" (LLDD declared)" if a.lldd else "")
                     + (" (EHCP declared)" if a.ehcp else "")
                     + (". Need and status from the secondary school's SEN "
                        "details; SENCO to review." if school.get("primary_need")
                        else ". Primary need to be confirmed by the SENCO.")
                     + (f"\n\nSEND details on the application:\n{send_text}"
                        if send_text else ""))
            entry = _send.create_entry({
                "student_id": sid,
                "register_status": school.get("register_status")
                or ("EHCP" if a.ehcp else "Awaiting Assessment"),
                "primary_need": school.get("primary_need") or "Other",
                **{k: school[k] for k in ("secondary_need", "ehcp_issued_on")
                   if school.get(k)},
                "date_added": today,
                "cycle_stage": "Assess", "status": "Active", "notes": notes})
            if send_text:
                _guard.log_sensitive("admissions send", "transfer to SEND "
                                     "register", applicant_id=aid)
            step("SEND register", True, f"Entry #{entry.entry_id} "
                 f"({entry.register_status}) for the SENCO to review")
        except Exception as e:  # noqa: BLE001
            carried["send"] = _held_note("SEND information", aid, e)
            step("SEND register", False, str(e))

    medical = (raw.get("medical") or "").strip()
    if medical:
        try:
            from education_system.systems.sixth_form.domain.pastoral.health.medical_records import (
                medical_records as _med,
            )
            old = _med.get_profile(sid)
            data: dict[str, Any] = {k: getattr(old, k) for k in (
                "nhs_number", "blood_group", "gp_name", "gp_practice",
                "gp_phone", "emergency_contact_name",
                "emergency_contact_phone", "emergency_contact_rel",
                "last_reviewed", "notes")} if old else {}
            block = (f"Medical information on admissions application {aid} "
                     f"({today}):\n{medical}")
            data["student_id"] = sid
            data["notes"] = (f"{data['notes']}\n\n{block}"
                             if data.get("notes") else block)
            _med.save_profile(data)
            _guard.log_sensitive("admissions medical",
                                 "transfer to medical profile",
                                 applicant_id=aid)
            step("medical", True, "Medical details added to the medical "
                 "profile notes for the medical team to review")
        except Exception as e:  # noqa: BLE001
            carried["medical"] = _held_note("Medical information", aid, e)
            step("medical", False, str(e))

    handover = (raw.get("safeguarding") or "").strip()
    if handover:
        source = (raw.get("received_from") or "").strip()
        try:
            from education_system.systems.sixth_form.domain.safeguarding import (
                safeguarding as _sg,
            )
            with _guard.system_actor("admissions-conversion",
                                     capabilities=(_access.SAFEGUARDING,)):
                receipt = _sg.report_concern(
                    sid,
                    "Safeguarding information handed over by the previous "
                    f"school{f' ({source})' if source else ''} on "
                    f"admissions applicant {aid}:\n{handover}",
                    category="Other", concern_type="Third-party report",
                    risk_level="Medium",
                    reported_by=converted_by or "Admissions conversion")
            _guard.log_sensitive("admissions safeguarding",
                                 "handover to safeguarding log",
                                 applicant_id=aid)
            step("safeguarding", True, f"Handover filed for the DSL as "
                 f"concern #{receipt.concern_id}")
        except Exception as e:  # noqa: BLE001
            carried["safeguarding"] = _held_note(
                "Safeguarding handover", aid, e)
            step("safeguarding", False, str(e))


def _carry_welfare(a: Applicant, sid: str, year: str, step: Any,
                   carried: dict[str, Any],
                   links: dict[str, Any] | None = None
                   ) -> list[tuple[str, str, bool]]:
    """Looked after / care leaver, young carer, free meals and bursary
    interest. Returns onboarding tasks to add to the checklist; the draft
    bursary application's id goes in ``links`` (the required bursary task
    is linked to it)."""
    tasks: list[tuple[str, str, bool]] = []
    if a.looked_after or a.care_leaver:
        what = " and ".join(x for x in (
            "looked after" if a.looked_after else None,
            "care leaver" if a.care_leaver else None) if x)
        tasks.append((f"Designated teacher: record care status ({what} on "
                      "application) — local authority, social worker, PEP",
                      "Wellbeing & Pastoral", True))
        step("looked after", True, f"{what.capitalize()}: onboarding task "
             "for the designated teacher (the care record needs the local "
             "authority)")
    if a.young_carer:
        tasks.append(("Young carer: complete the support record (flagged on "
                      "application)", "Wellbeing & Pastoral", True))
        step("young carer", True, "Onboarding task for the pastoral team "
             "(the support record needs who they care for)")
    if a.fsm_eligible:
        tasks.append(("Free meals: check 16-19 free meals eligibility and "
                      "record the entitlement (free meals in Year 11 on "
                      "application)", "Finance", True))
        step("free meals", True, "Onboarding task for finance (an "
             "entitlement needs evidence of the current basis)")
    if a.bursary_interest:
        basis = ("Looked-After Child" if a.looked_after else
                 "Care Leaver" if a.care_leaver else
                 "Free School Meals (Y11)" if a.fsm_eligible else None)
        try:
            from education_system.systems.sixth_form.domains.finance.domain.bursaries import (
                bursaries as _bursaries,
            )
            app = _bursaries.create_application({
                "student_id": sid,
                "bursary_type": ("Vulnerable Bursary"
                                 if basis in ("Looked-After Child",
                                              "Care Leaver")
                                 else "Discretionary Bursary"),
                "academic_year": year, "status": "Draft",
                "eligibility_basis": basis,
                "reason": f"Bursary interest on admissions application "
                          f"{a.applicant_id}",
                "notes": "Draft opened on conversion; the learner/family "
                         "still need to apply and provide evidence."})
            step("bursary", True, f"Draft bursary application "
                 f"#{app.application_id} ({app.bursary_type})")
            tasks.append(("Bursary applied for", "Finance", True))
            if links is not None:
                links["bursary_application_id"] = app.application_id
        except Exception as e:  # noqa: BLE001
            carried["bursary_interest"] = True
            tasks.append(("Bursary applied for", "Finance", True))
            step("bursary", False, f"Draft application not opened ({e}); "
                 "onboarding task added instead")
    return tasks


def _link_existing(applicant_id: str, student_id: str) -> Any:
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    student = _students.get_student(student_id)
    if student is None:
        raise ValidationError(f"No student {student_id!r}")
    with _connect() as conn:
        other = conn.execute(
            "SELECT applicant_id FROM admissions_applicants WHERE "
            "converted_student_id = ? AND applicant_id != ?",
            (student_id, applicant_id)).fetchone()
    if other:
        raise ValidationError(
            f"Student {student_id} is already linked to applicant "
            f"{other['applicant_id']}.")
    return student


def get_conversion(applicant_id: str) -> ConversionRecord | None:
    """What :func:`convert_to_student` carried across and each step."""
    import json as _json
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM admissions_conversions WHERE applicant_id = ?",
            (applicant_id,)).fetchone()
    if r is None:
        return None
    return ConversionRecord(
        applicant_id=r["applicant_id"], student_id=r["student_id"],
        converted_at=r["converted_at"], converted_by=r["converted_by"],
        academic_year=r["academic_year"], enrolment_id=r["enrolment_id"],
        checklist_id=r["checklist_id"],
        carried=_json.loads(r["carried_json"] or "{}"),
        steps=_json.loads(r["steps_json"] or "[]"))


def conversion_for_student(student_id: str) -> ConversionRecord | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT applicant_id FROM admissions_conversions "
            "WHERE student_id = ?", (student_id,)).fetchone()
    return get_conversion(r["applicant_id"]) if r else None
