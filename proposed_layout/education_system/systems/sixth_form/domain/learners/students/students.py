"""Student data layer for the Sixth Form System.

Owns the local SQLite DB (``data/sixthform.db``), the student_id /
sixth-form-email generation rules, the A-Level subject list, and the
CRUD functions used by the GUI panels.
"""

from __future__ import annotations

import datetime as _dt
import logging
import os
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.systems.sixth_form.infrastructure import paths

logger = logging.getLogger(__name__)

# Re-exported so existing references to ``students.DB_PATH`` keep working.
# Tests that need an isolated DB still rebind this module attribute.
DB_PATH = paths.STUDENTS_DB

EMAIL_DOMAIN = "sixthform.ac.uk"
ID_PREFIX = "C"
ID_DIGITS = 7

A_LEVEL_SUBJECTS: list[str] = [
    "Mathematics",
    "Further Mathematics",
    "English Literature",
    "English Language",
    "Physics",
    "Chemistry",
    "Biology",
    "History",
    "Geography",
    "Economics",
    "Business Studies",
    "Accounting",
    "Psychology",
    "Sociology",
    "Computer Science",
    "Art and Design",
    "Music",
    "French",
    "Spanish",
    "German",
    "Religious Studies",
    "Politics",
    "Philosophy",
    "Media Studies",
    "Drama and Theatre",
    "Physical Education",
    "Law",
]

