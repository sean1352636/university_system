"""Who may do what in academic integrity, the settings, and the audit.

* A **student** sees only their own documents and, once released, their own
  similarity reports — with their own text highlighted, never another
  student's text.
* **Module staff** (anyone in ``module_staff`` for the module, or the
  module's ``instructor``) check and review work on modules they teach.
* An integrity **reviewer** (role) reviews any module.
* An integrity **officer** (role) and administrators run cases, decide
  outcomes and appeals, and manage roles and settings.

Anonymous marking: while an assignment is marked anonymously and its marks
are not released, module staff and reviewers see a candidate number where
they would see a student number (:func:`student_label`). Integrity
officers always see who the student is; they run the case.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from education_system.systems.university.infrastructure.database.schemas import (
    academic_integrity_schema,
)

ADMIN_ROLES = ("admin", "administrator", "superadmin")
STAFF_ROLES = ("staff", "instructor", "lecturer", "teacher", "faculty") + ADMIN_ROLES

SETTINGS = {
    "auto_check": "1",
    "review_threshold": "0.25",
    "high_threshold": "0.5",
    "shingle_words": "6",
    "release_after_review": "1",
    "appeal_days": "14",
    "retention_years": "5",
    "statement_days": "10",
    "review_reminder_days": "5",
    "stage_reminder_days": "14",
    "auto_close": "1",
    "paraphrase_threshold": "0.2",
    "obfuscation_chars": "5",
    "ai_auto_check": "1",
    "ai_min_words": "250",
    "ai_review_threshold": "0.6",
    "external_checks": "0",
    "external_max_queries": "5",
    "notice_version": "2026-2",
    "notice_text": ("Work you submit is compared with other submissions to this university "
                    "to check that it is your own. Quotations in quotation marks and your "
                    "reference list are left out. Written work is also read for signs that "
                    "it was produced with a generative AI tool where the module does not "
                    "allow that; these are only indicators, never proof, and nothing is "
                    "decided on them alone. You can see your own results and comment on "
                    "them. A member of staff reviews every high match or indication before "
                    "anything happens, and you will be told the outcome and how to appeal. "
                    "Your submitted text is kept for the retention period and then removed."),
}


def ensure(conn) -> None:
    academic_integrity_schema.apply_to_connection(conn)


def now(at=None) -> str:
    return (at or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")


def dicts(cur) -> list[dict]:
    names = [d[0] for d in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def one(conn, sql, params=()) -> dict | None:
    found = dicts(conn.execute(sql, params))
    return found[0] if found else None


def require(allowed, message) -> None:
    if not allowed:
        raise PermissionError(message)


def audit(conn, actor, entity, entity_id, action, detail=None) -> None:
    conn.execute("INSERT INTO integrity_audit (entity, entity_id, action, actor, detail, at) "
                 "VALUES (?, ?, ?, ?, ?, ?)",
                 (entity, None if entity_id is None else str(entity_id), action, actor,
                  json.dumps(detail, default=str) if detail else None, now()))


def recent_audit(conn, who, limit=200) -> list[dict]:
    require(is_officer(conn, who), "Only an integrity officer can read the audit")
    return dicts(conn.execute("SELECT * FROM integrity_audit ORDER BY audit_id DESC LIMIT ?",
                              (int(limit),)))


# ── the person asking ───────────────────────────────────────────────────


@dataclass(frozen=True)
class Person:
    username: str
    role: str
    user_id: int | None = None
    student_id: str | None = None

    @property
    def is_admin(self) -> bool:
        return self.role in ADMIN_ROLES

    @property
    def is_staff(self) -> bool:
        return self.role in STAFF_ROLES

    @property
    def is_student(self) -> bool:
        return self.role == "student"


def person(conn, username, role="") -> Person:
    """The person behind ``username``; the role comes from ``users`` when
    the caller doesn't know it."""
    row = conn.execute("SELECT id, role, student_id FROM users WHERE username = ? "
                       "COLLATE NOCASE", (username,)).fetchone()
    role = str(role or (row[1] if row else "") or "").lower()
    return Person(str(username), role, row[0] if row else None, row[2] if row else None)


