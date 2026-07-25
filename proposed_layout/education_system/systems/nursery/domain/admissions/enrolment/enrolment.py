"""Domain layer for Registration & Enrolment (Nursery System).

Owns the ``enrolments`` table of the shared nursery DB
(``nursery_system/data/nursery.db`` — see ``core/database.py``). An enrolment
is the formal registration record created when a child joins the roll: the
contracted room / funded hours / weekly sessions, the registration date, the
statutory EYFS consents (photo, outings, emergency medical treatment, sun
cream) and an emergency contact. Each row points at a ``pupils`` record and,
optionally, the ``admissions`` application it was converted from.

This module is the join between the three flows:

* :func:`enrol_child` creates a brand-new child + enrolment in one step.
* :func:`enrol_from_application` converts an accepted admission — it creates the
  child, the enrolment, and flips the admission to ``enrolled``.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``enrolment_cli.py``, Tk GUI in ``enrolment_views.py``.
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

FEATURE_NAME = "Registration & Enrolment"
CATEGORY = "Children & Admissions"

ID_PREFIX = "NEN"
ID_DIGITS = 3

STATUSES = ("enrolled", "withdrawn", "completed")

# Consent flags captured at registration, in display order.
CONSENT_FIELDS = (
    ("photo_consent", "Photo / media consent"),
    ("outings_consent", "Local outings consent"),
    ("medical_consent", "Emergency medical treatment consent"),
    ("suncream_consent", "Sun cream application consent"),
)

_PHONE_RE = re.compile(r"^[0-9 +()\-]{6,20}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid enrolment-form input."""


@dataclass
class Enrolment:
    enrolment_id: str
    pupil_id: str
    application_id: str | None
    room: str | None
    start_date: str | None
    funded_hours: str | None
    weekly_sessions: str | None
    registration_date: str | None
    contract_signed: bool
    photo_consent: bool
    outings_consent: bool
    medical_consent: bool
    suncream_consent: bool
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    notes: str | None
    status: str
    # Joined from ``pupils`` for display; not stored on the enrolment row.
    child_name: str | None = None


def _ensure_schema() -> None:
    """Create (and demo-seed) the nursery tables if needed. Idempotent."""
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for enrolment")
        raise


def _row(r: sqlite3.Row) -> Enrolment:
    keys = r.keys()
    return Enrolment(
        enrolment_id=r["enrolment_id"],
        pupil_id=r["pupil_id"],
        application_id=r["application_id"],
        room=r["room"],
        start_date=r["start_date"],
        funded_hours=r["funded_hours"],
        weekly_sessions=r["weekly_sessions"],
        registration_date=r["registration_date"],
        contract_signed=bool(r["contract_signed"]),
        photo_consent=bool(r["photo_consent"]),
        outings_consent=bool(r["outings_consent"]),
        medical_consent=bool(r["medical_consent"]),
        suncream_consent=bool(r["suncream_consent"]),
        emergency_contact_name=r["emergency_contact_name"],
        emergency_contact_phone=r["emergency_contact_phone"],
        notes=r["notes"],
        status=r["status"],
        child_name=r["child_name"] if "child_name" in keys else None,
    )


