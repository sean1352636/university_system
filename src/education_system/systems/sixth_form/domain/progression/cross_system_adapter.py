"""Sixth Form's side of the platform transition contract."""

from __future__ import annotations

from typing import Any

from education_system.platform.cross_system.adapters import registry
from education_system.platform.cross_system.adapters.base import (
    AdapterError, ApplicantResult, EnrolmentResult, ExportResult,
    HandoverRequest, PhaseAdapter,
)


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

    def create_applicant(self, handover: HandoverRequest) -> ApplicantResult:
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
        student = students.create_student({
            "first_name": identity.get("first_name") or identity.get("given_name"),
            "last_name": identity.get("last_name") or identity.get("family_name"),
            "date_of_birth": identity.get("date_of_birth") or identity.get("dob"),
            "phone": contact.get("phone"),
            "subject_1": subjects[0], "subject_2": subjects[1], "subject_3": subjects[2],
            "status": "Inactive",
        })
        with students._connect() as conn:
            conn.execute("UPDATE students SET journey_id = ? WHERE student_id = ?",
                         (handover.journey_id, student.student_id))
            conn.commit()
        return ApplicantResult(local_applicant_id=student.student_id,
                               year_group="12", notes="FE transfer applicant")

    def create_enrolment(self, journey_id: str, application_id: str | None = None,
                         **details: Any) -> EnrolmentResult:
        from education_system.systems.sixth_form.domain.learners.students import students

        students.init_db()
        with students._connect() as conn:
            row = conn.execute(
                "SELECT student_id, status FROM students WHERE journey_id = ?",
                (journey_id,)).fetchone()
            if row is None:
                raise AdapterError(f"No sixth-form applicant for journey {journey_id}")
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


ADAPTER = SixthFormAdapter()


def register() -> SixthFormAdapter:
    registry.register(ADAPTER, replace=True)
    return ADAPTER


__all__ = ["SixthFormAdapter", "ADAPTER", "register"]
