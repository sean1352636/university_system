"""Pupil data layer for the Primary School System.

Reads the primary school DB named by ``paths.PRIMARY_PUPILS_DB``. Year
groups are R (Reception) through 6. Pupil IDs use the ``P`` prefix.
"""

from __future__ import annotations

import logging
import os
import random
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system import paths

logger = logging.getLogger(__name__)

# Anchored on the single paths module, not on __file__. This module used
# to compute `parents[3] / "data"`, which resolved inside the package —
# a location that stopped existing when the repo moved out of the home
# directory and var/ became a sibling of src/. It did not fail loudly:
# sqlite3 simply created a new empty primary.db next to the source and
# every pupil and leaver read came back empty, while the real data sat
# untouched in var/data/primary/. Every other primary module already
# reads paths.PRIMARY_*; this one was the last holdout.
DB_PATH = paths.PRIMARY_PUPILS_DB
_DATA_DIR = DB_PATH.parent

ID_PREFIX = "P"
ID_DIGITS = 7
YEAR_GROUPS = ("R", "1", "2", "3", "4", "5", "6")
EMAIL_DOMAIN = "primaryschool.local"

_PHONE_RE = re.compile(r"^[0-9 +()\-]{6,20}$")
_DOB_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Where a pupil stands on the school roll. ``applicant`` is a place held for
# a child arriving through a cross-system transfer who has not started;
# ``left`` is a pupil who has moved on — kept, never deleted, so the
# school's own history and statutory returns stay intact.
ON_ROLL = "on_roll"
ROLL_STATUSES = ("applicant", ON_ROLL, "left")


@dataclass
class Pupil:
    pupil_id: str
    first_name: str
    last_name: str
    year_group: str
    class_name: str | None
    date_of_birth: str | None
    email: str
    parent_name: str | None
    parent_phone: str | None
    medical_notes: str | None
    send_status: str | None
    roll_status: str = ON_ROLL
    journey_id: str | None = None
    left_date: str | None = None
    exit_reason: str | None = None

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


_SCHEMA = """
CREATE TABLE IF NOT EXISTS pupils (
    pupil_id        TEXT PRIMARY KEY,
    first_name      TEXT NOT NULL,
    last_name       TEXT NOT NULL,
    year_group      TEXT NOT NULL,
    class_name      TEXT,
    date_of_birth   TEXT,
    email           TEXT NOT NULL UNIQUE,
    parent_name     TEXT,
    parent_phone    TEXT,
    medical_notes   TEXT,
    send_status     TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    roll_status     TEXT NOT NULL DEFAULT 'on_roll',
    journey_id      TEXT,
    left_date       TEXT,
    exit_reason     TEXT
);
"""

# Columns added after the table first shipped; existing databases gain them
# on the next init_db().
_ADDED_COLUMNS = (
    ("roll_status", "TEXT NOT NULL DEFAULT 'on_roll'"),
    ("journey_id", "TEXT"),
    ("left_date", "TEXT"),
    ("exit_reason", "TEXT"),
)


def _migrate(conn: sqlite3.Connection) -> None:
    have = {row[1] for row in conn.execute("PRAGMA table_info(pupils)")}
    for name, decl in _ADDED_COLUMNS:
        if name not in have:
            conn.execute(f"ALTER TABLE pupils ADD COLUMN {name} {decl}")  # nosec B608 - constant
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_primary_pupils_journey "
        "ON pupils(journey_id) WHERE journey_id IS NOT NULL")


class ValidationError(ValueError):
    """Raised for invalid pupil-form input."""


def _connect() -> sqlite3.Connection:
    os.makedirs(_DATA_DIR, exist_ok=True)
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
            _migrate(conn)
    except sqlite3.Error:
        logger.exception("Failed to initialise primary pupils DB at %s", DB_PATH)
        raise
    logger.info("Primary pupils DB ready at %s", DB_PATH)
    _DB_READY = True


