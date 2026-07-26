"""Admissions data layer for the Secondary School System.

Tracks applicants from first contact through to enrolment. An accepted
application can be "enrolled" — which creates a row in the ``pupils``
table and links it back to the application via ``pupil_id``.
"""

from __future__ import annotations

import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.secondary.domain.learners.pupils import pupils as pupils_data
from education_system.systems.secondary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS, _connect as _pupils_connect, _DOB_RE,
)

logger = logging.getLogger(__name__)

# Same DB file as pupils — we add a separate table so cross-table joins
# (pupil_id ↔ pupils.pupil_id) stay local.
ID_PREFIX = "A"
ID_DIGITS = 7

STATUSES = ("pending", "offered", "accepted", "rejected", "withdrawn",
            "enrolled")
_FINAL_STATUSES = {"rejected", "withdrawn", "enrolled"}

_PHONE_RE = re.compile(r"^[0-9 +()\-]{6,20}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS admissions (
    application_id    TEXT PRIMARY KEY,
    applicant_first   TEXT NOT NULL,
    applicant_last    TEXT NOT NULL,
    date_of_birth     TEXT,
    year_applying     TEXT NOT NULL,
    parent_name       TEXT,
    parent_phone      TEXT,
    parent_email      TEXT,
    application_date  TEXT DEFAULT (date('now')),
    status            TEXT NOT NULL DEFAULT 'pending',
    pupil_id          TEXT,
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now'))
);
"""


@dataclass
class Application:
    application_id: str
    applicant_first: str
    applicant_last: str
    date_of_birth: str | None
    year_applying: str
    parent_name: str | None
    parent_phone: str | None
    parent_email: str | None
    application_date: str | None
    status: str
    pupil_id: str | None
    notes: str | None

    @property
    def applicant_name(self) -> str:
        return f"{self.applicant_first} {self.applicant_last}".strip()


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise admissions table")
        raise
    logger.info("Secondary admissions table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> Application:
    return Application(
        application_id=r["application_id"],
        applicant_first=r["applicant_first"],
        applicant_last=r["applicant_last"],
        date_of_birth=r["date_of_birth"],
        year_applying=r["year_applying"],
        parent_name=r["parent_name"],
        parent_phone=r["parent_phone"],
        parent_email=r["parent_email"],
        application_date=r["application_date"],
        status=r["status"],
        pupil_id=r["pupil_id"],
        notes=r["notes"],
    )


def generate_application_id() -> str:
    init_db()
    with _connect() as conn:
        for attempt in range(50):
            n = random.randint(10 ** (ID_DIGITS - 1), 10 ** ID_DIGITS - 1)
            aid = f"{ID_PREFIX}{n}"
            if conn.execute(
                "SELECT 1 FROM admissions WHERE application_id = ?", (aid,)
            ).fetchone() is None:
                if attempt > 0:
                    logger.info("Allocated application id %s after %d collisions",
                                aid, attempt)
                return aid
    logger.error("Exhausted 50 attempts allocating application id")
    raise RuntimeError("Could not allocate a unique application id")


def _require(value: str | None, label: str) -> str:
    if not value or not str(value).strip():
        raise ValidationError(f"{label} is required")
    return str(value).strip()


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["applicant_first"] = _require(data.get("applicant_first"), "First name")
    out["applicant_last"]  = _require(data.get("applicant_last"),  "Last name")
    yg = _require(data.get("year_applying"), "Year applying for")
    if yg not in YEAR_GROUPS:
        raise ValidationError(
            f"Year applying must be one of {', '.join(YEAR_GROUPS)}")
    out["year_applying"] = yg
    dob = (data.get("date_of_birth") or "").strip()
    if dob and not _DOB_RE.match(dob):
        raise ValidationError("Date of birth must be YYYY-MM-DD")
    out["date_of_birth"] = dob or None
    out["parent_name"] = (data.get("parent_name") or "").strip() or None
    ph = (data.get("parent_phone") or "").strip()
    if ph and not _PHONE_RE.match(ph):
        raise ValidationError("Parent phone contains invalid characters")
    out["parent_phone"] = ph or None
    em = (data.get("parent_email") or "").strip()
    if em and not _EMAIL_RE.match(em):
        raise ValidationError("Parent email is not a valid address")
    out["parent_email"] = em or None
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def create_application(data: dict[str, Any]) -> Application:
    init_db()
    logger.debug("create_application called with fields: %s",
                 sorted(k for k, v in data.items() if v not in (None, "")))
    try:
        payload = _validate(data)
    except ValidationError as e:
        logger.warning("create_application validation failed: %s", e)
        raise
    aid = generate_application_id()
    try:
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO admissions (
                    application_id, applicant_first, applicant_last,
                    date_of_birth, year_applying,
                    parent_name, parent_phone, parent_email, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (aid, payload["applicant_first"], payload["applicant_last"],
                 payload["date_of_birth"], payload["year_applying"],
                 payload["parent_name"], payload["parent_phone"],
                 payload["parent_email"], payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Database error creating application %s", aid)
        raise
    app = get_application(aid)
    assert app is not None
    logger.info("Created application %s for %s (year %s)",
                aid, app.applicant_name, app.year_applying)
    return app


def get_application(application_id: str) -> Application | None:
    init_db()
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT * FROM admissions WHERE application_id = ?",
                (application_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_application(%s) failed", application_id)
        raise
    return _row(row) if row else None


def list_applications(status: str | None = None) -> list[Application]:
    init_db()
    sql = "SELECT * FROM admissions"
    params: tuple[Any, ...] = ()
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status filter must be one of {', '.join(STATUSES)}")
        sql += " WHERE status = ?"
        params = (status,)
    sql += " ORDER BY application_date DESC, applicant_last, applicant_first"
    try:
        with _connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_applications failed")
        raise
    logger.debug("list_applications(status=%s) -> %d", status, len(rows))
    return [_row(r) for r in rows]


def update_application(application_id: str,
                       data: dict[str, Any]) -> Application:
    init_db()
    logger.debug("update_application(%s) fields: %s", application_id,
                 sorted(k for k, v in data.items() if v not in (None, "")))
    payload = _validate(data)
    existing = get_application(application_id)
    if existing is None:
        raise ValidationError(f"No application with id {application_id}")
    if existing.status in _FINAL_STATUSES:
        raise ValidationError(
            f"Cannot edit an application in status '{existing.status}'")
    try:
        with _connect() as conn:
            cur = conn.execute(
                """
                UPDATE admissions SET
                    applicant_first = ?, applicant_last = ?,
                    date_of_birth = ?, year_applying = ?,
                    parent_name = ?, parent_phone = ?, parent_email = ?,
                    notes = ?
                WHERE application_id = ?
                """,
                (payload["applicant_first"], payload["applicant_last"],
                 payload["date_of_birth"], payload["year_applying"],
                 payload["parent_name"], payload["parent_phone"],
                 payload["parent_email"], payload["notes"],
                 application_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(
                    f"No application with id {application_id}")
            conn.commit()
    except sqlite3.Error:
        logger.exception("Database error updating application %s",
                         application_id)
        raise
    app = get_application(application_id)
    assert app is not None
    logger.info("Updated application %s (%s)", application_id, app.applicant_name)
    return app


def set_status(application_id: str, new_status: str) -> Application:
    init_db()
    if new_status not in STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(STATUSES)}")
    existing = get_application(application_id)
    if existing is None:
        raise ValidationError(f"No application with id {application_id}")
    if existing.status == "enrolled":
        raise ValidationError(
            "Enrolled applications cannot be re-statused (delete instead)")
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE admissions SET status = ? WHERE application_id = ?",
                (new_status, application_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Database error setting status for %s",
                         application_id)
        raise
    logger.info("Application %s: %s -> %s",
                application_id, existing.status, new_status)
    app = get_application(application_id)
    assert app is not None
    return app


def enrol_application(application_id: str) -> tuple[Application, Any]:
    """Convert an accepted application into a real pupil record.

    Returns ``(application, pupil)``. The application's status becomes
    ``enrolled`` and ``pupil_id`` is set. Idempotent: calling twice on
    the same application raises rather than creating a second pupil.
    """
    init_db()
    existing = get_application(application_id)
    if existing is None:
        raise ValidationError(f"No application with id {application_id}")
    if existing.status == "enrolled":
        raise ValidationError(
            f"Application {application_id} is already enrolled "
            f"as pupil {existing.pupil_id}")
    if existing.status != "accepted":
        raise ValidationError(
            f"Only 'accepted' applications can be enrolled "
            f"(currently '{existing.status}')")
    pupil = pupils_data.create_pupil({
        "first_name":    existing.applicant_first,
        "last_name":     existing.applicant_last,
        "year_group":    existing.year_applying,
        "form_group":    None,
        "date_of_birth": existing.date_of_birth,
        "phone":         None,
        "parent_name":   existing.parent_name,
        "parent_phone":  existing.parent_phone,
        "send_status":   None,
    })
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE admissions SET status = 'enrolled', pupil_id = ? "
                "WHERE application_id = ?",
                (pupil.pupil_id, application_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Pupil %s was created but admissions UPDATE failed for app %s — "
            "manual reconciliation required", pupil.pupil_id, application_id)
        raise
    logger.info("Enrolled application %s -> pupil %s",
                application_id, pupil.pupil_id)
    app = get_application(application_id)
    assert app is not None
    return app, pupil


def delete_application(application_id: str) -> bool:
    init_db()
    snapshot = get_application(application_id)
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM admissions WHERE application_id = ?",
                (application_id,),
            )
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting application %s",
                         application_id)
        raise
    if deleted:
        name = snapshot.applicant_name if snapshot else "(unknown)"
        logger.info("Deleted application %s (%s)", application_id, name)
    else:
        logger.warning("delete_application: no application with id %s",
                       application_id)
    return deleted


def status_counts() -> dict[str, int]:
    init_db()
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS n FROM admissions GROUP BY status"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("status_counts failed")
        raise
    counts = {s: 0 for s in STATUSES}
    for r in rows:
        counts[r["status"]] = r["n"]
    return counts