def from_user(conn, user: dict | None) -> Person | None:
    if not user or not user.get("username"):
        return None
    return person(conn, user["username"], user.get("role") or "")


# ── roles ───────────────────────────────────────────────────────────────


def holds(conn, who: Person, role) -> bool:
    if who.is_admin:
        return True
    ensure(conn)
    return conn.execute("SELECT 1 FROM integrity_roles WHERE username = ? AND role = ?",
                        (who.username, role)).fetchone() is not None


def is_officer(conn, who: Person) -> bool:
    return holds(conn, who, "officer")


def grant(conn, who: Person, username, role) -> None:
    require(who.is_admin, "Only an administrator can grant integrity roles")
    if role not in ("reviewer", "officer"):
        raise ValueError("Role must be reviewer or officer")
    target = person(conn, username)
    if not target.is_staff:
        raise ValueError(f"No member of staff with username {username!r}")
    ensure(conn)
    conn.execute("INSERT OR IGNORE INTO integrity_roles (username, role, granted_by, granted_at) "
                 "VALUES (?, ?, ?, ?)", (target.username, role, who.username, now()))
    audit(conn, who.username, "role", target.username, "granted", {"role": role})


def revoke(conn, who: Person, username, role) -> None:
    require(who.is_admin, "Only an administrator can revoke integrity roles")
    ensure(conn)
    conn.execute("DELETE FROM integrity_roles WHERE username = ? AND role = ?", (username, role))
    audit(conn, who.username, "role", username, "revoked", {"role": role})


def roles(conn) -> list[dict]:
    ensure(conn)
    return dicts(conn.execute("SELECT * FROM integrity_roles ORDER BY username, role"))


# ── modules ─────────────────────────────────────────────────────────────


def teaches(conn, who: Person, module_code) -> bool:
    if not module_code or not who.is_staff:
        return False
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'module_staff'").fetchone():
        if conn.execute("SELECT 1 FROM module_staff WHERE module_code = ? AND username = ? "
                        "COLLATE NOCASE", (module_code, who.username)).fetchone():
            return True
    row = conn.execute("SELECT 1 FROM modules WHERE module_code = ? AND (instructor = ? "
                       "COLLATE NOCASE OR instructor_id = ?)",
                       (module_code, who.username, who.user_id)).fetchone()
    return row is not None


def taught_modules(conn, who: Person) -> list[str] | None:
    """Modules ``who`` may review; ``None`` means every module."""
    if is_officer(conn, who) or holds(conn, who, "reviewer"):
        return None
    if not who.is_staff:
        return []
    found = {r[0] for r in conn.execute("SELECT module_code FROM modules WHERE instructor = ? "
                                        "COLLATE NOCASE OR instructor_id = ?",
                                        (who.username, who.user_id))}
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'module_staff'").fetchone():
        found |= {r[0] for r in conn.execute("SELECT module_code FROM module_staff "
                                             "WHERE username = ? COLLATE NOCASE",
                                             (who.username,))}
    return sorted(found)


def can_review(conn, who: Person, module_code) -> bool:
    modules = taught_modules(conn, who)
    return modules is None or (module_code in modules)


def owns(who: Person, doc: dict) -> bool:
    if who.student_id and doc.get("student_id") == who.student_id:
        return True
    return who.user_id is not None and doc.get("author_id") == who.user_id \
        and doc.get("kind", "submission") == "submission" and who.is_student


def can_see_document(conn, who: Person, doc: dict) -> bool:
    return owns(who, doc) or can_review(conn, who, doc.get("module_code"))


# ── settings ────────────────────────────────────────────────────────────


def setting(conn, key) -> str:
    ensure(conn)
    row = conn.execute("SELECT value FROM integrity_settings WHERE key = ?", (key,)).fetchone()
    return row[0] if row else SETTINGS[key]


def number(conn, key) -> float:
    try:
        return float(setting(conn, key))
    except ValueError:
        return float(SETTINGS[key])


