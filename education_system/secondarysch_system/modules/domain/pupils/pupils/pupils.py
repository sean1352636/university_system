"""Pupil data layer for the Secondary School System.

Owns the SQLite DB at ``secondarysch_system/data/secondary.db`` and
the CRUD functions used by the CLI menu and Tk views. Year groups are
7–11 (KS3 / KS4). Pupil IDs use the ``Y`` prefix.
"""

from __future__ import annotations

import logging
import os
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.secondarysch_system.core import paths

logger = logging.getLogger(__name__)

# Re-exported so existing references to ``pupils.DB_PATH`` keep working.
# Tests that need an isolated DB still rebind this module attribute.
DB_PATH = paths.PUPILS_DB

ID_PREFIX = "Y"
ID_DIGITS = 7
YEAR_GROUPS = ("7", "8", "9", "10", "11")
EMAIL_DOMAIN = "secondaryschool.local"

_PHONE_RE = re.compile(r"^[0-9 +()\-]{6,20}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DOB_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class Pupil:
    pupil_id: str
    first_name: str
    last_name: str
    year_group: str
    form_group: str | None
    date_of_birth: str | None
    email: str
    phone: str | None
    parent_name: str | None
    parent_phone: str | None
    send_status: str | None

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


_SCHEMA = """
CREATE TABLE IF NOT EXISTS pupils (
    pupil_id        TEXT PRIMARY KEY,
    first_name      TEXT NOT NULL,
    last_name       TEXT NOT NULL,
    year_group      TEXT NOT NULL,
    form_group      TEXT,
    date_of_birth   TEXT,
    email           TEXT NOT NULL UNIQUE,
    phone           TEXT,
    parent_name     TEXT,
    parent_phone    TEXT,
    send_status     TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);
"""


class ValidationError(ValueError):
    """Raised for invalid pupil-form input."""


def _connect() -> sqlite3.Connection:
    os.makedirs(DB_PATH.parent, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise secondary pupils DB at %s", DB_PATH)
        raise
    logger.info("Secondary pupils DB ready at %s", DB_PATH)
    _DB_READY = True


def _row(r: sqlite3.Row) -> Pupil:
    return Pupil(
        pupil_id=r["pupil_id"],
        first_name=r["first_name"],
        last_name=r["last_name"],
        year_group=r["year_group"],
        form_group=r["form_group"],
        date_of_birth=r["date_of_birth"],
        email=r["email"],
        phone=r["phone"],
        parent_name=r["parent_name"],
        parent_phone=r["parent_phone"],
        send_status=r["send_status"],
    )


def generate_pupil_id() -> str:
    init_db()
    with _connect() as conn:
        for attempt in range(50):
            n = random.randint(10 ** (ID_DIGITS - 1), 10 ** ID_DIGITS - 1)
            pid = f"{ID_PREFIX}{n}"
            if conn.execute(
                "SELECT 1 FROM pupils WHERE pupil_id = ?", (pid,)
            ).fetchone() is None:
                if attempt > 0:
                    logger.info("Allocated pupil id %s after %d collisions",
                                pid, attempt)
                return pid
            if attempt == 25:
                logger.warning("Pupil-id allocator hit %d collisions", attempt)
    logger.error("Exhausted 50 attempts allocating a unique pupil id")
    raise RuntimeError("Could not allocate a unique pupil id after 50 tries")


def _generate_email(pupil_id: str) -> str:
    return f"{pupil_id.lower()}@{EMAIL_DOMAIN}"


def _require(value: str | None, label: str) -> str:
    if not value or not str(value).strip():
        raise ValidationError(f"{label} is required")
    return str(value).strip()


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["first_name"] = _require(data.get("first_name"), "First name")
    out["last_name"] = _require(data.get("last_name"), "Last name")
    yg = _require(data.get("year_group"), "Year group")
    if yg not in YEAR_GROUPS:
        raise ValidationError(
            f"Year group must be one of {', '.join(YEAR_GROUPS)}")
    out["year_group"] = yg
    out["form_group"] = (data.get("form_group") or "").strip() or None
    dob = (data.get("date_of_birth") or "").strip()
    if dob and not _DOB_RE.match(dob):
        raise ValidationError("Date of birth must be YYYY-MM-DD")
    out["date_of_birth"] = dob or None
    phone = (data.get("phone") or "").strip()
    if phone and not _PHONE_RE.match(phone):
        raise ValidationError("Phone number contains invalid characters")
    out["phone"] = phone or None
    out["parent_name"] = (data.get("parent_name") or "").strip() or None
    pphone = (data.get("parent_phone") or "").strip()
    if pphone and not _PHONE_RE.match(pphone):
        raise ValidationError("Parent phone contains invalid characters")
    out["parent_phone"] = pphone or None
    send = (data.get("send_status") or "").strip()
    if send and send.lower() not in ("yes", "no"):
        raise ValidationError("SEND status must be 'yes' or 'no'")
    out["send_status"] = send.lower() if send else None
    return out


def create_pupil(data: dict[str, Any]) -> Pupil:
    init_db()
    logger.debug("create_pupil called with fields: %s",
                 sorted(k for k, v in data.items() if v not in (None, "")))
    try:
        payload = _validate(data)
    except ValidationError as e:
        logger.warning("create_pupil validation failed: %s", e)
        raise
    pid = generate_pupil_id()
    email = _generate_email(pid)
    try:
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO pupils (
                    pupil_id, first_name, last_name, year_group, form_group,
                    date_of_birth, email, phone, parent_name, parent_phone,
                    send_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (pid, payload["first_name"], payload["last_name"],
                 payload["year_group"], payload["form_group"],
                 payload["date_of_birth"], email, payload["phone"],
                 payload["parent_name"], payload["parent_phone"],
                 payload["send_status"]),
            )
            conn.commit()
    except sqlite3.IntegrityError as e:
        logger.exception("INSERT failed for new pupil id=%s (collision?)", pid)
        raise ValidationError(f"Could not create pupil — {e}") from e
    except sqlite3.Error:
        logger.exception("Database error creating pupil id=%s", pid)
        raise
    pupil = get_pupil(pid)
    assert pupil is not None
    logger.info("Created pupil %s (%s, year %s)",
                pupil.pupil_id, pupil.full_name, pupil.year_group)
    # Anchor a canonical journey_id so this pupil links to the same person
    # in the primary/sixth-form systems (best-effort; matched on name+DOB).
    try:
        from education_system.shared.cross_system import person, progression
        jid = progression.register_local_student(
            "school", student_id=pupil.pupil_id,
            first_name=pupil.first_name, last_name=pupil.last_name,
            date_of_birth=pupil.date_of_birth)
        if jid:
            person.link_local_record("school", pupil.pupil_id, jid)
    except Exception:
        logger.debug("Journey registration skipped for pupil %s",
                     pupil.pupil_id, exc_info=True)
    return pupil


def get_pupil(pupil_id: str) -> Pupil | None:
    init_db()
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT * FROM pupils WHERE pupil_id = ?", (pupil_id,)
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_pupil(%s) failed", pupil_id)
        raise
    if row is None:
        logger.debug("get_pupil(%s) -> miss", pupil_id)
        return None
    return _row(row)


def list_pupils() -> list[Pupil]:
    init_db()
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM pupils ORDER BY year_group, last_name, first_name"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("list_pupils failed")
        raise
    logger.debug("list_pupils -> %d row(s)", len(rows))
    return [_row(r) for r in rows]


def search_pupils(query: str) -> list[Pupil]:
    init_db()
    raw = (query or "").strip()
    q = f"%{raw}%"
    try:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM pupils
                WHERE pupil_id LIKE ?
                   OR first_name LIKE ?
                   OR last_name LIKE ?
                   OR email LIKE ?
                   OR form_group LIKE ?
                ORDER BY year_group, last_name, first_name
                """,
                (q, q, q, q, q),
            ).fetchall()
    except sqlite3.Error:
        logger.exception("search_pupils(query_len=%d) failed", len(raw))
        raise
    logger.debug("search_pupils(query_len=%d) -> %d match(es)", len(raw), len(rows))
    return [_row(r) for r in rows]


_ADV_SORTS: dict[str, str] = {
    "name":  "last_name, first_name",
    "year":  "year_group, last_name, first_name",
    "id":    "pupil_id",
    "email": "email",
    "dob":   "date_of_birth",
}


def advanced_search(filters: dict[str, Any]) -> list[Pupil]:
    """Filter pupils by any combination of criteria.

    Recognised keys (all optional, all combined with AND):
      name, year_group, form_group, email, parent_name
      send_status     -- "yes" | "no"
      dob_from        -- ISO date inclusive lower bound
      dob_to          -- ISO date inclusive upper bound
      has_phone       -- "yes" | "no"
      has_parent      -- "yes" | "no"
      sort_by         -- key in _ADV_SORTS (default "year")
    """
    init_db()
    where: list[str] = []
    params: list[Any] = []

    def like(field: str, value: str) -> None:
        where.append(f"{field} LIKE ?")
        params.append(f"%{value}%")

    name = (filters.get("name") or "").strip()
    if name:
        where.append("(first_name LIKE ? OR last_name LIKE ?)")
        params.extend([f"%{name}%", f"%{name}%"])

    year = (filters.get("year_group") or "").strip()
    if year:
        if year not in YEAR_GROUPS:
            raise ValidationError(
                f"Year group filter must be one of {', '.join(YEAR_GROUPS)}")
        where.append("year_group = ?")
        params.append(year)

    for key, column in (("form_group", "form_group"),
                        ("email", "email"),
                        ("parent_name", "parent_name")):
        v = (filters.get(key) or "").strip()
        if v:
            like(column, v)

    send = (filters.get("send_status") or "").strip().lower()
    if send:
        if send not in ("yes", "no"):
            raise ValidationError("SEND filter must be 'yes' or 'no'")
        where.append("send_status = ?")
        params.append(send)

    for key, column, op in (("dob_from", "date_of_birth", ">="),
                            ("dob_to",   "date_of_birth", "<=")):
        v = (filters.get(key) or "").strip()
        if v:
            if not _DOB_RE.match(v):
                raise ValidationError(f"{key} must be YYYY-MM-DD")
            where.append(f"{column} {op} ?")
            params.append(v)

    for key, column in (("has_phone", "phone"),
                        ("has_parent", "parent_phone")):
        v = (filters.get(key) or "").strip().lower()
        if v == "yes":
            where.append(f"{column} IS NOT NULL AND {column} != ''")
        elif v == "no":
            where.append(f"({column} IS NULL OR {column} = '')")
        elif v not in ("", "any"):
            raise ValidationError(f"{key} must be 'yes', 'no', or blank")

    sort_key = (filters.get("sort_by") or "year").strip().lower()
    order_by = _ADV_SORTS.get(sort_key)
    if order_by is None:
        raise ValidationError(
            f"sort_by must be one of {', '.join(_ADV_SORTS)}")

    sql = "SELECT * FROM pupils"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY {order_by}"

    try:
        with _connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("advanced_search failed (filters=%s)",
                         sorted(k for k, v in filters.items() if v))
        raise
    logger.info("advanced_search: %d filter(s), %d result(s)",
                len(where), len(rows))
    return [_row(r) for r in rows]


def update_pupil(pupil_id: str, data: dict[str, Any]) -> Pupil:
    init_db()
    logger.debug("update_pupil(%s) called with fields: %s", pupil_id,
                 sorted(k for k, v in data.items() if v not in (None, "")))
    try:
        payload = _validate(data)
    except ValidationError as e:
        logger.warning("update_pupil(%s) validation failed: %s", pupil_id, e)
        raise
    try:
        with _connect() as conn:
            cur = conn.execute(
                """
                UPDATE pupils SET
                    first_name = ?, last_name = ?, year_group = ?, form_group = ?,
                    date_of_birth = ?, phone = ?, parent_name = ?,
                    parent_phone = ?, send_status = ?
                WHERE pupil_id = ?
                """,
                (payload["first_name"], payload["last_name"],
                 payload["year_group"], payload["form_group"],
                 payload["date_of_birth"], payload["phone"],
                 payload["parent_name"], payload["parent_phone"],
                 payload["send_status"], pupil_id),
            )
            if cur.rowcount == 0:
                logger.warning("update_pupil called for unknown id %s", pupil_id)
                raise ValidationError(f"No pupil with id {pupil_id}")
            conn.commit()
    except sqlite3.IntegrityError as e:
        logger.exception("UPDATE failed for pupil id=%s", pupil_id)
        raise ValidationError(f"Could not update pupil — {e}") from e
    except sqlite3.Error:
        logger.exception("Database error updating pupil id=%s", pupil_id)
        raise
    pupil = get_pupil(pupil_id)
    assert pupil is not None
    logger.info("Updated pupil %s (%s, year %s)",
                pupil_id, pupil.full_name, pupil.year_group)
    return pupil


def delete_pupil(pupil_id: str) -> bool:
    init_db()
    snapshot = get_pupil(pupil_id)
    try:
        with _connect() as conn:
            cur = conn.execute("DELETE FROM pupils WHERE pupil_id = ?", (pupil_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting pupil id=%s", pupil_id)
        raise
    if deleted:
        if snapshot is not None:
            logger.info("Deleted pupil %s (%s)", pupil_id, snapshot.full_name)
        else:
            logger.info("Deleted pupil %s (no snapshot — race?)", pupil_id)
    else:
        logger.warning("delete_pupil called for unknown id %s", pupil_id)
    return deleted
