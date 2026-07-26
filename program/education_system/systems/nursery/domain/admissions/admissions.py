"""Domain layer for Admissions & Waiting List (Nursery System).

Owns the ``admissions`` table of the shared nursery DB
(``nursery_system/data/nursery.db`` — see ``core/database.py``). Each row is an
application / enquiry that moves through a small pipeline:

    waiting → offered → accepted → enrolled

with ``declined`` / ``withdrawn`` as terminal exits. The waiting list is the
set of ``waiting`` rows ordered by priority band then application date. An
accepted application is what Registration & Enrolment converts into an on-roll
child; that step stamps ``pupil_id`` and flips the status to ``enrolled``.

Follows the 4-layer pattern used across the other systems: validation +
SQLite access here, CLI in ``admissions_cli.py``, Tk GUI in
``admissions_views.py``.
"""

from __future__ import annotations

import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.nursery.infrastructure.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Admissions & Waiting List"
CATEGORY = "Children & Admissions"

ID_PREFIX = "NADM"
ID_DIGITS = 3

# Priority bands, highest first. Looked-after children and siblings of current
# attendees are the usual statutory / policy priorities for a nursery.
PRIORITIES = ("looked-after", "sibling", "staff", "catchment", "standard")
_PRIORITY_RANK = {p: i for i, p in enumerate(PRIORITIES)}

STATUSES = ("waiting", "offered", "accepted", "declined", "withdrawn", "enrolled")
# Statuses still "live" on the waiting-list pipeline (not a terminal exit).
OPEN_STATUSES = ("waiting", "offered", "accepted")

FUNDED_HOURS_OPTIONS = (
    "",
    "15 hours",
    "30 hours",
    "2-year-old funding",
    "Private (unfunded)",
)

