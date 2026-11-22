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

from education_system.systems.university.application.students import record_rules
from education_system.systems.university.application.students import registration_extras
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
    NON_BINARY = "non-binary"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer not to say"
    #: Held when nothing was given (API, imports); not offered on the forms.
    UNSPECIFIED = "unspecified"


#: The gender options every system's add form offers. The university stores
#: the lower-case form (``Gender``), as it always has for male/female/other.
GENDER_OPTIONS = ("Female", "Male", "Non-binary", "Other", "Prefer not to say")


def gender_label(value) -> str:
    """``"non-binary"`` -> ``"Non-binary"``; anything else as held."""
    text = str(value or "")
    return next((o for o in GENDER_OPTIONS if o.lower() == text.lower()), text)


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
    phone: str = ""
    address: str = ""
    personal_email: str = ""
    nationality: str = ""
    mode_of_study: str = ""
    fee_status: str = ""
    entry_route: str = ""
    entry_override_reason: str = ""
    preferred_name: str = ""
    postcode: str = ""
    address_line1: str = ""
    address_line2: str = ""
    town: str = ""
    notes: str = ""
    #: Not stored on ``students``: the emergency contact and medical notes go
    #: to the health record (``registration_extras``).
    emergency_contact_name: str = ""
    emergency_contact_relationship: str = ""
    emergency_contact_phone: str = ""
    medical_notes: str = ""
    #: Create even though a student with the same name and DOB exists.
    allow_duplicate: bool = False


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
        errors["gender"] = f"must be one of {', '.join(GENDER_OPTIONS)}"
        gender = Gender.UNSPECIFIED
    errors.update(record_rules.validate_details(command.__dict__))
    errors.update(record_rules.validate_registration(command.__dict__))
    if errors:
        raise StudentValidationError(errors)
    details = record_rules.settle_address(record_rules.normalise_details(
        {k: getattr(command, k) for k in record_rules.CONTACT_FIELDS}))
    return StudentCommand(
        **{**command.__dict__, **{k: v or "" for k, v in details.items()},
           "first_name": first_name, "last_name": last_name, "gender": gender.value,
           "emergency_contact_relationship": record_rules.relationship_choice(
               command.emergency_contact_relationship)}
    )


_DETAIL_COLUMNS = record_rules.CONTACT_FIELDS + ("entry_route", "entry_override_reason")


def _refuse_duplicate(conn, command: StudentCommand) -> None:
    if command.allow_duplicate:
        return
    matches = record_rules.find_duplicates(conn, command.first_name, command.last_name,
                                           command.dob)
    if matches:
        listed = ", ".join(f"{m['student_id']} ({m['name']}, {m['course']}, {m['status']})"
                           for m in matches)
        raise StudentValidationError({"duplicate": f"possible duplicate of {listed}"})


def _store_details(conn, student_id: str, command: StudentCommand) -> None:
    """Contact and entry details, for the columns this database has."""
    record_rules.ensure(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(students)")}
    values = {k: getattr(command, k) or None for k in _DETAIL_COLUMNS if k in cols}
    if values:
        conn.execute(f"UPDATE students SET {', '.join(f'{k}=?' for k in values)} "  # nosec B608
                     "WHERE student_id=?", (*values.values(), student_id))


def _lifecycle_tables(conn) -> bool:
    return conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name IN "
                        "('student_lifecycle_history', 'student_lifecycle_actions')"
                        ).fetchone()[0] == 2