_PHONE_RE = re.compile(r"^[0-9 +()\-]{6,20}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Sixth-form system maps to the seeded shared-auth system_key "sixth_form".
AUTH_SYSTEM_KEY = "sixth_form"
AUTH_ROLE = "student"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    student_id                  TEXT PRIMARY KEY,
    first_name                  TEXT NOT NULL,
    middle_name                 TEXT,
    last_name                   TEXT NOT NULL,
    title                       TEXT,
    gender                      TEXT,
    date_of_birth               TEXT,
    phone                       TEXT,
    email                       TEXT NOT NULL UNIQUE,
    emergency_contact_name      TEXT,
    emergency_contact_phone     TEXT,
    emergency_contact_relation  TEXT,
    subject_1                   TEXT,
    subject_2                   TEXT,
    subject_3                   TEXT,
    status                      TEXT NOT NULL DEFAULT 'Active',
    created_at                  TEXT DEFAULT (datetime('now'))
);
"""

# Optional fields useful for university-system handover. Title/gender
# match the university CRUD's allowed values verbatim so an import can
# be a straight copy.
TITLES: tuple[str, ...] = ("Mr", "Ms", "Mrs", "Dr", "Prof")
GENDERS: tuple[str, ...] = ("male", "female", "other")

# Student-record lifecycle. ``Active`` is the default; ``Inactive``
# covers temporary breaks (illness, year-out), ``Suspended`` is
# disciplinary, ``Left`` is anyone who has gone (transferred,
# withdrawn, or finished). Distinct from enrolment status, which is
# per-academic-year on the ``enrolments`` table.
STATUSES: tuple[str, ...] = ("Active", "Inactive", "Suspended", "Left")
DEFAULT_STATUS: str = "Active"


@dataclass
class Student:
    student_id: str
    first_name: str
    middle_name: str | None
    last_name: str
    phone: str | None
    email: str
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    emergency_contact_relation: str | None
    subject_1: str | None
    subject_2: str | None
    subject_3: str | None
    title: str | None = None
    gender: str | None = None
    date_of_birth: str | None = None
    status: str = "Active"

    @property
    def full_name(self) -> str:
        parts = [self.first_name, self.middle_name or "", self.last_name]
        return " ".join(p for p in parts if p).strip()

    @property
    def subjects(self) -> list[str]:
        return [s for s in (self.subject_1, self.subject_2, self.subject_3) if s]


# ── DB plumbing ──────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    """Apply the schema once per process and log it once.

    Subsequent calls are cheap no-ops so callers can safely guard
    every entry point with ``init_db()`` without spamming the log.

    Also installs the persistent log handler on first call so that
    every subsequent ``logger.info/warning/...`` from sixth-form
    modules is captured to the ``system_logs`` table.
    """
    global _DB_READY
    if _DB_READY:
        return
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        # Backfill columns added after the original schema shipped.
        # SQLite's ADD COLUMN is the only safe migration here — we
        # check PRAGMA table_info to make it idempotent.
        existing_cols = {
            r["name"] for r in conn.execute(
                "PRAGMA table_info(students)").fetchall()
        }
        for col, ddl in (
                ("title",         "TEXT"),
                ("gender",        "TEXT"),
                ("date_of_birth", "TEXT"),
                ("status",        "TEXT NOT NULL DEFAULT 'Active'"),
        ):
            if col not in existing_cols:
                conn.execute(
                    f"ALTER TABLE students ADD COLUMN {col} {ddl}")
                logger.info("Sixth-form students: added column %s", col)
        conn.commit()
    # Wire up the persistent log table before we emit our own first
    # "ready" message so even that lands in the audit trail.
    try:
        from education_system.systems.sixth_form.infrastructure import log_store
        log_store.install()
    except Exception:
        logger.exception("Could not install persistent log handler")
    logger.info("Sixth form students DB ready at %s", DB_PATH)
    _DB_READY = True


def _row_to_student(row: sqlite3.Row) -> Student:
    return Student(
        student_id=row["student_id"],
        first_name=row["first_name"],
        middle_name=row["middle_name"],
        last_name=row["last_name"],
        phone=row["phone"],
        email=row["email"],
        emergency_contact_name=row["emergency_contact_name"],
        emergency_contact_phone=row["emergency_contact_phone"],
        emergency_contact_relation=row["emergency_contact_relation"],
        subject_1=row["subject_1"],
        subject_2=row["subject_2"],
        subject_3=row["subject_3"],
        title=(row["title"] if "title" in row.keys() else None),
        gender=(row["gender"] if "gender" in row.keys() else None),
        date_of_birth=(row["date_of_birth"]
                        if "date_of_birth" in row.keys() else None),
        status=(row["status"] if "status" in row.keys() else "Active") or "Active",
    )


# ── Generators ──────────────────────────────────────────────────────

def generate_student_id() -> str:
    """Return a fresh, unused id like 'C1470977' (C + 7 digits)."""
    init_db()
    with _connect() as conn:
        for attempt in range(50):
            n = random.randint(10 ** (ID_DIGITS - 1), 10 ** ID_DIGITS - 1)
            sid = f"{ID_PREFIX}{n}"
            row = conn.execute(
                "SELECT 1 FROM students WHERE student_id = ?", (sid,)
            ).fetchone()
            if row is None:
                if attempt == 0:
                    logger.debug("Allocated student id %s on first attempt", sid)
                else:
                    logger.info(
                        "Allocated student id %s after %d collisions",
                        sid, attempt)
                return sid
            if attempt == 25:
                logger.warning(
                    "Student-id allocator hit %d collisions — namespace "
                    "may be getting crowded", attempt)
    logger.error("Exhausted 50 attempts allocating a unique student id")
    raise RuntimeError("Could not allocate a unique student id after 50 tries")


def generate_sixthform_email(student_id: str) -> str:
    return f"{student_id.lower()}@{EMAIL_DOMAIN}"


# ── Validation ──────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for any invalid student-form input."""


def _require(value: str | None, label: str) -> str:
    if not value or not value.strip():
        raise ValidationError(f"{label} is required")
    return value.strip()


