"""Parent / Guardian Contacts data layer for the Sixth Form System.

A student may have multiple contacts. At most one contact per student
can be flagged ``is_primary`` (the one we call first / address letters
to). ``is_emergency_contact`` and ``receives_communications`` can be
toggled independently — emergency contacts aren't always the primary,
and not everyone with parental responsibility wants school emails.

Cascade: deleting a student wipes their contacts.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.sixthform_system.core import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.PARENT_CONTACTS_DB

RELATIONSHIPS: tuple[str, ...] = (
    "Mother", "Father", "Parent", "Step-mother", "Step-father",
    "Guardian", "Carer", "Foster Carer", "Grandmother",
    "Grandfather", "Aunt", "Uncle", "Sibling", "Social Worker",
    "Other",
)
DEFAULT_RELATIONSHIP: str = "Parent"

PREFERRED_CONTACT_METHODS: tuple[str, ...] = (
    "Email", "Phone (primary)", "Phone (secondary)", "SMS", "Post",
)
DEFAULT_PREFERRED_METHOD: str = "Email"

LANGUAGES: tuple[str, ...] = (
    "English", "Polish", "Urdu", "Punjabi", "Bengali", "Arabic",
    "Spanish", "French", "Portuguese", "Romanian", "Turkish",
    "Mandarin", "Cantonese", "Other",
)
DEFAULT_LANGUAGE: str = "English"

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^[+0-9 ()\-]{5,25}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS parent_contacts (
    contact_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id        TEXT NOT NULL,
    relationship      TEXT NOT NULL DEFAULT 'Parent',
    title             TEXT,
    first_name        TEXT NOT NULL,
    last_name         TEXT NOT NULL,
    email             TEXT,
    primary_phone     TEXT,
    secondary_phone   TEXT,
    address           TEXT,
    preferred_method  TEXT NOT NULL DEFAULT 'Email',
    preferred_language TEXT NOT NULL DEFAULT 'English',
    is_primary                INTEGER NOT NULL DEFAULT 0,
    is_emergency_contact      INTEGER NOT NULL DEFAULT 1,
    has_parental_responsibility INTEGER NOT NULL DEFAULT 1,
    receives_communications   INTEGER NOT NULL DEFAULT 1,
    lives_with_student        INTEGER NOT NULL DEFAULT 1,
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pc_student ON parent_contacts(student_id);
CREATE INDEX IF NOT EXISTS idx_pc_primary ON parent_contacts(student_id, is_primary);
CREATE INDEX IF NOT EXISTS idx_pc_email   ON parent_contacts(email);
"""


@dataclass
class Contact:
    contact_id: int
    student_id: str
    relationship: str
    title: str | None
    first_name: str
    last_name: str
    email: str | None
    primary_phone: str | None
    secondary_phone: str | None
    address: str | None
    preferred_method: str
    preferred_language: str
    is_primary: bool
    is_emergency_contact: bool
    has_parental_responsibility: bool
    receives_communications: bool
    lives_with_student: bool
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def full_name(self) -> str:
        parts = [p for p in (self.title, self.first_name, self.last_name) if p]
        return " ".join(parts)


@dataclass
class ContactRow:
    contact: Contact
    student_name: str


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    from education_system.sixthform_system.modules.domain.students import students as _students
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Parent-contacts schema ready at %s", DB_PATH)