class StudentLifecycleService:
    """Single write boundary for canonical student records."""

    def __init__(self, db_path: str | None = None, auth_db_path: str | None = None):
        self.db_path = db_path
        #: Shared sign-in is only switched on/off against the live auth.db
        #: when this service runs on the live student database, or when an
        #: auth.db is named explicitly (tests).
        self.auth_db_path = auth_db_path

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
            _refuse_duplicate(conn, command)
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
            _store_details(conn, student_id, command)
            record_rules.record_changes(conn, student_id, {}, {"record": "created"},
                                        "Student created", actor_id)
            registration_extras.store(conn, student_id, command, actor_id)
            from education_system.systems.university.domains.admissions.domain.services.admissions_selection import (
                enrol_student_in_curriculum,
            )
            # The curriculum helper works on a cursor (it calls fetchall);
            # handing it the connection made every create fail.
            curriculum = enrol_student_in_curriculum(
                conn.cursor(), student_id, command.course, course["course_name"]
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
        from education_system.systems.university.domains.curriculum.domain.course_management.timetable_sync import sync_for_student_enrolment
        return (("fee", assess_module_enrolment_fee), ("library hold", place_holds_for_enrolment),
                ("timetable", sync_for_student_enrolment))

    UPDATABLE = ("title", "first_name", "middle_name", "last_name", "gender", "dob",
                 "pronouns", "emergency_contact") + record_rules.CONTACT_FIELDS

    def update(self, student_id: str, changes: Mapping[str, Any], *, actor_id: str,
               reason: str, idempotency_key: str) -> LifecycleResult:
        """Change personal and contact details, with a reason, recording each
        changed field. A course change is a transfer: :meth:`transfer_course`."""
        normalized = _clean_update(changes, reason)
        with transaction(self.db_path) as conn:
            record_rules.ensure(conn)
            student = conn.execute("SELECT * FROM students WHERE student_id=?", (student_id,)).fetchone()
            if not student:
                raise StudentValidationError({"student_id": "does not exist"})
            normalized = record_rules.settle_address(normalized, dict(student))
            cols = set(student.keys())
            normalized = {k: v for k, v in normalized.items() if k in cols}
            changed = record_rules.record_changes(conn, student_id, dict(student), normalized,
                                                  reason, actor_id)
            normalized = {k: normalized[k] for k in changed}
            if "dob" in normalized and "age" in cols:
                normalized["age"] = _age(normalized["dob"])
            if normalized:
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
        return LifecycleResult(student_id, _status_of(student["status"]), event_id, tuple(normalized))

    def transfer_course(self, student_id: str, course: str, *, actor_id: str, reason: str,
                        idempotency_key: str) -> LifecycleResult:
        """Move a student to another course. Modules of the old course they
        are still enrolled on become 'Transferred' (their marks stay); the
        new course's curriculum is added; the change is recorded."""
        if not reason.strip():
            raise StudentValidationError({"reason": "is required"})
        with transaction(self.db_path) as conn:
            record_rules.ensure(conn)
            student = conn.execute("SELECT * FROM students WHERE student_id=?", (student_id,)).fetchone()
            if not student:
                raise StudentValidationError({"student_id": "does not exist"})
            target = _transfer_target(conn, student, course)
            history = _record_transfer(conn, student, course, actor_id, reason)
            _swap_curriculum(conn, student_id, course, target["course_name"])
            conn.execute("UPDATE students SET course=? WHERE student_id=?", (course, student_id))
            conn.execute("UPDATE courses SET current_enrollment=MAX(COALESCE(current_enrollment,0)-1,0) "
                         "WHERE course_code=?", (student["course"],))
            conn.execute("UPDATE courses SET current_enrollment=COALESCE(current_enrollment,0)+1 "
                         "WHERE course_code=?", (course,))
            record_rules.record_changes(conn, student_id, {"course": student["course"]},
                                        {"course": course}, reason, actor_id)
            event_id = transactional_publisher.publish(
                conn, "student.transferred",
                {"student_id": student_id, "from": student["course"], "to": course,
                 "reason": reason, "actor_id": actor_id},
                aggregate_id=student_id, idempotency_key=idempotency_key,
            )
        if history:
            _lifecycle().publish_change(student_id, "programme_transfer", history)
        return LifecycleResult(student_id, _status_of(student["status"]), event_id, ("course",))

    def deactivate(self, student_id: str, *, actor_id: str, reason: str,
                   idempotency_key: str) -> LifecycleResult:
        """Withdraw the student (registration lifecycle where it exists) and
        switch off their sign-in."""
        return self._set_active(student_id, False, actor_id, reason, idempotency_key)

    def restore(self, student_id: str, *, actor_id: str, reason: str,
                idempotency_key: str) -> LifecycleResult:
        """Reinstate a withdrawn student and switch their sign-in back on."""
        return self._set_active(student_id, True, actor_id, reason, idempotency_key)

    def _set_active(self, student_id: str, active: bool, actor_id: str, reason: str,
                    idempotency_key: str) -> LifecycleResult:
        if not reason.strip():
            raise StudentValidationError({"reason": "is required"})
        action = "reinstate" if active else "withdraw"
        with transaction(self.db_path) as conn:
            record_rules.ensure(conn)
            old = conn.execute("SELECT status FROM students WHERE student_id=?", (student_id,)).fetchone()
            if not old:
                raise StudentValidationError({"student_id": "does not exist"})
            history, status = _apply_status(conn, student_id, action, active, actor_id, reason)
            if "is_active" in {r[1] for r in conn.execute("PRAGMA table_info(users)")}:
                conn.execute("UPDATE users SET is_active=? WHERE student_id=?", (int(active), student_id))
            record_rules.record_changes(conn, student_id, {"status": old["status"]},
                                        {"status": status}, reason, actor_id)
            library_emails = [] if active else _library_clearance(conn, student_id)
            event_id = transactional_publisher.publish(
                conn, "student.restored" if active else "student.deactivated",
                {"student_id": student_id, "reason": reason, "actor_id": actor_id},
                aggregate_id=student_id, idempotency_key=idempotency_key,
            )
        if history:
            _lifecycle().publish_change(student_id, action, history, status=status)
        elif not active:
            # No lifecycle tables, so publish_change (which tells the
            # learner's sixth form) did not run; tell it here instead.
            from education_system.systems.university.application.students import (
                sixth_form_feedback,
            )
            sixth_form_feedback.publish_withdrawn(student_id, db_path=self.db_path)
        if self.db_path is None or self.auth_db_path:
            from education_system.systems.university.services.student_provisioning import (
                set_student_login_active,
            )
            set_student_login_active(student_id, active, self.auth_db_path)
        if library_emails:
            from education_system.systems.university.application.teaching import (
                occurrences as timetable_occurrences,
            )
            timetable_occurrences.send_emails(library_emails)
        return LifecycleResult(student_id, _status_of(status), event_id)

    def impact_preview(self, student_id: str) -> dict[str, int]:
        with transaction(self.db_path) as conn:
            if conn.execute("SELECT 1 FROM students WHERE student_id=?", (student_id,)).fetchone() is None:
                raise StudentValidationError({"student_id": "does not exist"})
            result: dict[str, int] = {}
            for table, column in (("student_modules", "student_id"), ("student_grades", "student_id"),
                                  ("attendance", "student_id"), ("users", "student_id"),
                                  ("book_loans", "user_id")):
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


def _status_of(value):
    """The record's status as a StudentStatus, or the stored text for a
    legacy value (e.g. 'Graduated') - never an error after a committed
    change."""
    try:
        return StudentStatus(value)
    except ValueError:
        return value


def _age(dob: str) -> int:
    born = date.fromisoformat(dob)
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def _clean_update(changes: Mapping[str, Any], reason: str) -> dict:
    allowed = set(StudentLifecycleService.UPDATABLE)
    if "course" in changes:
        raise StudentValidationError({"course": "is changed by a transfer "
                                                "(Registration status > Change study)"})
    unknown = set(changes) - allowed
    if unknown:
        raise StudentValidationError({key: "cannot be updated" for key in unknown})
    if not reason.strip():
        raise StudentValidationError({"reason": "is required"})
    normalized = dict(changes)
    if normalized.get("gender"):
        try:
            normalized["gender"] = Gender(str(normalized["gender"]).strip().lower()).value
        except ValueError:
            raise StudentValidationError(
                {"gender": f"must be one of {', '.join(GENDER_OPTIONS)}"}) from None
    for key in ("first_name", "last_name"):
        if key in normalized:
            normalized[key] = _clean_name(normalized[key], key)
    if normalized.get("dob"):
        try:
            if not 16 <= _age(normalized["dob"]) <= 100:
                raise StudentValidationError({"dob": "student age must be between 16 and 100"})
        except ValueError as exc:
            if isinstance(exc, StudentValidationError):
                raise
            raise StudentValidationError({"dob": "must use YYYY-MM-DD"}) from None
    errors = record_rules.validate_details(normalized)
    if errors:
        raise StudentValidationError(errors)
    return record_rules.normalise_details(normalized)


def validate_update(changes: Mapping[str, Any]) -> dict:
    """The checks :meth:`StudentLifecycleService.update` applies, without
    writing (for previews). Returns the normalised changes."""
    return _clean_update(changes, "preview")


def _lifecycle():
    from education_system.systems.university.domains.learners.domain import student_lifecycle
    return student_lifecycle


def _apply_status(conn, student_id, action, active, actor_id, reason):
    """Withdraw / reinstate through the registration lifecycle (history,
    downstream actions) when its tables exist; a plain status change on a
    database without them."""
    if _lifecycle_tables(conn):
        from education_system.systems.university.services.boundary_errors import (
            EnrolmentBoundaryError,
        )
        try:
            return _lifecycle().apply_status_change(conn, student_id, action,
                                                    actor_id=actor_id, reason=reason)
        except EnrolmentBoundaryError as exc:
            raise StudentValidationError({"status": str(exc)}) from None
    status = StudentStatus.ACTIVE if active else StudentStatus.WITHDRAWN
    conn.execute("UPDATE students SET is_active=?, status=? WHERE student_id=?",
                 (int(active), status.value, student_id))
    return None, status.value


def _transfer_target(conn, student, course):
    target = conn.execute("SELECT course_code, course_name FROM courses WHERE course_code=? AND "
                          "LOWER(COALESCE(status, 'active'))='active'", (course,)).fetchone()
    if target is None:
        raise StudentValidationError({"course": "is not in the active catalogue"})
    if course == student["course"]:
        raise StudentValidationError({"course": "is already the student's course"})
    if student["status"] not in (StudentStatus.ACTIVE, StudentStatus.INTERRUPTED,
                                 StudentStatus.SUSPENDED, StudentStatus.PROVISIONING_PENDING):
        raise StudentValidationError({"status": f"cannot transfer a {student['status']} student"})
    return target


def _record_transfer(conn, student, course, actor_id, reason):
    if not _lifecycle_tables(conn):
        return None
    cols = set(student.keys())
    row = {k: (student[k] if k in cols else None) for k in
           ("student_id", "status", "course", "mode_of_study", "campus_code")}
    return _lifecycle().record_history(conn, row, action="programme_transfer",
                                       actor_id=actor_id, reason=reason, new_programme=course)


def _swap_curriculum(conn, student_id, course, course_name):
    from education_system.systems.university.domains.admissions.domain.services import (
        admissions_selection,
    )
    entries = admissions_selection.curriculum_for(conn.cursor(), course, course_name)
    new_codes = [e["module_code"] for e in entries]
    marks = ", ".join("?" for _ in new_codes) or "''"
    conn.execute(f"UPDATE student_modules SET status='Transferred' WHERE student_id=? AND "  # nosec B608
                 f"status='Enrolled' AND module_code NOT IN ({marks})", (student_id, *new_codes))
    for e in entries:
        conn.execute("INSERT OR IGNORE INTO student_modules (student_id, module_code, "
                     "module_name, module_type, year, status) VALUES (?, ?, ?, 'Core', ?, "
                     "'Enrolled')", (student_id, e["module_code"], e["module_name"],
                                     str(e["year"])))
        conn.execute("UPDATE student_modules SET status='Enrolled' WHERE student_id=? AND "
                     "module_code=? AND status='Transferred'", (student_id, e["module_code"]))


__all__ = ["Gender", "LifecycleResult", "PurgeControlError", "StudentCommand",
           "StudentLifecycleService", "StudentStatus", "StudentValidationError",
           "validate_student_command", "validate_update"]


def _library_clearance(conn, student_id):
    """Tell a student who is leaving what library items or charges are still
    outstanding (``library_services.notify_leaver``). A library problem must
    never stop the withdrawal itself, so failures are logged and skipped."""
    try:
        from education_system.systems.university.application.library import (
            services as library_services,
        )
        return library_services.notify_leaver(conn, student_id)
    except Exception:
        logger.warning("library clearance notice for %s failed", student_id, exc_info=True)
        return []