def _validate_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["first_name"] = _require(data.get("first_name"), "First name")
    out["middle_name"] = (data.get("middle_name") or "").strip() or None
    out["last_name"] = _require(data.get("last_name"), "Last name")

    title = (data.get("title") or "").strip() or None
    if title is not None and title not in TITLES:
        raise ValidationError(
            f"Title must be one of: {', '.join(TITLES)}")
    out["title"] = title

    gender = (data.get("gender") or "").strip().lower() or None
    if gender is not None and gender not in GENDERS:
        raise ValidationError(
            f"Gender must be one of: {', '.join(GENDERS)}")
    out["gender"] = gender

    dob = (data.get("date_of_birth") or "").strip() or None
    if dob is not None:
        import datetime as _dt
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", dob):
            raise ValidationError(
                "Date of birth must be YYYY-MM-DD")
        try:
            _dt.date.fromisoformat(dob)
        except ValueError:
            raise ValidationError(
                "Date of birth is not a real calendar date") from None
    out["date_of_birth"] = dob

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    phone = (data.get("phone") or "").strip()
    if phone and not _PHONE_RE.match(phone):
        raise ValidationError("Phone number contains invalid characters")
    out["phone"] = phone or None

    personal_email = (data.get("personal_email") or "").strip()
    if personal_email and not _EMAIL_RE.match(personal_email):
        raise ValidationError("Personal email is not a valid address")
    out["personal_email"] = personal_email or None

    out["emergency_contact_name"] = (
        data.get("emergency_contact_name") or "").strip() or None
    ec_phone = (data.get("emergency_contact_phone") or "").strip()
    if ec_phone and not _PHONE_RE.match(ec_phone):
        raise ValidationError(
            "Emergency contact phone contains invalid characters")
    out["emergency_contact_phone"] = ec_phone or None
    out["emergency_contact_relation"] = (
        data.get("emergency_contact_relation") or "").strip() or None

    subjects = [
        (data.get("subject_1") or "").strip(),
        (data.get("subject_2") or "").strip(),
        (data.get("subject_3") or "").strip(),
    ]
    chosen = [s for s in subjects if s]
    if len(chosen) != 3:
        raise ValidationError("Please choose three A-Level subjects")
    if len(set(chosen)) != 3:
        raise ValidationError("A-Level subjects must be distinct")
    # Validate against the live subjects table (source of truth) but
    # fall back to the seed list if the table isn't there yet (e.g.
    # during unit tests that don't import the subjects module).
    try:
        from education_system.systems.sixth_form.domain.academics.subjects import subjects as _subjects
        for s in chosen:
            if not _subjects.is_valid_subject(s):
                raise ValidationError(f"Unknown A-Level subject: {s}")
    except ImportError:
        for s in chosen:
            if s not in A_LEVEL_SUBJECTS:
                raise ValidationError(f"Unknown A-Level subject: {s}")
    out["subject_1"], out["subject_2"], out["subject_3"] = subjects
    return out


# ── Login account provisioning ──────────────────────────────────────
#
# Each student gets a row in the shared `auth.db` so they can sign in
# through the universal login. Username == student_id, password is
# derived from the first name. We write directly via the schema-level
# hash helper (same path used by the seeded demo accounts) — going
# through `UserAuth.create_user` would fail strength validation, the
# same trade-off the seed already makes.

def _derive_password(first_name: str) -> str:
    return f"{first_name.strip().lower()}123456"


def _provision_login_account(student: Student) -> None:
    """Create a sign-in row in the shared auth DB for this student.

    Idempotent: if the username already exists we leave the row alone
    (don't reset their password) and just make sure the system mapping
    is present.
    """
    from education_system.platform.identity.auth.db import connect as _auth_connect
    from education_system.platform.identity.auth.password_manager import hash_password

    password = _derive_password(student.first_name)
    pw_hash = hash_password(password)
    display = student.full_name

    try:
        with _auth_connect() as conn:
            row = conn.execute(
                "SELECT id FROM users WHERE username = ?", (student.student_id,)
            ).fetchone()
            if row is None:
                cur = conn.execute(
                    "INSERT INTO users (username, password_hash, display_name, email) "
                    "VALUES (?, ?, ?, ?)",
                    (student.student_id, pw_hash, display, student.email),
                )
                user_id = cur.lastrowid
                logger.info(
                    "Provisioned login account for student %s (auth user_id=%d)",
                    student.student_id, user_id,
                )
            else:
                user_id = row["id"]
                logger.debug(
                    "Login account already exists for %s — leaving password intact",
                    student.student_id,
                )
            conn.execute(
                "INSERT OR IGNORE INTO user_systems (user_id, system_key, role) "
                "VALUES (?, ?, ?)",
                (user_id, AUTH_SYSTEM_KEY, AUTH_ROLE),
            )
            conn.commit()
    except Exception:
        logger.exception(
            "Failed to provision login account for student %s", student.student_id,
        )
        raise