def _row(r: sqlite3.Row) -> Contact:
    return Contact(
        contact_id=r["contact_id"], student_id=r["student_id"],
        relationship=r["relationship"], title=r["title"],
        first_name=r["first_name"], last_name=r["last_name"],
        email=r["email"], primary_phone=r["primary_phone"],
        secondary_phone=r["secondary_phone"], address=r["address"],
        preferred_method=r["preferred_method"],
        preferred_language=r["preferred_language"],
        is_primary=bool(r["is_primary"]),
        is_emergency_contact=bool(r["is_emergency_contact"]),
        has_parental_responsibility=bool(r["has_parental_responsibility"]),
        receives_communications=bool(r["receives_communications"]),
        lives_with_student=bool(r["lives_with_student"]),
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def _require(v, label: str):
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        raise ValidationError(f"{label} is required")
    return v


def _validate_email(v: Any) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        return None
    s = str(v).strip()
    if not _EMAIL_RE.match(s):
        raise ValidationError("Email is not a valid address")
    return s.lower()


def _validate_phone(v: Any, label: str) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        return None
    s = str(v).strip()
    if not _PHONE_RE.match(s):
        raise ValidationError(
            f"{label} can only contain digits, spaces, +, (), and -")
    return s


def _validate_student(v: Any) -> str:
    sid = _require(v, "Student ID").strip()
    from education_system.sixthform_system.modules.domain.students import students as _students
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    return sid


def _validate_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["student_id"] = _validate_student(data.get("student_id"))

    rel = _require(data.get("relationship") or DEFAULT_RELATIONSHIP,
                    "Relationship").strip()
    if rel not in RELATIONSHIPS:
        raise ValidationError(
            f"Relationship must be one of: {', '.join(RELATIONSHIPS)}")
    out["relationship"] = rel

    out["title"]      = (data.get("title") or "").strip() or None
    out["first_name"] = _require(data.get("first_name"),
                                    "First name").strip()
    out["last_name"]  = _require(data.get("last_name"),
                                    "Last name").strip()
    out["email"]           = _validate_email(data.get("email"))
    out["primary_phone"]   = _validate_phone(data.get("primary_phone"),
                                                "Primary phone")
    out["secondary_phone"] = _validate_phone(data.get("secondary_phone"),
                                                "Secondary phone")

    if not out["email"] and not out["primary_phone"] \
            and not out["secondary_phone"]:
        raise ValidationError(
            "At least one of email / primary phone / secondary phone "
            "is required so we can reach the contact")

    out["address"] = (data.get("address") or "").strip() or None

    pm = (data.get("preferred_method") or DEFAULT_PREFERRED_METHOD).strip()
    if pm not in PREFERRED_CONTACT_METHODS:
        raise ValidationError(
            f"Preferred method must be one of: "
            f"{', '.join(PREFERRED_CONTACT_METHODS)}")
    out["preferred_method"] = pm

    lang = (data.get("preferred_language")
            or DEFAULT_LANGUAGE).strip()
    if lang not in LANGUAGES:
        raise ValidationError(
            f"Preferred language must be one of: "
            f"{', '.join(LANGUAGES)}")
    out["preferred_language"] = lang

    out["is_primary"]                  = bool(data.get("is_primary"))
    out["is_emergency_contact"]        = bool(
        data.get("is_emergency_contact", True))
    out["has_parental_responsibility"] = bool(
        data.get("has_parental_responsibility", True))
    out["receives_communications"]     = bool(
        data.get("receives_communications", True))
    out["lives_with_student"]          = bool(
        data.get("lives_with_student", True))
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def _clear_other_primaries(conn: sqlite3.Connection, student_id: str,
                            *, except_id: int | None = None) -> None:
    if except_id is None:
        conn.execute(
            "UPDATE parent_contacts SET is_primary=0 "
            "WHERE student_id=? AND is_primary=1", (student_id,))
    else:
        conn.execute(
            "UPDATE parent_contacts SET is_primary=0 "
            "WHERE student_id=? AND is_primary=1 AND contact_id<>?",
            (student_id, except_id))


# ── CRUD ──────────────────────────────────────────────────────────

def create_contact(data: dict[str, Any]) -> Contact:
    init_db()
    try:
        p = _validate_payload(data)
    except ValidationError as e:
        logger.warning("create_contact validation failed: %s", e)
        raise
    with _connect() as conn:
        if p["is_primary"]:
            _clear_other_primaries(conn, p["student_id"])
        cur = conn.execute(
            """INSERT INTO parent_contacts (
                   student_id, relationship, title, first_name, last_name,
                   email, primary_phone, secondary_phone, address,
                   preferred_method, preferred_language,
                   is_primary, is_emergency_contact,
                   has_parental_responsibility, receives_communications,
                   lives_with_student, notes,
                   created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["student_id"], p["relationship"], p["title"],
             p["first_name"], p["last_name"], p["email"],
             p["primary_phone"], p["secondary_phone"], p["address"],
             p["preferred_method"], p["preferred_language"],
             int(p["is_primary"]), int(p["is_emergency_contact"]),
             int(p["has_parental_responsibility"]),
             int(p["receives_communications"]),
             int(p["lives_with_student"]),
             p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_contact(new_id)
    assert out is not None
    logger.info("Created parent contact #%d for %s (%s %s, %s)",
                new_id, p["student_id"], p["first_name"],
                p["last_name"], p["relationship"])
    return out


def get_contact(contact_id: int) -> Contact | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM parent_contacts WHERE contact_id = ?",
            (contact_id,)).fetchone()
        return _row(r) if r else None


def list_contacts(
    *,
    student_id: str | None = None,
    relationship: str | None = None,
    primary_only: bool = False,
    emergency_only: bool = False,
    receives_only: bool = False,
) -> list[Contact]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if relationship:
        if relationship not in RELATIONSHIPS:
            raise ValidationError(
                f"Relationship must be one of: {', '.join(RELATIONSHIPS)}")
        clauses.append("relationship = ?")
        args.append(relationship)
    if primary_only:
        clauses.append("is_primary = 1")
    if emergency_only:
        clauses.append("is_emergency_contact = 1")
    if receives_only:
        clauses.append("receives_communications = 1")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM parent_contacts {where} "
           "ORDER BY student_id, is_primary DESC, last_name, first_name")
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def list_contacts_with_detail(**kwargs) -> list[ContactRow]:
    rows = list_contacts(**kwargs)
    if not rows:
        return []
        from education_system.sixthform_system.modules.domain.students import students as _students
    names = {s.student_id: s.full_name for s in _students.list_students()}
    return [ContactRow(contact=c,
                        student_name=names.get(c.student_id, "(unknown)"))
            for c in rows]


def search_contacts(q: str) -> list[Contact]:
    init_db()
    q = (q or "").strip()
    if not q:
        return list_contacts()
    like = f"%{q}%"
    with _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM parent_contacts
                WHERE first_name LIKE ?
                   OR last_name  LIKE ?
                   OR email      LIKE ?
                   OR primary_phone   LIKE ?
                   OR secondary_phone LIKE ?
                   OR student_id      LIKE ?
                ORDER BY student_id, is_primary DESC,
                          last_name, first_name""",
            (like, like, like, like, like, like),
        ).fetchall()
    return [_row(r) for r in rows]


def contacts_for_student(student_id: str) -> list[Contact]:
    return list_contacts(student_id=student_id)


def primary_for_student(student_id: str) -> Contact | None:
    rows = list_contacts(student_id=student_id, primary_only=True)
    return rows[0] if rows else None


def update_contact(contact_id: int, data: dict[str, Any]) -> Contact:
    init_db()
    existing = get_contact(contact_id)
    if existing is None:
        raise ValidationError(f"No contact with id {contact_id}")
    merged = {
        "student_id":      existing.student_id,
        "relationship":    data.get("relationship", existing.relationship),
        "title":           data.get("title", existing.title),
        "first_name":      data.get("first_name", existing.first_name),
        "last_name":       data.get("last_name", existing.last_name),
        "email":           data.get("email", existing.email),
        "primary_phone":   data.get("primary_phone",
                                      existing.primary_phone),
        "secondary_phone": data.get("secondary_phone",
                                      existing.secondary_phone),
        "address":         data.get("address", existing.address),
        "preferred_method": data.get("preferred_method",
                                       existing.preferred_method),
        "preferred_language": data.get("preferred_language",
                                         existing.preferred_language),
        "is_primary":      data.get("is_primary", existing.is_primary),
        "is_emergency_contact": data.get("is_emergency_contact",
                                            existing.is_emergency_contact),
        "has_parental_responsibility": data.get(
            "has_parental_responsibility",
            existing.has_parental_responsibility),
        "receives_communications": data.get(
            "receives_communications", existing.receives_communications),
        "lives_with_student": data.get("lives_with_student",
                                          existing.lives_with_student),
        "notes":           data.get("notes", existing.notes),
    }
    p = _validate_payload(merged)
    with _connect() as conn:
        if p["is_primary"]:
            _clear_other_primaries(conn, p["student_id"],
                                     except_id=contact_id)
        conn.execute(
            """UPDATE parent_contacts SET
                  relationship=?, title=?, first_name=?, last_name=?,
                  email=?, primary_phone=?, secondary_phone=?, address=?,
                  preferred_method=?, preferred_language=?,
                  is_primary=?, is_emergency_contact=?,
                  has_parental_responsibility=?, receives_communications=?,
                  lives_with_student=?, notes=?,
                  updated_at=datetime('now')
               WHERE contact_id=?""",
            (p["relationship"], p["title"], p["first_name"], p["last_name"],
             p["email"], p["primary_phone"], p["secondary_phone"],
             p["address"], p["preferred_method"], p["preferred_language"],
             int(p["is_primary"]), int(p["is_emergency_contact"]),
             int(p["has_parental_responsibility"]),
             int(p["receives_communications"]),
             int(p["lives_with_student"]),
             p["notes"], contact_id),
        )
        conn.commit()
    out = get_contact(contact_id)
    assert out is not None
    logger.info("Updated parent contact #%d", contact_id)
    return out


def set_primary(contact_id: int) -> Contact:
    """Mark this contact as the primary (clearing any other primary
    for the same student)."""
    init_db()
    existing = get_contact(contact_id)
    if existing is None:
        raise ValidationError(f"No contact with id {contact_id}")
    with _connect() as conn:
        _clear_other_primaries(conn, existing.student_id,
                                 except_id=contact_id)
        conn.execute(
            "UPDATE parent_contacts SET is_primary=1, "
            "updated_at=datetime('now') WHERE contact_id=?",
            (contact_id,))
        conn.commit()
    out = get_contact(contact_id)
    assert out is not None
    logger.info("Set contact #%d as primary for %s",
                contact_id, existing.student_id)
    return out


def delete_contact(contact_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM parent_contacts WHERE contact_id = ?",
            (contact_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted parent contact #%d", contact_id)
            return True
        return False


# ── Summary ───────────────────────────────────────────────────────

@dataclass
class Summary:
    total: int
    students_with_contact: int
    students_without_contact: list[str]
    students_without_primary: list[str]
    students_without_emergency: list[str]
    by_relationship: dict[str, int]
    by_preferred_method: dict[str, int]
    by_language: dict[str, int]
    receives_communications: int
    no_email: int
    no_phone: int


def summary() -> Summary:
    init_db()
    from education_system.sixthform_system.modules.domain.students import students as _students
    all_students = _students.list_students()
    rows = list_contacts()

    by_student: dict[str, list[Contact]] = {}
    for c in rows:
        by_student.setdefault(c.student_id, []).append(c)

    by_rel = {r: 0 for r in RELATIONSHIPS}
    by_pm = {m: 0 for m in PREFERRED_CONTACT_METHODS}
    by_lang = {l: 0 for l in LANGUAGES}
    receives = 0
    no_email = 0
    no_phone = 0
    for c in rows:
        by_rel[c.relationship] = by_rel.get(c.relationship, 0) + 1
        by_pm[c.preferred_method] = by_pm.get(c.preferred_method, 0) + 1
        by_lang[c.preferred_language] = (
            by_lang.get(c.preferred_language, 0) + 1)
        if c.receives_communications:
            receives += 1
        if not c.email:
            no_email += 1
        if not c.primary_phone and not c.secondary_phone:
            no_phone += 1

    without_contact: list[str] = []
    without_primary: list[str] = []
    without_emergency: list[str] = []
    for s in all_students:
        cs = by_student.get(s.student_id, [])
        if not cs:
            without_contact.append(s.student_id)
            continue
        if not any(c.is_primary for c in cs):
            without_primary.append(s.student_id)
        if not any(c.is_emergency_contact for c in cs):
            without_emergency.append(s.student_id)

    return Summary(
        total=len(rows),
        students_with_contact=len(by_student),
        students_without_contact=without_contact,
        students_without_primary=without_primary,
        students_without_emergency=without_emergency,
        by_relationship=by_rel,
        by_preferred_method=by_pm,
        by_language=by_lang,
        receives_communications=receives,
        no_email=no_email,
        no_phone=no_phone,
    )
