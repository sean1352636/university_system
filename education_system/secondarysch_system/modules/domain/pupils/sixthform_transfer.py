"""Transfer secondary pupils into the sixth form system."""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass

from education_system.secondarysch_system.modules.domain.pupils.alumni import (
    alumni,
)
from education_system.secondarysch_system.modules.domain.pupils.pupils import (
    pupils as secondary_pupils,
)
from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
    ValidationError,
)
from education_system.shared.auth.db import connect as auth_connect
from education_system.shared.auth.password_manager import hash_password
from education_system.shared.auth.schema import initialise_auth_db
from education_system.sixthform_system.modules.domain.students.students import (
    students as sixth_students,
)

logger = logging.getLogger(__name__)

SIXTH_FORM_SYSTEM_KEY = "college"
SIXTH_FORM_ROLE = "student"
DEFAULT_DESTINATION = "Sixth Form System"


@dataclass(frozen=True)
class SixthFormTransferResult:
    source_pupil_id: str
    sixthform_student_id: str
    sixthform_email: str
    password: str
    alumni_id: str
    auth_user_id: int


def _generate_password() -> str:
    return f"Sixth-{secrets.token_urlsafe(9)}1!"


def _delete_auth_user(user_id: int) -> None:
    conn = auth_connect()
    try:
        for table in (
            "user_systems",
            "sessions",
            "password_history",
            "mfa_secrets",
            "mfa_recovery_codes",
            "security_questions",
        ):
            try:
                conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
            except Exception:
                logger.debug("Rollback skipped auth table %s", table, exc_info=True)
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()


def _ensure_not_already_alumni(pupil_id: str) -> None:
    alumni.init_db()
    with alumni._connect() as conn:
        row = conn.execute(
            "SELECT alumni_id FROM alumni WHERE pupil_id = ?",
            (pupil_id,),
        ).fetchone()
    if row:
        raise ValidationError(
            f"Pupil {pupil_id} is already alumni ({row['alumni_id']})"
        )


def _set_email_login(student, password: str) -> int:
    initialise_auth_db()
    conn = auth_connect()
    try:
        existing_email = conn.execute(
            "SELECT id FROM users WHERE username = ?",
            (student.email,),
        ).fetchone()
        student_id_user = conn.execute(
            "SELECT id FROM users WHERE username = ?",
            (student.student_id,),
        ).fetchone()
        if existing_email and (
                not student_id_user or existing_email["id"] != student_id_user["id"]):
            raise ValidationError(
                f"Login username {student.email} already exists."
            )

        pw_hash = hash_password(password)
        if student_id_user:
            user_id = student_id_user["id"]
            conn.execute(
                """
                UPDATE users
                   SET username = ?,
                       password_hash = ?,
                       display_name = ?,
                       email = ?,
                       is_active = 1,
                       failed_login_attempts = 0,
                       locked_until = NULL,
                       password_changed_at = datetime('now'),
                       updated_at = datetime('now')
                 WHERE id = ?
                """,
                (student.email, pw_hash, student.full_name, student.email, user_id),
            )
        else:
            cur = conn.execute(
                """
                INSERT INTO users (
                    username, password_hash, display_name, email,
                    password_changed_at
                ) VALUES (?, ?, ?, ?, datetime('now'))
                """,
                (student.email, pw_hash, student.full_name, student.email),
            )
            user_id = cur.lastrowid

        conn.execute(
            """
            INSERT OR REPLACE INTO user_systems (user_id, system_key, role)
            VALUES (?, ?, ?)
            """,
            (user_id, SIXTH_FORM_SYSTEM_KEY, SIXTH_FORM_ROLE),
        )
        conn.commit()
        return int(user_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def move_to_sixth_form(
    pupil_id: str,
    *,
    subject_1: str,
    subject_2: str,
    subject_3: str,
    destination: str | None = None,
    notes: str | None = None,
) -> SixthFormTransferResult:
    """Move a secondary pupil to sixth form and create their login."""
    pupil_id = (pupil_id or "").strip()
    if not pupil_id:
        raise ValidationError("Pupil ID is required")

    pupil = secondary_pupils.get_pupil(pupil_id)
    if pupil is None:
        raise ValidationError(f"No pupil with id {pupil_id}")
    _ensure_not_already_alumni(pupil_id)

    student = None
    auth_user_id: int | None = None
    alumnus = None
    password = _generate_password()

    try:
        try:
            student = sixth_students.create_student(
                {
                    "first_name": pupil.first_name,
                    "last_name": pupil.last_name,
                    "date_of_birth": pupil.date_of_birth or "",
                    "phone": pupil.phone or "",
                    "emergency_contact_name": pupil.parent_name or "",
                    "emergency_contact_phone": pupil.parent_phone or "",
                    "emergency_contact_relation": "Parent/Carer"
                    if pupil.parent_name or pupil.parent_phone else "",
                    "subject_1": subject_1,
                    "subject_2": subject_2,
                    "subject_3": subject_3,
                    "status": "Active",
                }
            )
        except Exception as exc:
            raise ValidationError(str(exc)) from exc
        auth_user_id = _set_email_login(student, password)

        alumnus = alumni.create_alumnus(
            {
                "pupil_id": pupil.pupil_id,
                "first_name": pupil.first_name,
                "last_name": pupil.last_name,
                "date_of_birth": pupil.date_of_birth or "",
                "year_left": pupil.year_group,
                "current_email": student.email,
                "current_phone": pupil.phone or "",
                "destination": destination or DEFAULT_DESTINATION,
                "status": "active",
                "notes": notes or "",
            }
        )

        secondary_pupils.delete_pupil(pupil.pupil_id)
    except Exception:
        logger.exception("Sixth form transfer failed for pupil %s", pupil_id)
        if alumnus is not None:
            try:
                alumni.delete_alumnus(alumnus.alumni_id)
            except Exception:
                logger.warning(
                    "Rollback could not delete alumnus %s",
                    alumnus.alumni_id,
                    exc_info=True,
                )
        if auth_user_id is not None:
            try:
                _delete_auth_user(auth_user_id)
            except Exception:
                logger.warning(
                    "Rollback could not delete auth user %s",
                    auth_user_id,
                    exc_info=True,
                )
        if student is not None:
            try:
                sixth_students.delete_student(student.student_id)
            except Exception:
                logger.warning(
                    "Rollback could not delete sixth form student %s",
                    student.student_id,
                    exc_info=True,
                )
        raise

    assert student is not None
    assert alumnus is not None
    assert auth_user_id is not None
    logger.info(
        "Moved secondary pupil %s to sixth form student %s and auth user %s",
        pupil.pupil_id,
        student.student_id,
        auth_user_id,
    )
    # Link the canonical journey across both phases, record the transition
    # and publish a durable progression event (best-effort; never raises).
    try:
        from education_system.shared.cross_system import progression
        progression.announce_progression(
            source_system="school",
            source_module="secondarysch_system.pupils.sixthform_transfer",
            first_name=pupil.first_name, last_name=pupil.last_name,
            date_of_birth=pupil.date_of_birth,
            source_student_id=pupil.pupil_id,
            target_student_id=student.student_id,
            subject_1=subject_1, subject_2=subject_2, subject_3=subject_3)
    except Exception:
        logger.debug("Cross-system progression announce skipped for "
                     "pupil %s", pupil.pupil_id, exc_info=True)
    return SixthFormTransferResult(
        source_pupil_id=pupil.pupil_id,
        sixthform_student_id=student.student_id,
        sixthform_email=student.email,
        password=password,
        alumni_id=alumnus.alumni_id,
        auth_user_id=auth_user_id,
    )