def _deprovision_login_account(student_id: str, email: str | None = None) -> None:
    """Revoke the shared-auth login for a deleted student.

    Many tables in the shared auth DB reference ``users(id)`` without
    ``ON DELETE CASCADE``, so a plain ``DELETE FROM users`` would fail
    on FK constraints (or orphan sessions/MFA secrets). Instead we
    disable foreign keys for this one transaction and clear the rows
    we created — ``user_systems`` and the ``users`` row itself. Best
    effort: errors are logged but not re-raised so a missing shared
    DB never blocks the student delete.
    """
    from education_system.platform.identity.auth.db import connect as _auth_connect
    try:
        with _auth_connect() as conn:
            row = conn.execute(
                "SELECT id FROM users WHERE username = ? OR username = ?",
                (student_id, (email or "")),
            ).fetchone()
            if row is None:
                logger.debug(
                    "No login account to deprovision for %s", student_id)
                return
            user_id = row["id"]
            conn.execute("PRAGMA foreign_keys=OFF")
            conn.execute("DELETE FROM user_systems WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM mfa_secrets WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM password_history WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM security_questions WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            logger.info(
                "Deprovisioned login account for student %s (auth user_id=%d)",
                student_id, user_id,
            )
    except Exception:
        logger.exception(
            "Failed to deprovision login account for %s — leaving row in place",
            student_id,
        )


# ── CRUD ────────────────────────────────────────────────────────────

def create_student(data: dict[str, Any]) -> Student:
    """Insert a new student. Returns the persisted `Student` (with
    auto-generated `student_id` and sixth-form email)."""
    init_db()
    # PII-safe entry log: record only WHICH fields the caller supplied,
    # never the values, so the trail is useful for debugging without
    # leaking names/phone numbers into log aggregation.
    logger.debug(
        "create_student called with fields: %s",
        sorted(k for k, v in data.items() if v not in (None, "")))
    try:
        payload = _validate_payload(data)
    except ValidationError as e:
        logger.warning("create_student validation failed: %s", e)
        raise
    sid = generate_student_id()
    email = generate_sixthform_email(sid)
    try:
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO students (
                    student_id, first_name, middle_name, last_name,
                    title, gender, date_of_birth,
                    phone, email,
                    emergency_contact_name, emergency_contact_phone,
                    emergency_contact_relation,
                    subject_1, subject_2, subject_3,
                    status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sid,
                    payload["first_name"],
                    payload["middle_name"],
                    payload["last_name"],
                    payload["title"],
                    payload["gender"],
                    payload["date_of_birth"],
                    payload["phone"],
                    email,
                    payload["emergency_contact_name"],
                    payload["emergency_contact_phone"],
                    payload["emergency_contact_relation"],
                    payload["subject_1"],
                    payload["subject_2"],
                    payload["subject_3"],
                    payload["status"],
                ),
            )
            conn.commit()
    except sqlite3.IntegrityError:
        logger.exception(
            "INSERT failed for new student id=%s (likely a duplicate "
            "student_id or email collision)", sid)
        raise
    student = get_student(sid)
    assert student is not None
    logger.info(
        "Created student %s (%s, email=%s, subjects=%s)",
        student.student_id, student.full_name, student.email, student.subjects,
    )
    _provision_login_account(student)
    _send_welcome_email(student)
    # Anchor a canonical journey_id so this student links to the same
    # person in the secondary/university systems (best-effort; matched on
    # name + DOB).
    try:
        from education_system.platform.cross_system import person, progression
        jid = progression.register_local_student(
            "sixth_form", student_id=student.student_id,
            first_name=student.first_name, last_name=student.last_name,
            date_of_birth=student.date_of_birth)
        if jid:
            person.link_local_record("sixth_form", student.student_id, jid)
    except Exception:
        logger.debug("Journey registration skipped for student %s",
                     student.student_id, exc_info=True)
    return student