_PHONE_RE = re.compile(r"^[0-9 +()\-]{6,20}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid application-form input."""


@dataclass
class Application:
    application_id: str
    child_first_name: str
    child_last_name: str
    date_of_birth: str | None
    parent_name: str | None
    parent_phone: str | None
    parent_email: str | None
    requested_room: str | None
    requested_start: str | None
    funded_hours: str | None
    days_required: str | None
    date_applied: str | None
    priority: str
    status: str
    offer_date: str | None
    notes: str | None
    pupil_id: str | None

    @property
    def child_name(self) -> str:
        return f"{self.child_first_name} {self.child_last_name}".strip()


def _ensure_schema() -> None:
    """Create (and demo-seed) the nursery tables if needed. Idempotent."""
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for admissions")
        raise


def _row(r: sqlite3.Row) -> Application:
    return Application(
        application_id=r["application_id"],
        child_first_name=r["child_first_name"],
        child_last_name=r["child_last_name"],
        date_of_birth=r["date_of_birth"],
        parent_name=r["parent_name"],
        parent_phone=r["parent_phone"],
        parent_email=r["parent_email"],
        requested_room=r["requested_room"],
        requested_start=r["requested_start"],
        funded_hours=r["funded_hours"],
        days_required=r["days_required"],
        date_applied=r["date_applied"],
        priority=r["priority"],
        status=r["status"],
        offer_date=r["offer_date"],
        notes=r["notes"],
        pupil_id=r["pupil_id"],
    )


_SELECT = "SELECT * FROM admissions"

# Waiting list ordering: priority band, then how long they've been waiting.
_WAITING_ORDER = """
ORDER BY CASE priority
            WHEN 'looked-after' THEN 0
            WHEN 'sibling'      THEN 1
            WHEN 'staff'        THEN 2
            WHEN 'catchment'    THEN 3
            ELSE 4
         END,
         COALESCE(date_applied, '9999-99-99'),
         application_id
"""


# ── Validation ───────────────────────────────────────────────────────────────

def _require(value: str | None, label: str) -> str:
    if not value or not str(value).strip():
        raise ValidationError(f"{label} is required")
    return str(value).strip()


def _opt(value: str | None) -> str | None:
    v = (value or "").strip()
    return v or None


def _opt_date(value: str | None, label: str) -> str | None:
    v = (value or "").strip()
    if v and not _DATE_RE.match(v):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return v or None


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["child_first_name"] = _require(data.get("child_first_name"), "Child first name")
    out["child_last_name"] = _require(data.get("child_last_name"), "Child last name")
    out["date_of_birth"] = _opt_date(data.get("date_of_birth"), "Date of birth")
    out["parent_name"] = _opt(data.get("parent_name"))

    pphone = (data.get("parent_phone") or "").strip()
    if pphone and not _PHONE_RE.match(pphone):
        raise ValidationError("Parent phone contains invalid characters")
    out["parent_phone"] = pphone or None

    pemail = (data.get("parent_email") or "").strip()
    if pemail and not _EMAIL_RE.match(pemail):
        raise ValidationError("Parent email is not a valid address")
    out["parent_email"] = pemail or None

    out["requested_room"] = _opt(data.get("requested_room"))
    out["requested_start"] = _opt_date(data.get("requested_start"), "Requested start date")

    funded = (data.get("funded_hours") or "").strip()
    if funded and funded not in FUNDED_HOURS_OPTIONS:
        raise ValidationError(
            "Funded hours must be one of: "
            + ", ".join(o for o in FUNDED_HOURS_OPTIONS if o))
    out["funded_hours"] = funded or None

    out["days_required"] = _opt(data.get("days_required"))
    out["date_applied"] = _opt_date(data.get("date_applied"), "Application date")

    priority = (data.get("priority") or "standard").strip().lower()
    if priority not in PRIORITIES:
        raise ValidationError(f"Priority must be one of {', '.join(PRIORITIES)}")
    out["priority"] = priority

    out["notes"] = _opt(data.get("notes"))
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_application_id() -> str:
    """Allocate a unique ``NADM###`` id, widening past the demo range if full."""
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {
                r[0] for r in conn.execute(
                    "SELECT application_id FROM admissions").fetchall()
            }
    except sqlite3.Error:
        logger.exception("Could not read existing application ids")
        raise

    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"

    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        aid = f"{ID_PREFIX}{n}"
        if aid not in existing:
            return aid
    raise RuntimeError("Could not allocate a unique application id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_applications(*, statuses: tuple[str, ...] | None = None) -> list[Application]:
    """List applications, optionally filtered to the given statuses."""
    _ensure_schema()
    sql = _SELECT
    params: list[Any] = []
    if statuses:
        placeholders = ", ".join("?" for _ in statuses)
        sql += f" WHERE status IN ({placeholders})"
        params.extend(statuses)
    sql += _WAITING_ORDER
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_applications failed")
        raise
    logger.debug("list_applications(statuses=%s) -> %d row(s)", statuses, len(rows))
    return [_row(r) for r in rows]


def list_waiting_list() -> list[Application]:
    """Just the live pipeline (waiting / offered / accepted), in priority order."""
    return list_applications(statuses=OPEN_STATUSES)


def get_application(application_id: str) -> Application | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE application_id = ?", (application_id,)
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_application(%s) failed", application_id)
        raise
    return _row(row) if row else None


def search_applications(query: str) -> list[Application]:
    _ensure_schema()
    like = f"%{(query or '').strip()}%"
    sql = _SELECT + """
        WHERE (application_id LIKE ?
            OR child_first_name LIKE ?
            OR child_last_name LIKE ?
            OR parent_name LIKE ?
            OR parent_email LIKE ?
            OR requested_room LIKE ?)
    """ + _WAITING_ORDER
    params = [like] * 6
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("search_applications failed")
        raise
    return [_row(r) for r in rows]


def counts_by_status() -> dict[str, int]:
    """Return a status -> count map (handy for dashboards / summaries)."""
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS n FROM admissions GROUP BY status"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("counts_by_status failed")
        raise
    return {r["status"]: r["n"] for r in rows}


# ── Writes ───────────────────────────────────────────────────────────────────

def create_application(data: dict[str, Any]) -> Application:
    _ensure_schema()
    payload = _validate(data)
    aid = generate_application_id()
    try:
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO admissions (
                    application_id, child_first_name, child_last_name,
                    date_of_birth, parent_name, parent_phone, parent_email,
                    requested_room, requested_start, funded_hours, days_required,
                    date_applied, priority, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'waiting', ?)
                """,
                (aid, payload["child_first_name"], payload["child_last_name"],
                 payload["date_of_birth"], payload["parent_name"],
                 payload["parent_phone"], payload["parent_email"],
                 payload["requested_room"], payload["requested_start"],
                 payload["funded_hours"], payload["days_required"],
                 payload["date_applied"], payload["priority"], payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        logger.exception("INSERT failed for new application id=%s", aid)
        raise ValidationError(f"Could not create application — {e}") from e
    app = get_application(aid)
    assert app is not None
    logger.info("Created application %s (%s, priority %s)",
                app.application_id, app.child_name, app.priority)
    return app


def update_application(application_id: str, data: dict[str, Any]) -> Application:
    _ensure_schema()
    payload = _validate(data)
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE admissions SET
                    child_first_name = ?, child_last_name = ?, date_of_birth = ?,
                    parent_name = ?, parent_phone = ?, parent_email = ?,
                    requested_room = ?, requested_start = ?, funded_hours = ?,
                    days_required = ?, date_applied = ?, priority = ?, notes = ?
                WHERE application_id = ?
                """,
                (payload["child_first_name"], payload["child_last_name"],
                 payload["date_of_birth"], payload["parent_name"],
                 payload["parent_phone"], payload["parent_email"],
                 payload["requested_room"], payload["requested_start"],
                 payload["funded_hours"], payload["days_required"],
                 payload["date_applied"], payload["priority"], payload["notes"],
                 application_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No application with id {application_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for application id=%s", application_id)
        raise ValidationError(f"Could not update application — {e}") from e
    app = get_application(application_id)
    assert app is not None
    logger.info("Updated application %s (%s)", application_id, app.child_name)
    return app


def delete_application(application_id: str) -> bool:
    _ensure_schema()
    snapshot = get_application(application_id)
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM admissions WHERE application_id = ?", (application_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting application id=%s", application_id)
        raise
    if deleted:
        who = snapshot.child_name if snapshot else "(no snapshot)"
        logger.info("Deleted application %s (%s)", application_id, who)
    return deleted


def set_status(application_id: str, status: str,
               *, offer_date: str | None = None,
               pupil_id: str | None = None) -> Application:
    """Move an application to ``status``, optionally stamping offer/pupil info."""
    _ensure_schema()
    status = (status or "").strip().lower()
    if status not in STATUSES:
        raise ValidationError(f"Status must be one of {', '.join(STATUSES)}")
    if offer_date is not None:
        offer_date = _opt_date(offer_date, "Offer date")
    try:
        with connect() as conn:
            if status == "offered":
                conn.execute(
                    "UPDATE admissions SET status = ?, offer_date = "
                    "COALESCE(?, offer_date) WHERE application_id = ?",
                    (status, offer_date, application_id))
            elif status == "enrolled":
                conn.execute(
                    "UPDATE admissions SET status = ?, pupil_id = "
                    "COALESCE(?, pupil_id) WHERE application_id = ?",
                    (status, pupil_id, application_id))
            else:
                conn.execute(
                    "UPDATE admissions SET status = ? WHERE application_id = ?",
                    (status, application_id))
            if conn.total_changes == 0:
                raise ValidationError(f"No application with id {application_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("Database error setting status for application id=%s",
                         application_id)
        raise
    app = get_application(application_id)
    if app is None:
        raise ValidationError(f"No application with id {application_id}")
    logger.info("Application %s status -> %s", application_id, status)
    return app


def offer_place(application_id: str, offer_date: str | None = None) -> Application:
    return set_status(application_id, "offered", offer_date=offer_date)


def accept_offer(application_id: str) -> Application:
    return set_status(application_id, "accepted")


def decline(application_id: str) -> Application:
    return set_status(application_id, "declined")


def withdraw(application_id: str) -> Application:
    return set_status(application_id, "withdrawn")


def mark_enrolled(application_id: str, pupil_id: str) -> Application:
    """Flag an application as enrolled and link it to its on-roll child.

    Called by the Registration & Enrolment flow once a child record exists.
    """
    return set_status(application_id, "enrolled", pupil_id=pupil_id)
