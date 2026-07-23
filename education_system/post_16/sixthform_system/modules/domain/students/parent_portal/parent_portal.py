"""Parent / guardian portal for the Sixth Form System.

This is the data + auth layer behind a parent-facing self-service view.
The system already records parent *contact details* (``parent_contacts``)
but has no way for a parent to log in and see their child's record. This
module adds:

* **Parent accounts** — username + salted PBKDF2 password hash, stored
  in the shared ``sixthform.db`` (kept separate from staff/student auth
  so the two never collide).
* **Student links** — which students an account may view. A parent can
  be linked to more than one child; a child can have more than one
  linked guardian.
* **Read-only snapshots** — a safe, aggregated view of each linked
  child built from the modules a parent should see: attendance, risk
  band, predicted grades, recent behaviour and UCAS progress. No raw
  safeguarding / medical data is ever exposed here.

The staff CLI/GUI manage accounts and links; the REST API
(:mod:`sixthform_system.api`) serves the snapshots to authenticated
parents.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import logging
import secrets
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.post_16.sixthform_system.core import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.PARENT_PORTAL_DB

_PBKDF2_ROUNDS = 200_000


@dataclass
class ParentAccount:
    account_id: int
    username: str
    full_name: str
    email: str | None
    is_active: bool
    created_at: str
    last_login: str | None


# ── DB plumbing ──────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_SCHEMA = """
CREATE TABLE IF NOT EXISTS parent_accounts (
    account_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    full_name     TEXT NOT NULL,
    email         TEXT,
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT DEFAULT (datetime('now')),
    last_login    TEXT
);

CREATE TABLE IF NOT EXISTS parent_student_links (
    account_id   INTEGER NOT NULL,
    student_id   TEXT NOT NULL,
    relationship TEXT NOT NULL DEFAULT 'Parent',
    created_at   TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (account_id, student_id),
    FOREIGN KEY (account_id) REFERENCES parent_accounts(account_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id)        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pslink_student ON parent_student_links(student_id);
"""

_DB_READY = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.post_16.sixthform_system.modules.domain.students.students import students as _students
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    _DB_READY = True
    logger.debug("Parent-portal schema ready at %s", DB_PATH)


class ValidationError(ValueError):
    """Raised for invalid portal input."""


# ── Password hashing (stdlib PBKDF2) ─────────────────────────────────

def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _PBKDF2_ROUNDS)
    return dk.hex(), salt


def _verify_password(password: str, stored_hash: str, salt: str) -> bool:
    candidate, _ = _hash_password(password, salt)
    return secrets.compare_digest(candidate, stored_hash)


# ── Account management ───────────────────────────────────────────────

def _row_to_account(r: sqlite3.Row) -> ParentAccount:
    return ParentAccount(
        account_id=r["account_id"], username=r["username"], full_name=r["full_name"],
        email=r["email"], is_active=bool(r["is_active"]),
        created_at=r["created_at"], last_login=r["last_login"])


def create_account(*, username: str, password: str, full_name: str,
                   email: str = "") -> int:
    init_db()
    username = (username or "").strip().lower()
    if not username:
        raise ValidationError("Username is required")
    if len(password or "") < 8:
        raise ValidationError("Password must be at least 8 characters")
    if not (full_name or "").strip():
        raise ValidationError("Full name is required")
    pw_hash, salt = _hash_password(password)
    with _connect() as conn:
        if conn.execute("SELECT 1 FROM parent_accounts WHERE username=?", (username,)).fetchone():
            raise ValidationError(f"Username '{username}' already exists")
        cur = conn.execute(
            "INSERT INTO parent_accounts (username, full_name, email, password_hash, password_salt) "
            "VALUES (?,?,?,?,?)",
            (username, full_name.strip(), email.strip() or None, pw_hash, salt))
        conn.commit()
        logger.info("Created parent account %s", username)
        return cur.lastrowid


def set_password(account_id: int, new_password: str) -> None:
    init_db()
    if len(new_password or "") < 8:
        raise ValidationError("Password must be at least 8 characters")
    pw_hash, salt = _hash_password(new_password)
    with _connect() as conn:
        conn.execute(
            "UPDATE parent_accounts SET password_hash=?, password_salt=? WHERE account_id=?",
            (pw_hash, salt, account_id))
        conn.commit()


def set_active(account_id: int, active: bool) -> None:
    init_db()
    with _connect() as conn:
        conn.execute("UPDATE parent_accounts SET is_active=? WHERE account_id=?",
                     (1 if active else 0, account_id))
        conn.commit()


def delete_account(account_id: int) -> None:
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM parent_accounts WHERE account_id=?", (account_id,))
        conn.commit()


def list_accounts() -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM parent_accounts ORDER BY username").fetchall()
        out = []
        for r in rows:
            links = conn.execute(
                "SELECT COUNT(*) AS n FROM parent_student_links WHERE account_id=?",
                (r["account_id"],)).fetchone()["n"]
            d = _row_to_account(r).__dict__
            d["linked_students"] = links
            out.append(d)
    return out


def authenticate(username: str, password: str) -> ParentAccount | None:
    """Return the account on success, recording last_login; else None."""
    init_db()
    username = (username or "").strip().lower()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM parent_accounts WHERE username=? AND is_active=1", (username,)).fetchone()
        if not r or not _verify_password(password or "", r["password_hash"], r["password_salt"]):
            logger.info("Failed parent login for %s", username)
            return None
        conn.execute("UPDATE parent_accounts SET last_login=? WHERE account_id=?",
                     (_dt.datetime.now().isoformat(timespec="seconds"), r["account_id"]))
        conn.commit()
        return _row_to_account(r)


# ── Student links ────────────────────────────────────────────────────

def link_student(account_id: int, student_id: str, *, relationship: str = "Parent") -> None:
    init_db()
    with _connect() as conn:
        if not conn.execute("SELECT 1 FROM students WHERE student_id=?", (student_id,)).fetchone():
            raise ValidationError(f"Unknown student: {student_id}")
        if not conn.execute("SELECT 1 FROM parent_accounts WHERE account_id=?", (account_id,)).fetchone():
            raise ValidationError(f"Unknown account: {account_id}")
        conn.execute(
            "INSERT OR REPLACE INTO parent_student_links (account_id, student_id, relationship) "
            "VALUES (?,?,?)", (account_id, student_id, relationship or "Parent"))
        conn.commit()


def unlink_student(account_id: int, student_id: str) -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            "DELETE FROM parent_student_links WHERE account_id=? AND student_id=?",
            (account_id, student_id))
        conn.commit()


def linked_students(account_id: int) -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT l.student_id, l.relationship, s.first_name, s.last_name
              FROM parent_student_links l
              JOIN students s ON s.student_id = l.student_id
             WHERE l.account_id=?
             ORDER BY s.last_name, s.first_name
            """, (account_id,)).fetchall()
    return [{"student_id": r["student_id"], "relationship": r["relationship"],
             "full_name": f"{r['first_name']} {r['last_name']}".strip()} for r in rows]


