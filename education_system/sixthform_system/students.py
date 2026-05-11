"""Student data layer for the Sixth Form System.

Owns the local SQLite DB (``data/sixthform.db``), the student_id /
sixth-form-email generation rules, the A-Level subject list, and the
CRUD functions used by the GUI panels.
"""

from __future__ import annotations

import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.sixthform_system import paths

logger = logging.getLogger(__name__)

# Re-exported so existing references to ``students.DB_PATH`` keep working.
# Tests that need an isolated DB still rebind this module attribute.
DB_PATH = paths.STUDENTS_DB

EMAIL_DOMAIN = "sixthorm.ac.uk"
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

# Sixth-form system maps to the seeded shared-auth system_key "college".
AUTH_SYSTEM_KEY = "college"
AUTH_ROLE = "student"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    student_id                  TEXT PRIMARY KEY,
    first_name                  TEXT NOT NULL,
    middle_name                 TEXT,
    last_name                   TEXT NOT NULL,
    phone                       TEXT,
    email                       TEXT NOT NULL UNIQUE,
    emergency_contact_name      TEXT,
    emergency_contact_phone     TEXT,
    emergency_contact_relation  TEXT,
    subject_1                   TEXT,
    subject_2                   TEXT,
    subject_3                   TEXT,
    created_at                  TEXT DEFAULT (datetime('now'))
);
"""


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


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Sixth form students DB ready at %s", DB_PATH)


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
                logger.debug("Allocated student id %s on attempt %d", sid, attempt + 1)
                return sid
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
    from education_system.shared.auth.db import connect as _auth_connect
    from education_system.shared.auth.password_manager import hash_password

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


def _deprovision_login_account(student_id: str) -> None:
    """Revoke the shared-auth login for a deleted student.

    Many tables in the shared auth DB reference ``users(id)`` without
    ``ON DELETE CASCADE``, so a plain ``DELETE FROM users`` would fail
    on FK constraints (or orphan sessions/MFA secrets). Instead we
    disable foreign keys for this one transaction and clear the rows
    we created — ``user_systems`` and the ``users`` row itself. Best
    effort: errors are logged but not re-raised so a missing shared
    DB never blocks the student delete.
    """
    from education_system.shared.auth.db import connect as _auth_connect
    try:
        with _auth_connect() as conn:
            row = conn.execute(
                "SELECT id FROM users WHERE username = ?", (student_id,)
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
    try:
        payload = _validate_payload(data)
    except ValidationError as e:
        logger.warning("create_student validation failed: %s", e)
        raise
    sid = generate_student_id()
    email = generate_sixthform_email(sid)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO students (
                student_id, first_name, middle_name, last_name,
                phone, email,
                emergency_contact_name, emergency_contact_phone,
                emergency_contact_relation,
                subject_1, subject_2, subject_3
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sid,
                payload["first_name"],
                payload["middle_name"],
                payload["last_name"],
                payload["phone"],
                email,
                payload["emergency_contact_name"],
                payload["emergency_contact_phone"],
                payload["emergency_contact_relation"],
                payload["subject_1"],
                payload["subject_2"],
                payload["subject_3"],
            ),
        )
        conn.commit()
    student = get_student(sid)
    assert student is not None
    logger.info(
        "Created student %s (%s, email=%s, subjects=%s)",
        student.student_id, student.full_name, student.email, student.subjects,
    )
    _provision_login_account(student)
    return student


def get_student(student_id: str) -> Student | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()
        return _row_to_student(row) if row else None


def list_students() -> list[Student]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM students ORDER BY last_name, first_name"
        ).fetchall()
        return [_row_to_student(r) for r in rows]


def search_students(query: str) -> list[Student]:
    """Match against student_id, names, or sixth-form email."""
    init_db()
    q = f"%{query.strip()}%"
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
        return [_row_to_student(r) for r in rows]


def update_student(student_id: str, data: dict[str, Any]) -> Student:
    """Update editable fields. ID and sixth-form email are immutable."""
    init_db()
    try:
        payload = _validate_payload(data)
    except ValidationError as e:
        logger.warning("update_student(%s) validation failed: %s", student_id, e)
        raise
    with _connect() as conn:
        cur = conn.execute(
            """
            UPDATE students SET
                first_name = ?, middle_name = ?, last_name = ?,
                phone = ?,
                emergency_contact_name = ?, emergency_contact_phone = ?,
                emergency_contact_relation = ?,
                subject_1 = ?, subject_2 = ?, subject_3 = ?
            WHERE student_id = ?
            """,
            (
                payload["first_name"],
                payload["middle_name"],
                payload["last_name"],
                payload["phone"],
                payload["emergency_contact_name"],
                payload["emergency_contact_phone"],
                payload["emergency_contact_relation"],
                payload["subject_1"],
                payload["subject_2"],
                payload["subject_3"],
                student_id,
            ),
        )
        if cur.rowcount == 0:
            logger.warning("update_student called for unknown id %s", student_id)
            raise ValidationError(f"No student with id {student_id}")
        conn.commit()
    student = get_student(student_id)
    assert student is not None
    logger.info("Updated student %s", student_id)
    return student


def delete_student(student_id: str) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM students WHERE student_id = ?", (student_id,)
        )
        conn.commit()
        deleted = cur.rowcount > 0
    if deleted:
        logger.info("Deleted student %s", student_id)
        _deprovision_login_account(student_id)
    else:
        logger.warning("delete_student called for unknown id %s", student_id)
    return deleted