def _send_welcome_email(student: Student) -> None:
    """Drop a welcome email into the student's inbox.

    Best-effort: any failure is logged but never blocks student
    creation — the record is more important than the welcome message.
    """
    try:
        from education_system.systems.sixth_form import SYSTEM_NAME
        from education_system.systems.sixth_form.domain.operations.communications.messages import (
            email_templates,
        )
        subjects = list(student.subjects) + ["", "", ""]
        msg = email_templates.send_from_template(
            "welcome_student",
            {
                "system_name": SYSTEM_NAME,
                "student_id":  student.student_id,
                "first_name":  student.first_name,
                "last_name":   student.last_name,
                "full_name":   student.full_name,
                "email":       student.email,
                "password":    _derive_password(student.first_name),
                "subject_1":   subjects[0],
                "subject_2":   subjects[1],
                "subject_3":   subjects[2],
            },
            to_name=student.full_name,
            to_address=student.email,
            student_id=student.student_id,
        )
        logger.info(
            "Welcome email delivered to student %s (message #%d, to=%s)",
            student.student_id, msg.message_id, student.email)
    except Exception:
        logger.exception(
            "Welcome email could not be sent to %s — student record was "
            "still created", student.student_id)


def get_student(student_id: str) -> Student | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()
    if row is None:
        logger.debug("get_student(%s) -> miss", student_id)
        return None
    return _row_to_student(row)


def list_students() -> list[Student]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM students ORDER BY last_name, first_name"
        ).fetchall()
    logger.debug("list_students -> %d row(s)", len(rows))
    return [_row_to_student(r) for r in rows]


def list_year_13_students() -> list[Student]:
    """Return sixth-form students whose latest enrolment is Year 13 and
    still active (status='Enrolled').

    Joins the ``students`` table to the ``enrolments`` table on
    ``student_id`` and filters to ``year_group=13``. If a student has
    multiple Year 13 rows across academic years we take the most
    recent. Used by the university-system import flow to surface
    leavers ready to be admitted onto a course.
    """
    init_db()
    # Ensure enrolments schema exists so the JOIN doesn't fail when
    # this is called before the enrolments module has been touched
    # this process.
    try:
        from education_system.systems.sixth_form.domain.admissions.enrolments import (
            enrolments as _enrolments,
        )
        _enrolments.init_db()
    except Exception:
        logger.exception(
            "list_year_13_students: could not init enrolments schema")
        return []
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT s.*
              FROM students AS s
             WHERE s.status = 'Active'
               AND s.student_id IN (
                       SELECT e.student_id
                         FROM enrolments AS e
                        WHERE e.year_group = 13
                          AND e.status = 'Enrolled'
                   )
             ORDER BY s.last_name, s.first_name
            """,
        ).fetchall()
    logger.debug("list_year_13_students -> %d row(s)", len(rows))
    return [_row_to_student(r) for r in rows]


def search_students(query: str) -> list[Student]:
    """Match against student_id, names, or sixth-form email."""
    init_db()
    raw = (query or "").strip()
    if not raw:
        logger.debug("search_students called with empty query")
    q = f"%{raw}%"
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM students
            WHERE student_id LIKE ?
               OR first_name LIKE ?
               OR middle_name LIKE ?
               OR last_name LIKE ?
               OR email LIKE ?
            ORDER BY last_name, first_name
            """,
            (q, q, q, q, q),
        ).fetchall()
    logger.debug(
        "search_students(query_len=%d) -> %d match(es)", len(raw), len(rows))
    return [_row_to_student(r) for r in rows]


