"""Sixth Form's side of the platform transition contract."""

from __future__ import annotations

import logging
from typing import Any

from education_system.platform.cross_system.adapters import registry
from education_system.platform.cross_system.adapters.base import (
    AdapterError, ApplicantResult, EnrolmentResult, ExportResult,
    HandoverRequest, PhaseAdapter,
)

logger = logging.getLogger(__name__)

_ASCII_UPPER = str.maketrans("abcdefghijklmnopqrstuvwxyz", "ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def _sqlite_upper(text: str) -> str:
    """SQLite's ``UPPER()``: folds ASCII letters only."""
    return text.translate(_ASCII_UPPER)


def _reroute_handover(application_id: int) -> None:
    """Re-check the university handover after the university settles the
    application (e.g. confirms the Insurance place). Best-effort."""
    try:
        from education_system.systems.sixth_form.domain.progression import (
            university_handover,
        )
        university_handover.reroute_for_ucas_application(application_id)
    except Exception:
        logger.exception("Could not re-check the university handover for "
                         "application #%s", application_id)


class SixthFormAdapter(PhaseAdapter):
    system = "sixth_form"

    # ── Learner logins ──────────────────────────────────────────────

    learner_login_roles = ("student",)

    def learner_ids_for_login(self, account: dict) -> list[str]:
        """The student whose id is this login's username.

        Every student's login is provisioned with ``username = student_id``
        (``students._provision_login_account``). Parent-portal accounts
        share the ``users`` table but hold the ``parent`` role, so they are
        never asked.
        """
        from education_system.systems.sixth_form.domain.learners.students import students

        username = str(account.get("username") or "").strip()
        if not username:
            return []
        students.init_db()
        with students._connect() as conn:
            rows = conn.execute(
                "SELECT student_id FROM students WHERE UPPER(student_id) = UPPER(?)",
                (username,)).fetchall()
        return [str(r[0]) for r in rows]

    def learner_ids_for_logins(self, accounts: list[dict]) -> dict[int, list[str]]:
        """:meth:`learner_ids_for_login` for many logins, in one query.

        Same rule: the student whose id matches the username, compared the
        way SQLite's ``UPPER()`` does (ASCII letters only).
        """
        from education_system.systems.sixth_form.domain.learners.students import students

        students.init_db()
        with students._connect() as conn:
            by_key: dict[str, list[str]] = {}
            for (sid,) in conn.execute("SELECT student_id FROM students"):
                by_key.setdefault(_sqlite_upper(str(sid)), []).append(str(sid))
        out: dict[int, list[str]] = {}
        for account in accounts:
            username = str(account.get("username") or "").strip()
            out[int(account["id"])] = (list(by_key.get(_sqlite_upper(username), []))
                                       if username else [])
        return out

    def create_applicant(self, handover: HandoverRequest) -> ApplicantResult:
        if handover.source_system == "secondary":
            # A Year 11 pupil from the school: an admissions applicant (with
            # GCSEs and SEN details), not a student yet.
            from education_system.systems.sixth_form.domain.admissions import (
                secondary_handover,
            )
            return ApplicantResult(
                local_applicant_id=secondary_handover.receive(handover),
                year_group="12", notes="Year 11 applicant from the secondary school")
        from education_system.systems.sixth_form.domain.learners.students import students

        students.init_db()
        with students._connect() as conn:
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(students)")}
            if "journey_id" not in columns:
                conn.execute("ALTER TABLE students ADD COLUMN journey_id TEXT")
                conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_sf_students_journey "
                             "ON students(journey_id) WHERE journey_id IS NOT NULL")
            existing = conn.execute(
                "SELECT student_id FROM students WHERE journey_id = ?",
                (handover.journey_id,)).fetchone()
        if existing:
            return ApplicantResult(local_applicant_id=existing["student_id"],
                                   notes="existing journey record")

        identity = handover.get("learner_identity") or handover.get("student_identity") or {}
        contact = handover.get("contact_details") or {}
        request = (handover.get("transfer_request")
                   or handover.get("application_details") or {})
        subjects = request.get("subjects") or []
        if len(subjects) != 3 or len(set(subjects)) != 3:
            raise AdapterError("Three distinct A-level subject choices are required")
        from education_system.systems.sixth_form.domain.learners.students.system_actor import (
            unless_signed_in,
        )
        # Driven by another phase's handover or drainer: nobody is signed
        # in to the sixth form, so the write runs as the named system.
        with unless_signed_in("cross-system-intake"):
            student = students.create_student(allow_duplicate=True, data={
                "first_name": identity.get("first_name") or identity.get("given_name"),
                "last_name": identity.get("last_name") or identity.get("family_name"),
                "date_of_birth": identity.get("date_of_birth") or identity.get("dob"),
                "phone": contact.get("phone"),
                "subject_1": subjects[0], "subject_2": subjects[1],
                "subject_3": subjects[2],
                "status": "Inactive",
            })
        with students._connect() as conn:
            conn.execute("UPDATE students SET journey_id = ? WHERE student_id = ?",
                         (handover.journey_id, student.student_id))
            conn.commit()
        return ApplicantResult(local_applicant_id=student.student_id,
                               year_group="12", notes="FE transfer applicant")

    def update_applicant_results(self, handover: HandoverRequest) -> None:
        if handover.source_system != "secondary":
            raise self._not_implemented("update_applicant_results")
        from education_system.systems.sixth_form.domain.admissions import secondary_handover
        secondary_handover.receive_results(handover)

    def update_applicant_choices(self, handover: HandoverRequest) -> None:
        if handover.source_system != "secondary":
            raise self._not_implemented("update_applicant_choices")
        from education_system.systems.sixth_form.domain.admissions import secondary_handover
        secondary_handover.receive_choices(handover)

    def course_options(self, gcse_results: list[dict]) -> list[dict]:
        """Every A-level offered, checked against these GCSE results using
        the admissions entry requirements (see
        ``entry_requirements.course_eligibility``). Like offered_subjects,
        not part of the PhaseAdapter contract: callers use getattr."""
        from education_system.systems.sixth_form.domain.admissions import entry_requirements
        return entry_requirements.course_eligibility(gcse_results,
                                                     list(self.offered_subjects()))

    def option_blocks(self, subjects: list[str],
                      journey_id: str | None = None) -> dict[str, Any]:
        """Whether these A-levels fit the option blocks for the coming
        intake, with places left (``option_blocks.programme_check``). The
        learner's own application (by *journey_id*) doesn't count against
        the places. Not part of the PhaseAdapter contract: callers use
        getattr."""
        from education_system.systems.sixth_form.domain.academics.qualifications import (
            option_blocks,
        )
        from education_system.systems.sixth_form.domain.admissions import (
            secondary_handover,
        )
        # Reading programme places needs admissions access: the school asks
        # as the handover's system actor, as receive() does.
        access = secondary_handover._access()
        with secondary_handover._guard.system_actor(secondary_handover.ACTOR,
                                                    capabilities=(access.ADMISSIONS,)):
            own = secondary_handover._existing(journey_id) if journey_id else None
            return option_blocks.programme_check(list(subjects or []),
                                                 exclude_applicant=own)

    def create_enrolment(self, journey_id: str, application_id: str | None = None,
                         **details: Any) -> EnrolmentResult:
        from education_system.systems.sixth_form.domain.learners.students import students

        students.init_db()
        with students._connect() as conn:
            columns = {r["name"] for r in conn.execute("PRAGMA table_info(students)")}
            row = (conn.execute(
                "SELECT student_id, status FROM students WHERE journey_id = ?",
                (journey_id,)).fetchone() if "journey_id" in columns else None)
        if row is None:
            # A secondary handover is an admissions applicant: it becomes a
            # student only by conversion, which admissions staff do.
            from education_system.systems.sixth_form.domain.admissions import (
                secondary_handover,
            )
            sid = secondary_handover.converted_student(journey_id)
            if sid is None:
                raise AdapterError(f"No sixth-form applicant for journey {journey_id}"
                                   " - convert the applicant in Admissions first")
            return EnrolmentResult(local_student_id=sid, year_group="12",
                                   start_date=details.get("start_date"))
        with students._connect() as conn:
            conn.execute("UPDATE students SET status = 'Active' WHERE student_id = ?",
                         (row["student_id"],))
            conn.commit()
        return EnrolmentResult(local_student_id=row["student_id"], year_group="12",
                               start_date=details.get("start_date"))

    def export_handover(self, local_student_id: str,
                        consent: bool | set[str] | None = None, *,
                        destination_system: str | None = None) -> ExportResult:
        from education_system.systems.sixth_form.domain.learners.students import students

        student = students.get_student(local_student_id)
        if student is None:
            raise AdapterError(f"No sixth-form learner {local_student_id} to export")
        subjects = [s for s in (student.subject_1, student.subject_2, student.subject_3) if s]
        return ExportResult(record={
            "student_identity": {
                "first_name": student.first_name,
                "last_name": student.last_name,
                "date_of_birth": student.date_of_birth,
            },
            "contact_details": {"email": student.email, "phone": student.phone},
            "current_programme": {"subjects": subjects, "status": student.status},
        }, local_student_id=local_student_id)

    def close_enrolment(self, local_student_id: str, reason: str,
                        **details: Any) -> None:
        from education_system.systems.sixth_form.domain.learners.students import students

        if students.get_student(local_student_id) is None:
            raise AdapterError(f"No sixth-form learner {local_student_id} to close")
        student = students.get_student(local_student_id)
        assert student is not None
        from education_system.systems.sixth_form.domain.learners.students.system_actor import (
            unless_signed_in,
        )
        with unless_signed_in("cross-system-leaver"):
            self._close_student(local_student_id, student)

    @staticmethod
    def _close_student(local_student_id: str, student: Any) -> None:
        from education_system.systems.sixth_form.domain.learners.students import students

        students.update_student(local_student_id, {
            "first_name": student.first_name,
            "middle_name": student.middle_name,
            "last_name": student.last_name,
            "title": student.title,
            "gender": student.gender,
            "date_of_birth": student.date_of_birth,
            "phone": student.phone,
            "emergency_contact_name": student.emergency_contact_name,
            "emergency_contact_phone": student.emergency_contact_phone,
            "emergency_contact_relation": student.emergency_contact_relation,
            "subject_1": student.subject_1,
            "subject_2": student.subject_2,
            "subject_3": student.subject_3,
            "status": "Left",
        })

    def offered_subjects(self) -> tuple[str, ...]:
        """The A-level catalogue, for a sending college to check choices against.

        Not part of the PhaseAdapter contract — only a destination that admits
        onto a fixed subject list has one — so callers reach it with getattr
        and treat its absence as "no list published".
        """
        from education_system.systems.sixth_form.domain.learners.students.students import (
            A_LEVEL_SUBJECTS,
        )

        return tuple(A_LEVEL_SUBJECTS)


    # ── Admissions reads for a university (optional contract) ───────

    def ucas_choices_for_institution(self, institution_names: set[str] | None = None,
                                     *, include_placed: bool = False
                                     ) -> list[dict]:
        from education_system.systems.sixth_form.domain.progression.university import ucas

        return ucas.choices_for_institution(
            set(institution_names) if institution_names is not None else None,
            include_placed=include_placed)

    def ucas_choice(self, choice_id: int) -> dict | None:
        from education_system.systems.sixth_form.domain.progression.university import ucas

        try:
            return ucas.choice_detail(int(choice_id))
        except (TypeError, ValueError):
            return None

    def ucas_application(self, application_id: int) -> dict | None:
        from education_system.systems.sixth_form.domain.progression.university import ucas

        return ucas.application_detail(int(application_id))

    def ucas_record_reply(self, choice_id: int,
                          final_decision: str | None) -> dict:
        from education_system.systems.sixth_form.domain.progression.university import ucas

        try:
            ucas.record_reply(int(choice_id), final_decision)
        except ucas.ValidationError as exc:
            raise AdapterError(str(exc)) from exc
        out = ucas.choice_detail(int(choice_id))
        if out is None:
            raise AdapterError(f"No UCAS choice with id {choice_id}")
        return out

    def ucas_set_application_status(self, application_id: int,
                                    status: str) -> dict:
        from education_system.systems.sixth_form.domain.progression.university import ucas

        try:
            ucas.set_application_status(int(application_id), status)
        except ucas.ValidationError as exc:
            raise AdapterError(str(exc)) from exc
        _reroute_handover(int(application_id))
        out = ucas.application_detail(int(application_id))
        assert out is not None
        return out

    def exam_results_for_admissions(self, student_id: str, *,
                                    year: int | None = None) -> list[dict]:
        """Every result for the learner, embargoed ones marked unreleased.

        ``released`` is the sixth form's own visibility rule (released, or
        the embargo has passed); ``release_at`` is the embargo time, or the
        recorded release time when there was no embargo.
        """
        from education_system.systems.sixth_form.domain.assessment.exam_results import (
            exam_results as _results,
        )

        if not student_id:
            return []
        rows = _results.results_for_student(str(student_id), year=year,
                                            released_only=False)
        if not rows:
            return []
        visible = {r.result.result_id for r in _results.results_for_student(
            str(student_id), year=year, released_only=True)}
        qual_types: dict[str, str | None] = {}

        def _qual(subject: str) -> str | None:
            if subject not in qual_types:
                try:
                    from education_system.systems.sixth_form.domain.academics.qualifications import (
                        learning_aims,
                    )
                    qual_types[subject] = learning_aims.qualification_type_for(
                        str(student_id), subject)
                except Exception:
                    qual_types[subject] = None
            return qual_types[subject]

        out = []
        for row in rows:
            res = row.result
            release_at = res.embargo_until or res.released_at or None
            out.append({
                "subject": row.subject,
                "grade": res.grade,
                "qualification_type": _qual(row.subject),
                "released": res.result_id in visible,
                "release_at": (release_at.replace(" ", "T")
                               if isinstance(release_at, str) else None),
                "season": row.season,
                "year": row.year,
                # Beyond the contract minimum.
                "exam_board": row.exam_board,
                "paper_code": row.paper_code,
            })
        return out

    def learner_summary(self, student_id: str) -> dict | None:
        from education_system.systems.sixth_form.domain.learners.students import students

        if not student_id:
            return None
        student = students.get_student(str(student_id))
        if student is None:
            return None
        journey_id = None
        try:
            with students._connect() as conn:
                cols = {r["name"] for r in conn.execute("PRAGMA table_info(students)")}
                if "journey_id" in cols:
                    row = conn.execute(
                        "SELECT journey_id FROM students WHERE student_id = ?",
                        (student.student_id,)).fetchone()
                    journey_id = row["journey_id"] if row else None
        except Exception:
            journey_id = None
        if not journey_id:
            try:
                from education_system.platform.cross_system import identity_service
                anchor = identity_service.find_by_student("sixth_form", student.student_id)
                journey_id = anchor["journey_id"] if anchor else None
            except Exception:
                journey_id = None
        return {
            "id": student.student_id,
            "student_id": student.student_id,
            "title": student.title,
            "first_name": student.first_name,
            "middle_name": student.middle_name,
            "last_name": student.last_name,
            "full_name": student.full_name,
            "gender": student.gender,
            "dob": student.date_of_birth,
            "date_of_birth": student.date_of_birth,
            "email": student.email,
            "journey_id": journey_id,
            "status": student.status,
            "subjects": list(student.subjects),
        }

    def notify_learner(self, student_id: str, *, subject: str, body: str,
                       sender: str) -> bool:
        from education_system.systems.sixth_form.domain.progression.university import (
            ucas_events,
        )

        return ucas_events.notify_learner(student_id, subject=subject,
                                          body=body, sender=sender)

    def send_learner_template(self, student_id: str, template: str,
                              context: dict) -> int | None:
        from education_system.systems.sixth_form.domain.learners.students import students
        from education_system.systems.sixth_form.domains.communications.domain.messages import (
            email_templates,
        )

        student = students.get_student(str(student_id)) if student_id else None
        if student is None:
            return None
        msg = email_templates.send_from_template(
            template, dict(context), to_name=student.full_name,
            to_address=student.email, student_id=student.student_id)
        return msg.message_id

    def close_leaver_logins(self, student_id: str) -> None:
        from education_system.systems.sixth_form.domain.learners.students import students

        students.disable_leaver_login(str(student_id))
        # Parent logins that existed only to follow this learner; one that
        # still covers a sibling here is left alone by the sixth form.
        students.disable_orphaned_parent_logins(str(student_id))

    def mark_transferred(self, student_id: str, *, moved_by: str) -> None:
        from education_system.systems.sixth_form.domain.learners.students import transfers
        from education_system.systems.sixth_form.domain.learners.students.system_actor import (
            unless_signed_in,
        )
        # The university's import / transfer drainer has nobody signed in
        # to the sixth form; a signed-in sixth form user is checked as
        # themselves.
        with unless_signed_in("cross-system-transfer"):
            transfers.mark_transferred(str(student_id), moved_by=moved_by)

    def handover_readiness(self, student_id: str) -> Any:
        from education_system.systems.sixth_form.domain.progression import (
            handover_eligibility,
        )

        return handover_eligibility.assess_id(str(student_id))

    def build_handover(self, student_id: str) -> Any:
        from education_system.systems.sixth_form.domain.learners.students import students
        from education_system.systems.sixth_form.domain.progression import (
            university_handover,
        )

        student = students.get_student(str(student_id))
        if student is None:
            raise AdapterError(f"No sixth-form learner {student_id}")
        return university_handover.build(student)

    def right_to_study_note(self) -> str:
        from education_system.systems.sixth_form.domain.progression import (
            handover_eligibility,
        )

        return handover_eligibility.RIGHT_TO_STUDY_NOTE


    # ── Published facts and records other systems may ask for ──────────

    def list_learners(self) -> list[dict]:
        """Every learner record, as plain dicts (id, names, status, DOB)."""
        from education_system.systems.sixth_form.domain.learners.students import students

        return [{"student_id": s.student_id,
                 "full_name": getattr(s, "full_name", None)
                 or f"{getattr(s, 'first_name', '')} {getattr(s, 'last_name', '')}".strip(),
                 "first_name": getattr(s, "first_name", None),
                 "last_name": getattr(s, "last_name", None),
                 "status": getattr(s, "status", None),
                 "date_of_birth": getattr(s, "date_of_birth", None)}
                for s in students.list_students()]

    def handover_consent(self, student_id: str) -> dict | None:
        """The learner's recorded consent to hand data to a university."""
        from education_system.systems.sixth_form.domain.progression import (
            university_handover,
        )

        consent = university_handover.consent_for(str(student_id))
        return dict(consent) if consent else None

    def medical_record(self, student_id: str) -> dict:
        """The learner's medical profile, conditions, medications and allergies."""
        import dataclasses

        from education_system.systems.sixth_form.domain.pastoral.health.medical_records import (
            medical_records as mr,
        )

        def _d(obj):
            if obj is None:
                return None
            if dataclasses.is_dataclass(obj):
                return dataclasses.asdict(obj)
            return dict(obj) if isinstance(obj, dict) else dict(vars(obj))

        sid = str(student_id)
        mr.init_db()
        return {"profile": _d(mr.get_profile(sid)),
                "conditions": [_d(c) for c in mr.list_conditions(student_id=sid)],
                "medications": [_d(m) for m in mr.list_medications(student_id=sid)],
                "allergies": [_d(a) for a in mr.list_allergies(student_id=sid)]}


ADAPTER = SixthFormAdapter()


def register() -> SixthFormAdapter:
    registry.register(ADAPTER, replace=True)
    return ADAPTER


__all__ = ["SixthFormAdapter", "ADAPTER", "register"]