def _check_value(key, value) -> None:
    if key in ("review_threshold", "high_threshold", "paraphrase_threshold",
               "ai_review_threshold"):
        if not 0 < float(value) <= 1:
            raise ValueError(f"{key} must be between 0 and 1")
    elif key in ("shingle_words", "appeal_days", "retention_years", "statement_days",
                 "review_reminder_days", "stage_reminder_days", "obfuscation_chars",
                 "external_max_queries", "ai_min_words"):
        if not value.isdigit() or int(value) < 1:
            raise ValueError(f"{key} must be a whole number above zero")
        if key == "shingle_words" and not 3 <= int(value) <= 15:
            raise ValueError("shingle_words must be between 3 and 15")
        if key == "external_max_queries" and int(value) > 20:
            raise ValueError("external_max_queries can be at most 20")
    elif key in ("auto_check", "release_after_review", "auto_close",
                 "external_checks", "ai_auto_check") and value not in ("0", "1"):
        raise ValueError(f"{key} must be 0 or 1")
    elif not value:
        raise ValueError(f"{key} cannot be empty")


def set_setting(conn, who: Person, key, value) -> None:
    require(is_officer(conn, who), "Only an integrity officer can change integrity settings")
    if key not in SETTINGS:
        raise ValueError(f"Unknown setting {key!r}")
    value = str(value).strip()
    try:
        _check_value(key, value)
    except ValueError as exc:
        if "could not convert" in str(exc):
            raise ValueError(f"{key} must be a number") from None
        raise
    conn.execute("INSERT INTO integrity_settings (key, value, updated_by, updated_at) "
                 "VALUES (?, ?, ?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
                 "updated_by = excluded.updated_by, updated_at = excluded.updated_at",
                 (key, value, who.username, now()))
    audit(conn, who.username, "setting", key, "changed", {"value": value})


def module_threshold(conn, module_code) -> float:
    """The review threshold for a module (its own setting, else the default)."""
    row = conn.execute("SELECT similarity_threshold FROM course_integrity_settings "
                       "WHERE module_code = ?", (module_code,)).fetchone()
    if row and row[0]:
        return float(row[0])
    return number(conn, "review_threshold")


def checks_enabled(conn, module_code) -> bool:
    if setting(conn, "auto_check") != "1":
        return False
    row = conn.execute("SELECT plagiarism_enabled FROM course_integrity_settings "
                       "WHERE module_code = ?", (module_code,)).fetchone()
    return not row or bool(row[0])


def set_module_settings(conn, who: Person, module_code, *, enabled, threshold,
                        allow_collaboration=False, notes="", ai_enabled=None) -> None:
    require(is_officer(conn, who) or teaches(conn, who, module_code),
            "Only the module's staff or an integrity officer can change its settings")
    threshold = float(threshold)
    if not 0 < threshold <= 1:
        raise ValueError("The threshold must be between 0 and 1")
    ensure(conn)
    conn.execute("INSERT INTO course_integrity_settings (module_code, plagiarism_enabled, "
                 "similarity_threshold, allow_collaboration, notes, updated_at, updated_by) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(module_code) DO UPDATE SET "
                 "plagiarism_enabled = excluded.plagiarism_enabled, "
                 "similarity_threshold = excluded.similarity_threshold, "
                 "allow_collaboration = excluded.allow_collaboration, notes = excluded.notes, "
                 "updated_at = excluded.updated_at, updated_by = excluded.updated_by",
                 (module_code, 1 if enabled else 0, threshold, 1 if allow_collaboration else 0,
                  notes, now(), who.username))
    if ai_enabled is not None:
        conn.execute("UPDATE course_integrity_settings SET ai_detection_enabled = ? "
                     "WHERE module_code = ?", (1 if ai_enabled else 0, module_code))
    audit(conn, who.username, "module", module_code, "settings changed",
          {"enabled": bool(enabled), "threshold": threshold, "ai_enabled": ai_enabled})


def ai_checks_enabled(conn, module_code) -> bool:
    """AI-writing indicators run on submission (setting ``ai_auto_check``)
    unless the module turned them off (``ai_detection_enabled``)."""
    if setting(conn, "ai_auto_check") != "1":
        return False
    row = conn.execute("SELECT ai_detection_enabled FROM course_integrity_settings "
                       "WHERE module_code = ?", (module_code,)).fetchone()
    return not row or row[0] is None or bool(row[0])