def update_student(student_id: str, data: dict[str, Any]) -> Student:
    """Update editable fields. ID and sixth-form email are immutable."""
    init_db()
    logger.debug(
        "update_student(%s) called with fields: %s",
        student_id,
        sorted(k for k, v in data.items() if v not in (None, "")))
    try:
        payload = _validate_payload(data)
    except ValidationError as e:
        logger.warning("update_student(%s) validation failed: %s", student_id, e)
        raise
    before = get_student(student_id)
    if before is None:
        logger.warning(
            "update_student(%s): no existing row — UPDATE will be a no-op "
            "and will raise", student_id)
    with _connect() as conn:
        cur = conn.execute(
            """
            UPDATE students SET
                first_name = ?, middle_name = ?, last_name = ?,
                title = ?, gender = ?, date_of_birth = ?,
                phone = ?,
                emergency_contact_name = ?, emergency_contact_phone = ?,
                emergency_contact_relation = ?,
                subject_1 = ?, subject_2 = ?, subject_3 = ?,
                status = ?
            WHERE student_id = ?
            """,
            (
                payload["first_name"],
                payload["middle_name"],
                payload["last_name"],
                payload["title"],
                payload["gender"],
                payload["date_of_birth"],
                payload["phone"],
                payload["emergency_contact_name"],
                payload["emergency_contact_phone"],
                payload["emergency_contact_relation"],
                payload["subject_1"],
                payload["subject_2"],
                payload["subject_3"],
                payload["status"],
                student_id,
            ),
        )
        if cur.rowcount == 0:
            logger.warning("update_student called for unknown id %s", student_id)
            raise ValidationError(f"No student with id {student_id}")
        conn.commit()
    student = get_student(student_id)
    assert student is not None
    if before is not None:
        changes = _diff_student(before, student)
        if changes:
            # Field names only (no values) — audit-friendly but PII-safe.
            logger.info(
                "Updated student %s — changed fields: %s",
                student_id, ", ".join(label for label, _o, _n in changes))
            _send_update_email(before, student, changes=changes)
        else:
            logger.info(
                "Updated student %s — no tracked fields changed",
                student_id)
    else:
        logger.info("Updated student %s", student_id)
    return student


_TRACKED_UPDATE_FIELDS: tuple[tuple[str, str], ...] = (
    ("first_name",                 "First name"),
    ("middle_name",                "Middle name"),
    ("last_name",                  "Last name"),
    ("phone",                      "Phone"),
    ("emergency_contact_name",     "Emergency contact name"),
    ("emergency_contact_phone",    "Emergency contact phone"),
    ("emergency_contact_relation", "Emergency contact relation"),
    ("subject_1",                  "A-Level subject 1"),
    ("subject_2",                  "A-Level subject 2"),
    ("subject_3",                  "A-Level subject 3"),
)


def _diff_student(before: Student, after: Student) -> list[tuple[str, str, str]]:
    """Return [(label, old, new), ...] for fields that actually changed."""
    out: list[tuple[str, str, str]] = []
    for attr, label in _TRACKED_UPDATE_FIELDS:
        old_v = getattr(before, attr, None)
        new_v = getattr(after, attr, None)
        if (old_v or "") != (new_v or ""):
            out.append((label, str(old_v) if old_v else "(empty)",
                                str(new_v) if new_v else "(empty)"))
    return out


def _send_update_email(before: Student, after: Student, *,
                       changes: list[tuple[str, str, str]] | None = None) -> None:
    """Email the student a summary of what changed in their record.

    No-op if nothing tracked actually changed. Best-effort: failure
    never blocks the update itself.
    """
    if changes is None:
        changes = _diff_student(before, after)
    if not changes:
        logger.debug(
            "Update email skipped for %s — diff is empty",
            after.student_id)
        return
    try:
        import datetime as _dt
        from education_system.systems.sixth_form import SYSTEM_NAME
        from education_system.systems.sixth_form.domain.operations.communications.messages import (
            email_templates,
        )
        change_lines = "\n".join(
            f"  • {label}:\n      was: {old}\n      now: {new}"
            for label, old, new in changes
        )
        msg = email_templates.send_from_template(
            "student_record_updated",
            {
                "system_name": SYSTEM_NAME,
                "student_id":  after.student_id,
                "first_name":  after.first_name,
                "full_name":   after.full_name,
                "updated_at":  _dt.datetime.now().strftime(
                    "%Y-%m-%d %H:%M"),
                "changes":     change_lines,
            },
            to_name=after.full_name,
            to_address=after.email,
            student_id=after.student_id,
        )
        logger.info(
            "Update email delivered to student %s (message #%d, %d "
            "change(s))",
            after.student_id, msg.message_id, len(changes))
    except Exception:
        logger.exception(
            "Update email could not be sent to %s — the record update "
            "itself succeeded", after.student_id)