# ── Read-only child snapshots ────────────────────────────────────────

def student_snapshot(student_id: str) -> dict[str, Any]:
    """Build the parent-safe view of one student.

    Aggregates only the fields appropriate for a guardian: identity,
    attendance, risk band (no internal factor breakdown), predicted vs
    target grades, a recent behaviour summary and UCAS progress %.
    """
    init_db()
    from education_system.post_16.sixthform_system.modules.domain.assessment.risk_analytics import risk_analytics

    with _connect() as conn:
        s = conn.execute(
            "SELECT first_name, last_name, email, status FROM students WHERE student_id=?",
            (student_id,)).fetchone()
        if not s:
            raise ValidationError(f"Unknown student: {student_id}")
        # Recent behaviour (last 30 days), positive/negative split.
        behaviour = {"positive": 0, "negative": 0}
        if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='behaviour_entries'").fetchone():
            start = (_dt.date.today() - _dt.timedelta(days=30)).isoformat()
            for r in conn.execute(
                "SELECT entry_type, COUNT(*) n FROM behaviour_entries "
                "WHERE student_id=? AND entry_date>=? GROUP BY entry_type", (student_id, start)):
                if r["entry_type"] == "Positive":
                    behaviour["positive"] = r["n"]
                elif r["entry_type"] == "Negative":
                    behaviour["negative"] = r["n"]

    assessment = risk_analytics.assess_student(student_id)
    subjects = [{
        "subject": p.subject, "predicted": p.predicted_grade,
        "target": p.target_grade, "latest_mock": p.latest_mock_grade,
        "forecast": p.forecast_grade, "on_target": p.on_target,
    } for p in assessment.predictions]

    ucas = None
    try:
        from education_system.post_16.sixthform_system.modules.domain.progression.ucas_workflow import ucas_workflow
        pipe = ucas_workflow.get_pipeline(student_id)
        ucas = {"percent": pipe["percent"], "complete": pipe["complete"],
                "total": pipe["total"]}
    except Exception:
        logger.debug("UCAS pipeline unavailable for %s", student_id, exc_info=True)

    return {
        "student_id": student_id,
        "full_name": f"{s['first_name']} {s['last_name']}".strip(),
        "status": s["status"],
        "attendance_pct": assessment.attendance_pct,
        "risk_band": assessment.band,
        "behaviour_30d": behaviour,
        "subjects": subjects,
        "ucas": ucas,
    }


def account_dashboard(account_id: int) -> dict[str, Any]:
    """Everything one logged-in parent should see: their identity plus a
    snapshot per linked child."""
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM parent_accounts WHERE account_id=?", (account_id,)).fetchone()
        if not r:
            raise ValidationError(f"Unknown account: {account_id}")
        account = _row_to_account(r)
    children = []
    for link in linked_students(account_id):
        snap = student_snapshot(link["student_id"])
        snap["relationship"] = link["relationship"]
        children.append(snap)
    return {
        "account": {"username": account.username, "full_name": account.full_name,
                    "email": account.email},
        "children": children,
    }