def collaboration_allowed(conn, module_code) -> bool:
    if not module_code:
        return False
    ensure(conn)
    row = conn.execute("SELECT allow_collaboration FROM course_integrity_settings "
                       "WHERE module_code = ?", (module_code,)).fetchone()
    return bool(row and row[0])


# ── anonymous marking ───────────────────────────────────────────────────


def anonymised(conn, assignment_id) -> bool:
    """Is this assignment marked anonymously with its marks not yet released?"""
    if not assignment_id:
        return False
    cols = {r[1] for r in conn.execute("PRAGMA table_info(assignments)")}
    if "anonymous_marking" not in cols:
        return False
    released = "grades_released_at" if "grades_released_at" in cols else "NULL"
    row = conn.execute(f"SELECT anonymous_marking, {released} FROM assignments "  # nosec B608
                       "WHERE id = ?", (assignment_id,)).fetchone()
    return bool(row and row[0] and not row[1])


def student_label(conn, who: Person, student_id, assignment_id) -> str | None:
    """What ``who`` may see in place of ``student_id``: the student number,
    or the candidate number while the assignment is marked anonymously."""
    if student_id is None or who.is_student or is_officer(conn, who):
        return student_id
    if not anonymised(conn, assignment_id):
        return student_id
    row = None
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'assignment_candidate_numbers'"
                    ).fetchone():
        row = conn.execute("SELECT candidate_number FROM assignment_candidate_numbers WHERE "
                           "assignment_id = ? AND student_id = ?",
                           (assignment_id, str(student_id))).fetchone()
    return row[0] if row else "anonymous candidate"


# ── who to tell ─────────────────────────────────────────────────────────


def email_of(conn, username) -> str | None:
    row = conn.execute("SELECT email FROM users WHERE username = ? COLLATE NOCASE",
                       (username,)).fetchone()
    return row[0] if row and row[0] else None


def officer_emails(conn) -> list[str]:
    """Integrity officers, or the administrators when there are none."""
    ensure(conn)
    found = [r[0] for r in conn.execute(
        "SELECT u.email FROM integrity_roles r JOIN users u ON u.username = r.username "
        "COLLATE NOCASE WHERE r.role = 'officer' AND COALESCE(u.email, '') <> ''")]
    if not found:
        marks = ",".join("?" * len(ADMIN_ROLES))
        found = [r[0] for r in conn.execute(
            f"SELECT email FROM users WHERE LOWER(role) IN ({marks}) "  # nosec B608
            "AND COALESCE(email, '') <> ''", ADMIN_ROLES)]
    return sorted(set(found))


def module_staff_emails(conn, module_code) -> list[str]:
    """The module's instructor and anyone in ``module_staff`` for it."""
    names: set[str] = set()
    row = conn.execute("SELECT instructor, instructor_id FROM modules WHERE module_code = ?",
                       (module_code,)).fetchone()
    found: set[str] = set()
    if row:
        if row[0]:
            names.add(str(row[0]))
        if row[1]:
            email = conn.execute("SELECT email FROM users WHERE id = ?", (row[1],)).fetchone()
            if email and email[0]:
                found.add(email[0])
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'module_staff'").fetchone():
        names |= {r[0] for r in conn.execute("SELECT username FROM module_staff WHERE "
                                             "module_code = ?", (module_code,))}
    found |= {e for e in (email_of(conn, n) for n in names) if e}
    return sorted(found)


# ── the student notice ──────────────────────────────────────────────────


def notice(conn) -> dict:
    return {"version": setting(conn, "notice_version"), "text": setting(conn, "notice_text")}


def acknowledge(conn, who: Person) -> None:
    ensure(conn)
    conn.execute("INSERT OR IGNORE INTO integrity_acknowledgements (username, notice_version, "
                 "acknowledged_at) VALUES (?, ?, ?)",
                 (who.username, setting(conn, "notice_version"), now()))


def has_acknowledged(conn, who: Person) -> bool:
    ensure(conn)
    return conn.execute("SELECT 1 FROM integrity_acknowledgements WHERE username = ? AND "
                        "notice_version = ?", (who.username, setting(conn, "notice_version"))
                        ).fetchone() is not None