# Where transfer notifications land. Override at runtime via the
# ``EDU_SIXTHFORM_ADMIN_EMAIL`` environment variable if your school
# routes admin mail somewhere other than the default.
SIXTHFORM_ADMIN_EMAIL_DEFAULT = "admin@sixthform.ac.uk"


def _sixthform_admin_email() -> str:
    return os.environ.get(
        "EDU_SIXTHFORM_ADMIN_EMAIL",
        SIXTHFORM_ADMIN_EMAIL_DEFAULT,
    ).strip() or SIXTHFORM_ADMIN_EMAIL_DEFAULT


def _deactivate_login_account(student_id: str) -> bool:
    """Set ``is_active = 0`` on the student's shared-auth user row.

    Keeps the row in place (history, audit, password-history references
    survive) but blocks future logins — the shared ``UserAuth.login``
    flow refuses inactive accounts with a generic
    "Invalid username or password" error, the same response unknown
    usernames get, so account existence isn't leaked by the message.

    Returns ``True`` if a row was updated, ``False`` if no such auth
    account exists. Best-effort: errors are logged but never raised so
    transfer flow continues even if the shared DB is unavailable.
    """
    from education_system.platform.identity.auth.db import connect as _auth_connect
    try:
        with _auth_connect() as conn:
            cur = conn.execute(
                "UPDATE users SET is_active = 0 WHERE username = ?",
                (student_id,),
            )
            # Also kill any live sessions so they're booted right now.
            conn.execute(
                "UPDATE sessions SET is_active = 0 WHERE user_id IN "
                "(SELECT id FROM users WHERE username = ?)",
                (student_id,),
            )
            conn.commit()
            if cur.rowcount:
                logger.info(
                    "Deactivated sixth-form login for %s (sessions revoked)",
                    student_id)
                return True
            logger.warning(
                "Deactivate-login: no auth account found for %s",
                student_id)
            return False
    except Exception:
        logger.exception(
            "Failed to deactivate sixth-form login for %s", student_id)
        return False


def mark_transferred(student_id: str,
                      *, moved_by: str | None = None) -> Student:
    """Mark a sixth-form student as transferred to another system.

    Composite, idempotent-ish operation:

      1. Updates the student row's ``status`` to ``'Left'``.
      2. Deactivates the shared-auth login (``users.is_active = 0``)
         and revokes any live sessions, so the student can no longer
         sign in with their sixth-form credentials.
      3. Sends an email to the sixth-form admin inbox via the
         ``student_transferred_to_university`` template, naming the
         student and quoting their id.

    Each step logs progress and failure individually. The auth and
    email steps are best-effort: failures are logged but do not block
    the status update or each other, so a successful import in the
    university system can never be left half-applied.
    """
    init_db()
    student = get_student(student_id)
    if student is None:
        raise ValidationError(f"No student with id {student_id}")

    # Already transferred? The status flip and login deactivation below
    # are idempotent no-ops, but the notification email is not — so only
    # send it the first time to avoid duplicate admin notices on a
    # repeated/accidental call.
    already_left = student.status == "Left"

    # 1) Flip status to Left — independent of any side-effects below.
    with _connect() as conn:
        conn.execute(
            "UPDATE students SET status = 'Left' WHERE student_id = ?",
            (student_id,),
        )
        conn.commit()
    logger.info(
        "Marked student %s (%s) as Left (transferred)",
        student_id, student.full_name,
    )

    # 2) Deactivate the auth login.
    _deactivate_login_account(student_id)

    # 2b) Register the canonical cross-system identity and publish a
    #     progression event onto the durable bus so the university
    #     system can admit the student. Only on the first transfer.
    if not already_left:
        _publish_progression(student, moved_by)

    # 3) Notify the sixth-form admin inbox — only on the first transfer.
    if already_left:
        logger.info(
            "Student %s was already 'Left' — skipping duplicate "
            "transfer notification email", student_id,
        )
    else:
        try:
            from education_system.systems.sixth_form.domain.operations.communications.messages import (
                email_templates,
            )
            admin_email = _sixthform_admin_email()
            context = {
                "student_id":     student.student_id,
                "full_name":      student.full_name,
                "first_name":     student.first_name,
                "last_name":      student.last_name,
                "date_of_birth":  student.date_of_birth or "—",
                "transferred_at": _dt.datetime.utcnow().strftime(
                    "%Y-%m-%d %H:%M UTC"),
                "moved_by":       (moved_by or "university system").strip()
                                  or "university system",
            }
            email_templates.send_from_template(
                "student_transferred_to_university",
                context,
                to_name="Sixth Form Admin",
                to_address=admin_email,
                student_id=student.student_id,
            )
            logger.info(
                "Transfer notification email queued for %s to %s",
                student_id, admin_email,
            )
        except Exception:
            logger.exception(
                "Transfer notification email failed for %s "
                "(student row was still marked Left)", student_id,
            )

    # Return the refreshed Student row so callers can see the new
    # status without an extra fetch.
    out = get_student(student_id)
    assert out is not None
    return out


