"""Application boundary for university student CRUD and lifecycle changes.

CLI and GUI adapters should collect input and render :class:`LifecycleResult`;
all database decisions and durable follow-up work live here.
"""

from __future__ import annotations

import secrets
import json
import logging
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any, Callable, Mapping

from education_system.systems.university.infrastructure.database.db import transaction
from education_system.systems.university.infrastructure.events import transactional_publisher

logger = logging.getLogger(__name__)


class StudentStatus(StrEnum):
    PROVISIONING_PENDING = "Registration Pending"
    ACTIVE = "Active"
    INTERRUPTED = "Interrupted"
    WITHDRAWN = "Withdrawn"
    DEFERRED = "Deferred"
    SUSPENDED = "Suspended"
    COMPLETED = "Completed"
    CLOSED = "Closed"


class Gender(StrEnum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    UNSPECIFIED = "unspecified"


class StudentValidationError(ValueError):
    def __init__(self, errors: Mapping[str, str]):
        self.errors = dict(errors)
        super().__init__("; ".join(f"{key}: {value}" for key, value in self.errors.items()))


class PurgeControlError(PermissionError):
    pass


@dataclass(frozen=True)
class StudentCommand:
    first_name: str
    last_name: str
    dob: str
    course: str
    middle_name: str = ""
    title: str = ""
    gender: str = Gender.UNSPECIFIED
    student_id: str | None = None
    email_address: str | None = None
    entry_qualifications: str = ""
    ucas_tariff: int | None = None


@dataclass(frozen=True)
class LifecycleResult:
    student_id: str
    status: StudentStatus
    event_id: str
    changed_fields: tuple[str, ...] = field(default_factory=tuple)
    provisioning_error: str | None = None


def _clean_name(value: str, field_name: str) -> str:
    value = " ".join(str(value or "").strip().split())
    if not 1 <= len(value) <= 100:
        raise StudentValidationError({field_name: "must be between 1 and 100 characters"})
    if not any(ch.isalpha() for ch in value):
        raise StudentValidationError({field_name: "must contain a letter"})
    if any(not (ch.isalpha() or ch in " -'.") for ch in value):
        raise StudentValidationError({field_name: "contains unsupported characters"})
    return unicodedata.normalize("NFC", value)


def validate_student_command(command: StudentCommand) -> StudentCommand:
    errors: dict[str, str] = {}
    try:
        first_name = _clean_name(command.first_name, "first_name")
    except StudentValidationError as exc:
        errors.update(exc.errors)
        first_name = command.first_name
    try:
        last_name = _clean_name(command.last_name, "last_name")
    except StudentValidationError as exc:
        errors.update(exc.errors)
        last_name = command.last_name
    try:
        born = date.fromisoformat(command.dob)
        age = date.today().year - born.year - ((date.today().month, date.today().day) < (born.month, born.day))
        if not 16 <= age <= 100:
            errors["dob"] = "student age must be between 16 and 100"
    except (TypeError, ValueError):
        errors["dob"] = "must use YYYY-MM-DD"
    if not str(command.course or "").strip():
        errors["course"] = "is required"
    if command.student_id and (not command.student_id.isdigit() or len(command.student_id) != 7):
        errors["student_id"] = "must contain exactly seven digits"
    try:
        gender = Gender(str(command.gender or Gender.UNSPECIFIED).lower())
    except ValueError:
        errors["gender"] = "must be male, female, other, or unspecified"
        gender = Gender.UNSPECIFIED
    if errors:
        raise StudentValidationError(errors)
    return StudentCommand(
        **{**command.__dict__, "first_name": first_name, "last_name": last_name, "gender": gender.value}
    )


class StudentLifecycleService:
    """Single write boundary for canonical student records."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path

    def _allocate_id(self, conn) -> str:
        for _ in range(25):
            student_id = str(secrets.randbelow(9_000_000) + 1_000_000)
            if conn.execute("SELECT 1 FROM students WHERE student_id=?", (student_id,)).fetchone() is None:
                return student_id
        raise RuntimeError("Could not allocate a unique student ID")

    def create(self, command: StudentCommand, *, actor_id: str, idempotency_key: str) -> LifecycleResult:
        command = validate_student_command(command)
        with transaction(self.db_path) as conn:
            prior = conn.execute(
                "SELECT event_id, aggregate_id FROM university_event_outbox WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if prior:
                return LifecycleResult(str(prior["aggregate_id"]), StudentStatus.PROVISIONING_PENDING, str(prior["event_id"]))
            course = conn.execute(
                # Case-insensitive: the status column held mixed casing, and an
                # exact match silently hid a course from enrolment.
                "SELECT course_code, course_name FROM courses "
                "WHERE course_code=? AND LOWER(COALESCE(status, 'active'))='active'",
                (command.course,),
            ).fetchone()
            if course is None:
                raise StudentValidationError({"course": "is not in the active catalogue"})
            student_id = command.student_id or self._allocate_id(conn)
            email = command.email_address or f"C{student_id}@tees.ac.uk"
            if conn.execute(
                "SELECT 1 FROM students WHERE student_id=? OR lower(email_address)=lower(?)",
                (student_id, email),
            ).fetchone():
                raise StudentValidationError({"student_id": "student ID or email already exists"})
            born = date.fromisoformat(command.dob)
            today = date.today()
            age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
            now = datetime.now().isoformat(timespec="seconds")
            conn.execute(
                """INSERT INTO students
                     (student_id,email_address,title,first_name,middle_name,last_name,
                      gender,dob,age,course,registration_datetime,status,
                      enrollment_date,is_active,entry_qualifications,ucas_tariff)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?, ?,?,1,?,?)""",
                (student_id,email,command.title,command.first_name,command.middle_name,
                 command.last_name,command.gender,command.dob,age,command.course,now,
                 StudentStatus.PROVISIONING_PENDING.value,now,
                 command.entry_qualifications,command.ucas_tariff),
            )
            from education_system.systems.university.domains.academics.domain.services.admissions_selection import (
                enrol_student_in_curriculum,
            )
            curriculum = enrol_student_in_curriculum(
                conn, student_id, command.course, course["course_name"]
            )
            conn.execute(
                "UPDATE courses SET current_enrollment=current_enrollment+1 WHERE course_code=?",
                (command.course,),
            )
            payload = {"student_id": student_id, "email_address": email,
                       "course": command.course, "actor_id": actor_id,
                       "first_name": command.first_name,
                       "last_name": command.last_name,
                       "module_codes": [item["module_code"] for item in curriculum]}
            event_id = transactional_publisher.publish(
                conn, "student.provisioning.requested", payload,
                aggregate_id=student_id, idempotency_key=idempotency_key,
            )
        return LifecycleResult(student_id, StudentStatus.PROVISIONING_PENDING, event_id)

    def provision(self, student_id: str, *, auth: Any = None) -> LifecycleResult:
        """Process a pending create event idempotently and record failures.

        The canonical row, curriculum and event already exist atomically. This
        processor may be called immediately by desktop adapters and safely
        retried by an outbox worker after a crash or external-system outage.
        """
        with transaction(self.db_path) as conn:
            row = conn.execute(
                """SELECT * FROM university_event_outbox
                     WHERE aggregate_id=? AND event_name='student.provisioning.requested'
                     ORDER BY available_at DESC LIMIT 1""",
                (student_id,),
            ).fetchone()
            if row is None:
                raise StudentValidationError({"student_id": "has no provisioning request"})
            if row["delivered_at"]:
                return LifecycleResult(student_id, StudentStatus.ACTIVE, row["event_id"])
            payload = json.loads(row["payload_json"])
        failures: list[str] = []
        from education_system.systems.university.services.student_provisioning import (
            default_student_password,
            provision_student_login,
        )
        login = provision_student_login(
            auth, username=student_id,
            password=default_student_password(None, None),
            email=payload["email_address"], first_name=payload["first_name"],
            last_name=payload["last_name"],
        )
        if not login["shared_ok"]:
            failures.append("shared sign-in account")
        if not login["legacy_ok"]:
            failures.append("university sign-in account")
        if not login.get("activation_sent"):
            failures.append("activation email")
        for module_code in payload.get("module_codes", []):
            for label, operation in self._module_provisioners():
                try:
                    operation(student_id, module_code)
                except Exception as exc:
                    logger.warning("%s failed for %s/%s: %s", label, student_id, module_code, exc)
                    failures.append(f"{label}:{module_code}")
        try:
            from education_system.systems.university.domains.learners.interfaces.gui.students.student_crud_gui.sync.chat_rooms import _auto_join_module_chat_rooms
            _auto_join_module_chat_rooms(
                student_id=student_id, email_address=payload["email_address"],
                first_name=payload["first_name"], last_name=payload["last_name"],
                module_codes=payload.get("module_codes", []),
            )
        except Exception as exc:
            logger.warning("chat provisioning failed for %s: %s", student_id, exc)
            failures.append("module chat")
        with transaction(self.db_path) as conn:
            if failures:
                error = ", ".join(sorted(set(failures)))
                conn.execute(
                    "UPDATE university_event_outbox SET attempts=attempts+1,last_error=? WHERE event_id=?",
                    (error, row["event_id"]),
                )
                return LifecycleResult(
                    student_id, StudentStatus.PROVISIONING_PENDING, row["event_id"],
                    provisioning_error=error,
                )
            conn.execute(
                "UPDATE students SET status='Active',is_active=1 WHERE student_id=?",
                (student_id,),
            )
            conn.execute(
                "UPDATE university_event_outbox SET attempts=attempts+1,last_error=NULL,delivered_at=CURRENT_TIMESTAMP WHERE event_id=?",
                (row["event_id"],),
            )
        return LifecycleResult(student_id, StudentStatus.ACTIVE, row["event_id"])

    @staticmethod
    def _module_provisioners():
        from education_system.systems.university.domains.finance.domain.services.enrolment_fees import assess_module_enrolment_fee
        from education_system.systems.university.plugins.campus_commerce.domain.textbooks.services.library_holds import place_holds_for_enrolment
        from education_system.systems.university.domains.academics.domain.services.course_management.timetable_sync import sync_for_student_enrolment
        return (("fee", assess_module_enrolment_fee), ("library hold", place_holds_for_enrolment),
                ("timetable", sync_for_student_enrolment))

    def update(self, student_id: str, changes: Mapping[str, Any], *, actor_id: str,
               reason: str, idempotency_key: str) -> LifecycleResult:
        allowed = {"title", "first_name", "middle_name", "last_name", "gender", "dob",
                   "course", "pronouns", "emergency_contact"}
        unknown = set(changes) - allowed
        if unknown:
            raise StudentValidationError({key: "cannot be updated" for key in unknown})
        if not reason.strip():
            raise StudentValidationError({"reason": "is required"})
        normalized = dict(changes)
        for key in ("first_name", "last_name"):
            if key in normalized:
                normalized[key] = _clean_name(normalized[key], key)
        with transaction(self.db_path) as conn:
            student = conn.execute("SELECT * FROM students WHERE student_id=?", (student_id,)).fetchone()
            if not student:
                raise StudentValidationError({"student_id": "does not exist"})
            if "course" in normalized and conn.execute(
                "SELECT 1 FROM courses WHERE course_code=? "
                "AND LOWER(COALESCE(status, 'active'))='active'", (normalized["course"],)
            ).fetchone() is None:
                raise StudentValidationError({"course": "is not in the active catalogue"})
            if "dob" in normalized:
                born = date.fromisoformat(normalized["dob"])
                today = date.today()
                normalized["age"] = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
                allowed.add("age")
            if "course" in normalized and normalized["course"] != student["course"]:
                from education_system.systems.university.domains.academics.domain.services.admissions_selection import (
                    enrol_student_in_curriculum,
                )
                conn.execute("DELETE FROM student_modules WHERE student_id=?", (student_id,))
                course_row = conn.execute(
                    "SELECT course_name FROM courses WHERE course_code=?", (normalized["course"],)
                ).fetchone()
                enrol_student_in_curriculum(
                    conn, student_id, normalized["course"], course_row["course_name"]
                )
            assignments = ", ".join(f"{key}=?" for key in normalized)
            conn.execute(f"UPDATE students SET {assignments} WHERE student_id=?", (*normalized.values(), student_id))  # nosec B608
            if "first_name" in normalized or "last_name" in normalized:
                conn.execute(
                    """UPDATE users SET first_name=COALESCE(?,first_name),
                           last_name=COALESCE(?,last_name),updated_at=CURRENT_TIMESTAMP
                         WHERE student_id=?""",
                    (normalized.get("first_name"), normalized.get("last_name"), student_id),
                )
            payload = {"student_id": student_id, "changes": normalized,
                       "reason": reason, "actor_id": actor_id}
            event_id = transactional_publisher.publish(
                conn, "student.updated", payload, aggregate_id=student_id,
                idempotency_key=idempotency_key,
            )
        return LifecycleResult(student_id, StudentStatus(student["status"]), event_id, tuple(normalized))

    def deactivate(self, student_id: str, *, actor_id: str, reason: str,
                   idempotency_key: str) -> LifecycleResult:
        return self._set_active(student_id, False, actor_id, reason, idempotency_key)

    def restore(self, student_id: str, *, actor_id: str, reason: str,
                idempotency_key: str) -> LifecycleResult:
        return self._set_active(student_id, True, actor_id, reason, idempotency_key)

    def _set_active(self, student_id: str, active: bool, actor_id: str, reason: str,
                    idempotency_key: str) -> LifecycleResult:
        if not reason.strip():
            raise StudentValidationError({"reason": "is required"})
        status = StudentStatus.ACTIVE if active else StudentStatus.WITHDRAWN
        with transaction(self.db_path) as conn:
            cur = conn.execute(
                "UPDATE students SET is_active=?, status=? WHERE student_id=?",
                (int(active), status.value, student_id),
            )
            if cur.rowcount != 1:
                raise StudentValidationError({"student_id": "does not exist"})
            conn.execute("UPDATE users SET is_active=? WHERE student_id=?", (int(active), student_id))
            event_id = transactional_publisher.publish(
                conn, "student.restored" if active else "student.deactivated",
                {"student_id": student_id, "reason": reason, "actor_id": actor_id},
                aggregate_id=student_id, idempotency_key=idempotency_key,
            )
        return LifecycleResult(student_id, status, event_id)

    def impact_preview(self, student_id: str) -> dict[str, int]:
        with transaction(self.db_path) as conn:
            if conn.execute("SELECT 1 FROM students WHERE student_id=?", (student_id,)).fetchone() is None:
                raise StudentValidationError({"student_id": "does not exist"})
            result: dict[str, int] = {}
            for table, column in (("student_modules", "student_id"), ("student_grades", "student_id"),
                                  ("attendance", "student_id"), ("users", "student_id")):
                exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
                result[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {column}=?", (student_id,)).fetchone()[0]) if exists else 0  # nosec B608
            return result

    def purge(self, student_id: str, *, actor_id: str, approved_by: str, reason: str,
              case_reference: str, reauthenticated: bool,
              legal_hold_check: Callable[[str], bool], idempotency_key: str) -> LifecycleResult:
        """Queue a purge under dual control; no adapter may delete inline."""
        if not reason.strip() or not case_reference.strip():
            raise PurgeControlError("Purge requires a reason and case reference")
        if not reauthenticated or not approved_by or approved_by == actor_id:
            raise PurgeControlError("Purge requires reauthentication and independent approval")
        if legal_hold_check(student_id):
            raise PurgeControlError("Student is subject to a retention/legal hold")
        with transaction(self.db_path) as conn:
            student = conn.execute("SELECT status FROM students WHERE student_id=?", (student_id,)).fetchone()
            if not student:
                raise StudentValidationError({"student_id": "does not exist"})
            if student["status"] != StudentStatus.WITHDRAWN.value:
                raise PurgeControlError("Student must be deactivated before purge")
            event_id = transactional_publisher.publish(
                conn, "student.purge.requested",
                {"student_id": student_id, "reason": reason,
                 "case_reference": case_reference, "actor_id": actor_id,
                 "approved_by": approved_by},
                aggregate_id=student_id, idempotency_key=idempotency_key,
            )
        return LifecycleResult(student_id, StudentStatus.WITHDRAWN, event_id)


__all__ = ["Gender", "LifecycleResult", "PurgeControlError", "StudentCommand",
           "StudentLifecycleService", "StudentStatus", "StudentValidationError",
           "validate_student_command"]