_SELECT = """
SELECT e.*,
       TRIM(COALESCE(p.first_name, '') || ' ' || COALESCE(p.last_name, ''))
           AS child_name
FROM enrolments e
LEFT JOIN pupils p ON p.pupil_id = e.pupil_id
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


def _as_bool(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    s = str(value or "").strip().lower()
    return int(s in ("1", "y", "yes", "true", "on"))


def _validate(data: dict[str, Any], *, require_pupil: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_pupil:
        out["pupil_id"] = _require(data.get("pupil_id"), "Pupil ID")
    out["application_id"] = _opt(data.get("application_id"))
    out["room"] = _opt(data.get("room"))
    out["start_date"] = _opt_date(data.get("start_date"), "Start date")
    out["funded_hours"] = _opt(data.get("funded_hours"))
    out["weekly_sessions"] = _opt(data.get("weekly_sessions"))
    out["registration_date"] = _opt_date(
        data.get("registration_date"), "Registration date")
    out["contract_signed"] = _as_bool(data.get("contract_signed"))
    out["photo_consent"] = _as_bool(data.get("photo_consent"))
    out["outings_consent"] = _as_bool(data.get("outings_consent"))
    out["medical_consent"] = _as_bool(data.get("medical_consent"))
    out["suncream_consent"] = _as_bool(data.get("suncream_consent"))
    out["emergency_contact_name"] = _opt(data.get("emergency_contact_name"))

    ephone = (data.get("emergency_contact_phone") or "").strip()
    if ephone and not _PHONE_RE.match(ephone):
        raise ValidationError("Emergency contact phone contains invalid characters")
    out["emergency_contact_phone"] = ephone or None

    out["notes"] = _opt(data.get("notes"))

    status = (data.get("status") or "enrolled").strip().lower()
    if status not in STATUSES:
        raise ValidationError(f"Status must be one of {', '.join(STATUSES)}")
    out["status"] = status
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_enrolment_id() -> str:
    """Allocate a unique ``NEN###`` id, widening past the demo range if full."""
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {
                r[0] for r in conn.execute(
                    "SELECT enrolment_id FROM enrolments").fetchall()
            }
    except sqlite3.Error:
        logger.exception("Could not read existing enrolment ids")
        raise

    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"

    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        eid = f"{ID_PREFIX}{n}"
        if eid not in existing:
            return eid
    raise RuntimeError("Could not allocate a unique enrolment id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_enrolments(*, include_withdrawn: bool = True) -> list[Enrolment]:
    _ensure_schema()
    sql = _SELECT
    params: tuple[Any, ...] = ()
    if not include_withdrawn:
        sql += " WHERE e.status = ?"
        params = ("enrolled",)
    sql += " ORDER BY e.start_date DESC, e.enrolment_id DESC"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_enrolments failed")
        raise
    return [_row(r) for r in rows]


def get_enrolment(enrolment_id: str) -> Enrolment | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE e.enrolment_id = ?", (enrolment_id,)
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_enrolment(%s) failed", enrolment_id)
        raise
    return _row(row) if row else None


def get_by_pupil(pupil_id: str) -> Enrolment | None:
    """Return the most recent enrolment for a child, if any."""
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE e.pupil_id = ? "
                "ORDER BY e.start_date DESC, e.enrolment_id DESC LIMIT 1",
                (pupil_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_by_pupil(%s) failed", pupil_id)
        raise
    return _row(row) if row else None


def search_enrolments(query: str) -> list[Enrolment]:
    _ensure_schema()
    like = f"%{(query or '').strip()}%"
    sql = _SELECT + """
        WHERE (e.enrolment_id LIKE ?
            OR e.pupil_id LIKE ?
            OR p.first_name LIKE ?
            OR p.last_name LIKE ?
            OR e.room LIKE ?)
        ORDER BY e.start_date DESC, e.enrolment_id DESC
    """
    params = [like] * 5
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("search_enrolments failed")
        raise
    return [_row(r) for r in rows]


# ── Writes ───────────────────────────────────────────────────────────────────

def _pupil_exists(conn: sqlite3.Connection, pupil_id: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM pupils WHERE pupil_id = ?", (pupil_id,)
    ).fetchone() is not None


def create_enrolment(data: dict[str, Any]) -> Enrolment:
    """Create an enrolment for an existing child (``pupil_id`` required)."""
    _ensure_schema()
    payload = _validate(data, require_pupil=True)
    eid = generate_enrolment_id()
    try:
        with connect() as conn:
            if not _pupil_exists(conn, payload["pupil_id"]):
                raise ValidationError(
                    f"No child on roll with id {payload['pupil_id']}")
            conn.execute(
                """
                INSERT INTO enrolments (
                    enrolment_id, pupil_id, application_id, room, start_date,
                    funded_hours, weekly_sessions, registration_date,
                    contract_signed, photo_consent, outings_consent,
                    medical_consent, suncream_consent, emergency_contact_name,
                    emergency_contact_phone, notes, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (eid, payload["pupil_id"], payload["application_id"],
                 payload["room"], payload["start_date"], payload["funded_hours"],
                 payload["weekly_sessions"], payload["registration_date"],
                 payload["contract_signed"], payload["photo_consent"],
                 payload["outings_consent"], payload["medical_consent"],
                 payload["suncream_consent"], payload["emergency_contact_name"],
                 payload["emergency_contact_phone"], payload["notes"],
                 payload["status"]),
            )
            conn.commit()
    except sqlite3.IntegrityError as e:
        logger.exception("INSERT failed for new enrolment id=%s", eid)
        raise ValidationError(f"Could not create enrolment — {e}") from e
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("Database error creating enrolment id=%s", eid)
        raise
    enr = get_enrolment(eid)
    assert enr is not None
    logger.info("Created enrolment %s for pupil %s", eid, payload["pupil_id"])
    return enr


def enrol_child(child_data: dict[str, Any],
                enrolment_data: dict[str, Any]) -> Enrolment:
    """Register a brand-new child: create the ``pupils`` record then enrol it.

    ``child_data`` is passed to the Child Directory (it allocates the child id);
    ``enrolment_data`` supplies the registration / consent details.
    """
    _ensure_schema()
    from education_system.systems.nursery.domain.learners.children import children
    child = children.create_child(child_data)
    merged = dict(enrolment_data)
    merged["pupil_id"] = child.pupil_id
    # Carry across room / funded hours from the child record if not overridden.
    merged.setdefault("room", child.room or "")
    merged.setdefault("funded_hours", child.funded_hours or "")
    merged.setdefault("start_date", child.start_date or "")
    try:
        return create_enrolment(merged)
    except Exception:
        # Roll back the orphaned child record so a failed registration doesn't
        # leave a half-created pupil on the roll.
        logger.exception("Enrolment failed after creating child %s — rolling back",
                         child.pupil_id)
        try:
            children.delete_child(child.pupil_id)
        except Exception:
            logger.exception("Could not roll back child %s", child.pupil_id)
        raise


def enrol_from_application(application_id: str,
                           overrides: dict[str, Any] | None = None) -> Enrolment:
    """Convert an accepted admission into an on-roll child + enrolment.

    Creates the child from the application's details, creates the enrolment,
    and flips the admission to ``enrolled`` (linking it to the new child).
    ``overrides`` may supply / override any child or enrolment field.
    """
    _ensure_schema()
    from education_system.systems.nursery.domain.admissions import admissions
    app = admissions.get_application(application_id)
    if app is None:
        raise ValidationError(f"No application with id {application_id}")
    if app.pupil_id:
        raise ValidationError(
            f"Application {application_id} is already enrolled as {app.pupil_id}")

    overrides = overrides or {}
    child_data = {
        "first_name": overrides.get("first_name", app.child_first_name),
        "last_name": overrides.get("last_name", app.child_last_name),
        "date_of_birth": overrides.get("date_of_birth", app.date_of_birth or ""),
        "room": overrides.get("room", app.requested_room or ""),
        "funded_hours": overrides.get("funded_hours", app.funded_hours or ""),
        "start_date": overrides.get("start_date", app.requested_start or ""),
        "parent_name": overrides.get("parent_name", app.parent_name or ""),
        "parent_phone": overrides.get("parent_phone", app.parent_phone or ""),
        "parent_email": overrides.get("parent_email", app.parent_email or ""),
    }
    enrolment_data = {
        "application_id": application_id,
        "room": overrides.get("room", app.requested_room or ""),
        "start_date": overrides.get("start_date", app.requested_start or ""),
        "funded_hours": overrides.get("funded_hours", app.funded_hours or ""),
        "weekly_sessions": overrides.get("weekly_sessions", app.days_required or ""),
        "registration_date": overrides.get("registration_date", ""),
        "contract_signed": overrides.get("contract_signed", 0),
        "photo_consent": overrides.get("photo_consent", 0),
        "outings_consent": overrides.get("outings_consent", 0),
        "medical_consent": overrides.get("medical_consent", 0),
        "suncream_consent": overrides.get("suncream_consent", 0),
        "emergency_contact_name": overrides.get("emergency_contact_name", ""),
        "emergency_contact_phone": overrides.get("emergency_contact_phone", ""),
        "notes": overrides.get("notes", ""),
    }
    enr = enrol_child(child_data, enrolment_data)
    try:
        admissions.mark_enrolled(application_id, enr.pupil_id)
    except Exception:
        logger.exception(
            "Enrolment %s created but could not flag admission %s as enrolled",
            enr.enrolment_id, application_id)
    logger.info("Enrolled application %s -> child %s (enrolment %s)",
                application_id, enr.pupil_id, enr.enrolment_id)
    return enr


def update_enrolment(enrolment_id: str, data: dict[str, Any]) -> Enrolment:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE enrolments SET
                    application_id = ?, room = ?, start_date = ?,
                    funded_hours = ?, weekly_sessions = ?, registration_date = ?,
                    contract_signed = ?, photo_consent = ?, outings_consent = ?,
                    medical_consent = ?, suncream_consent = ?,
                    emergency_contact_name = ?, emergency_contact_phone = ?,
                    notes = ?, status = ?
                WHERE enrolment_id = ?
                """,
                (payload["application_id"], payload["room"], payload["start_date"],
                 payload["funded_hours"], payload["weekly_sessions"],
                 payload["registration_date"], payload["contract_signed"],
                 payload["photo_consent"], payload["outings_consent"],
                 payload["medical_consent"], payload["suncream_consent"],
                 payload["emergency_contact_name"],
                 payload["emergency_contact_phone"], payload["notes"],
                 payload["status"], enrolment_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No enrolment with id {enrolment_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for enrolment id=%s", enrolment_id)
        raise ValidationError(f"Could not update enrolment — {e}") from e
    enr = get_enrolment(enrolment_id)
    assert enr is not None
    logger.info("Updated enrolment %s", enrolment_id)
    return enr


def delete_enrolment(enrolment_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM enrolments WHERE enrolment_id = ?", (enrolment_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting enrolment id=%s", enrolment_id)
        raise
    if deleted:
        logger.info("Deleted enrolment %s", enrolment_id)
    return deleted


def withdraw(enrolment_id: str, *, take_off_roll: bool = True) -> Enrolment:
    """Mark an enrolment withdrawn; optionally set the child's status to 'left'."""
    _ensure_schema()
    enr = get_enrolment(enrolment_id)
    if enr is None:
        raise ValidationError(f"No enrolment with id {enrolment_id}")
    try:
        with connect() as conn:
            conn.execute(
                "UPDATE enrolments SET status = 'withdrawn' WHERE enrolment_id = ?",
                (enrolment_id,))
            if take_off_roll:
                conn.execute(
                    "UPDATE pupils SET status = 'left' WHERE pupil_id = ?",
                    (enr.pupil_id,))
            conn.commit()
    except sqlite3.Error:
        logger.exception("Database error withdrawing enrolment id=%s", enrolment_id)
        raise
    updated = get_enrolment(enrolment_id)
    assert updated is not None
    logger.info("Withdrew enrolment %s (take_off_roll=%s)",
                enrolment_id, take_off_roll)
    return updated