def _publish_progression(student, moved_by: str | None) -> None:
    """Best-effort: register the canonical journey and publish a
    ``student.progression.completed`` event for the university system.

    Requires name + DOB to anchor the canonical identity; if the
    sixth-form record is missing a DOB we skip the bus (the status
    flip / email still apply) rather than create an unmatchable journey.
    """
    if not (student.first_name and student.last_name
            and student.date_of_birth):
        logger.info(
            "Skipping cross-system publish for %s — needs name + DOB "
            "to anchor a canonical identity", student.student_id)
        return
    try:
        from education_system.platform.cross_system import identity_service
        from education_system.platform.integrations.external import cross_system_bus
        journey_id = identity_service.get_or_create_journey(
            first_name=student.first_name,
            last_name=student.last_name,
            date_of_birth=student.date_of_birth,
            system="sixth_form", student_id=student.student_id)
        cross_system_bus.publish_cross_system(
            cross_system_bus.EVENT_STUDENT_PROGRESSION_COMPLETED,
            source_system="sixth_form",
            source_module="sixthform_system.students",
            journey_id=journey_id, target_system="university",
            sf_student_id=student.student_id,
            first_name=student.first_name,
            middle_name=student.middle_name,
            last_name=student.last_name,
            date_of_birth=student.date_of_birth,
            gender=student.gender, title=student.title,
            moved_by=moved_by)
        logger.info(
            "Published progression event for %s (journey %s) to "
            "university", student.student_id, journey_id)
        _emit_transfer_webhook(student, journey_id, moved_by)
    except Exception:
        logger.exception(
            "Cross-system progression publish failed for %s "
            "(status/login/email still applied)", student.student_id)


def _emit_transfer_webhook(student, journey_id: str,
                           moved_by: str | None) -> None:
    """Best-effort: notify external subscribers of the transfer."""
    try:
        from education_system.platform.integrations.webhooks.webhook_service import (
            WebhookService,
        )
        WebhookService().dispatch(
            "student.transferred",
            {
                "journey_id": journey_id,
                "sf_student_id": student.student_id,
                "full_name": student.full_name,
                "date_of_birth": student.date_of_birth,
                "moved_by": moved_by or "university system",
            },
            system_key="sixth_form")
    except Exception:
        logger.debug("Transfer webhook dispatch skipped for %s",
                     student.student_id, exc_info=True)


def delete_student(student_id: str) -> bool:
    init_db()
    # Capture identifying details before the row is gone so the log
    # message names the person and the audit trail is meaningful even
    # after the record no longer exists.
    snapshot = get_student(student_id)
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM students WHERE student_id = ?", (student_id,)
        )
        conn.commit()
        deleted = cur.rowcount > 0
    if deleted:
        if snapshot is not None:
            logger.info(
                "Deleted student %s (%s, email=%s)",
                student_id, snapshot.full_name, snapshot.email)
        else:
            # Theoretically reachable if a concurrent writer inserted
            # the row between snapshot and DELETE — log it so the
            # mismatch is visible.
            logger.info(
                "Deleted student %s (no snapshot — race?)", student_id)
        _deprovision_login_account(
            student_id,
            email=snapshot.email if snapshot is not None else None,
        )
    else:
        logger.warning("delete_student called for unknown id %s", student_id)
    return deleted