def _row(r: sqlite3.Row) -> Pupil:
    keys = r.keys()
    return Pupil(
        pupil_id=r["pupil_id"],
        first_name=r["first_name"],
        last_name=r["last_name"],
        year_group=r["year_group"],
        class_name=r["class_name"],
        date_of_birth=r["date_of_birth"],
        email=r["email"],
        parent_name=r["parent_name"],
        parent_phone=r["parent_phone"],
        medical_notes=r["medical_notes"],
        send_status=r["send_status"],
        roll_status=(r["roll_status"] if "roll_status" in keys else None) or ON_ROLL,
        journey_id=r["journey_id"] if "journey_id" in keys else None,
        left_date=r["left_date"] if "left_date" in keys else None,
        exit_reason=r["exit_reason"] if "exit_reason" in keys else None,
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
    out["class_name"] = (data.get("class_name") or "").strip() or None
    dob = (data.get("date_of_birth") or "").strip()
    if dob and not _DOB_RE.match(dob):
        raise ValidationError("Date of birth must be YYYY-MM-DD")
    out["date_of_birth"] = dob or None
    out["parent_name"] = (data.get("parent_name") or "").strip() or None
    pphone = (data.get("parent_phone") or "").strip()
    if pphone and not _PHONE_RE.match(pphone):
        raise ValidationError("Parent phone contains invalid characters")
    out["parent_phone"] = pphone or None
    out["medical_notes"] = (data.get("medical_notes") or "").strip() or None
    send = (data.get("send_status") or "").strip()
    if send and send.lower() not in ("yes", "no"):
        raise ValidationError("SEND status must be 'yes' or 'no'")
    out["send_status"] = send.lower() if send else None
    return out


def create_pupil(data: dict[str, Any], *, roll_status: str = ON_ROLL,
                 journey_id: str | None = None) -> Pupil:
    """Create a pupil. ``roll_status='applicant'`` holds a place for a child
    arriving through a cross-system transfer; ``journey_id`` stamps the
    canonical journey so a redelivered transfer finds this row."""
    init_db()
    logger.debug("create_pupil called with fields: %s",
                 sorted(k for k, v in data.items() if v not in (None, "")))
    if roll_status not in ROLL_STATUSES:
        raise ValidationError(
            f"Roll status must be one of {', '.join(ROLL_STATUSES)}")
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
                    pupil_id, first_name, last_name, year_group, class_name,
                    date_of_birth, email, parent_name, parent_phone,
                    medical_notes, send_status, roll_status, journey_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (pid, payload["first_name"], payload["last_name"],
                 payload["year_group"], payload["class_name"],
                 payload["date_of_birth"], email, payload["parent_name"],
                 payload["parent_phone"], payload["medical_notes"],
                 payload["send_status"], roll_status, journey_id),
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
    # in the nursery/secondary systems (best-effort; matched on name+DOB).
    try:
        from education_system.platform.cross_system import person, progression
        jid = progression.register_local_student(
            "primary", student_id=pupil.pupil_id,
            first_name=pupil.first_name, last_name=pupil.last_name,
            date_of_birth=pupil.date_of_birth)
        if jid:
            person.link_local_record("primary", pupil.pupil_id, jid)
    except Exception:
        logger.debug("Journey registration skipped for pupil %s",
                     pupil.pupil_id, exc_info=True)
    # A login named after this pupil (made before the pupil record) is
    # linked now that the journey exists. Best-effort, never raises.
    from education_system.platform.cross_system import login_links
    for name in (pupil.pupil_id, getattr(pupil, "email", None)):
        login_links.try_sync_username(name)
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


def find_by_journey(journey_id: str) -> Pupil | None:
    """The pupil stamped with a canonical journey, whatever their roll status."""
    if not journey_id:
        return None
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM pupils WHERE journey_id = ?", (journey_id,)
        ).fetchone()
    return _row(row) if row is not None else None


def set_roll_status(pupil_id: str, roll_status: str, *,
                    left_date: str | None = None,
                    exit_reason: str | None = None) -> Pupil:
    """Move a pupil on or off roll. Never deletes the row."""
    if roll_status not in ROLL_STATUSES:
        raise ValidationError(
            f"Roll status must be one of {', '.join(ROLL_STATUSES)}")
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE pupils SET roll_status = ?, left_date = ?, exit_reason = ? "
            "WHERE pupil_id = ?",
            (roll_status, left_date if roll_status == "left" else None,
             exit_reason if roll_status == "left" else None, pupil_id))
        if cur.rowcount == 0:
            raise ValidationError(f"No pupil with id {pupil_id}")
        conn.commit()
    pupil = get_pupil(pupil_id)
    assert pupil is not None
    logger.info("Pupil %s roll status -> %s", pupil_id, roll_status)
    return pupil


def list_pupils(*, include_off_roll: bool = False) -> list[Pupil]:
    """Pupils on roll. ``include_off_roll`` adds applicants and leavers."""
    init_db()
    where = "" if include_off_roll else "WHERE roll_status = 'on_roll' "
    try:
        with _connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM pupils {where}"  # nosec B608 - constant fragment
                "ORDER BY year_group, last_name, first_name"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("list_pupils failed")
        raise
    logger.debug("list_pupils -> %d row(s)", len(rows))
    return [_row(r) for r in rows]


def search_pupils(query: str, *, include_off_roll: bool = False) -> list[Pupil]:
    init_db()
    raw = (query or "").strip()
    q = f"%{raw}%"
    roll = "" if include_off_roll else "AND roll_status = 'on_roll' "
    try:
        with _connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM pupils
                WHERE (pupil_id LIKE ?
                   OR first_name LIKE ?
                   OR last_name LIKE ?
                   OR email LIKE ?
                   OR class_name LIKE ?)
                {roll}
                ORDER BY year_group, last_name, first_name
                """,  # nosec B608 - constant fragment
                (q, q, q, q, q),
            ).fetchall()
    except sqlite3.Error:
        logger.exception("search_pupils(query_len=%d) failed", len(raw))
        raise
    logger.debug("search_pupils(query_len=%d) -> %d match(es)", len(raw), len(rows))
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
                    first_name = ?, last_name = ?, year_group = ?, class_name = ?,
                    date_of_birth = ?, parent_name = ?, parent_phone = ?,
                    medical_notes = ?, send_status = ?
                WHERE pupil_id = ?
                """,
                (payload["first_name"], payload["last_name"],
                 payload["year_group"], payload["class_name"],
                 payload["date_of_birth"], payload["parent_name"],
                 payload["parent_phone"], payload["medical_notes"],
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
