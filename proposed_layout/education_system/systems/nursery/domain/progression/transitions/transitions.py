"""Domain layer for Transition to School (Nursery System).

Owns the ``transitions`` table — a child's move on to primary school
(Reception). Tracks the destination school, the expected start date, whether
the transition report has been sent to the receiving school and the transition
activities completed (visits, transition days, reception-teacher visit), with a
simple planned → in_progress → completed workflow.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``transitions_cli.py``, Tk GUI in ``transitions_views.py``.
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

FEATURE_NAME = "Transition to School"
CATEGORY = "Children & Admissions"

ID_PREFIX = "NTR"
ID_DIGITS = 3

STATUSES = ("planned", "in_progress", "completed")

# JSON email template (data/templates/email/<name>.json) sent to both the
# nursery admin and the receiving primary school when a child moves on.
TRANSFER_TEMPLATE = "nursery_to_primary_transfer"
DEFAULT_NURSERY_NAME = "Our Nursery"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid transition input."""


@dataclass
class Transition:
    transition_id: str
    pupil_id: str
    destination_school: str | None
    expected_start: str | None
    transition_report_sent: bool
    report_sent_date: str | None
    teacher_visit: bool
    activities: str | None
    status: str
    notes: str | None
    child_name: str | None = None
    room: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for transitions")
        raise


_SELECT = """
SELECT t.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       p.room AS room
FROM transitions t
LEFT JOIN pupils p ON p.pupil_id = t.pupil_id
"""


def _row(r: sqlite3.Row) -> Transition:
    keys = r.keys()
    return Transition(
        transition_id=r["transition_id"],
        pupil_id=r["pupil_id"],
        destination_school=r["destination_school"],
        expected_start=r["expected_start"],
        transition_report_sent=bool(r["transition_report_sent"]),
        report_sent_date=r["report_sent_date"],
        teacher_visit=bool(r["teacher_visit"]),
        activities=r["activities"],
        status=r["status"],
        notes=r["notes"],
        child_name=r["child_name"] if "child_name" in keys else None,
        room=r["room"] if "room" in keys else None,
    )


# ── Validation ───────────────────────────────────────────────────────────────

def _opt(value: str | None) -> str | None:
    v = (value or "").strip()
    return v or None


def _opt_date(value: str | None, label: str) -> str | None:
    v = (value or "").strip()
    if v and not _DATE_RE.match(v):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return v or None


def _as_bool(value: Any) -> int:
    if isinstance(value, (bool, int)):
        return int(bool(value))
    return int(str(value or "").strip().lower() in ("1", "y", "yes", "true", "on"))


def _validate(data: dict[str, Any], *, require_pupil: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_pupil:
        pid = (data.get("pupil_id") or "").strip()
        if not pid:
            raise ValidationError("Child (pupil ID) is required")
        out["pupil_id"] = pid

    out["destination_school"] = _opt(data.get("destination_school"))
    out["expected_start"] = _opt_date(data.get("expected_start"), "Expected start")
    out["transition_report_sent"] = _as_bool(data.get("transition_report_sent"))
    out["report_sent_date"] = _opt_date(data.get("report_sent_date"),
                                        "Report sent date")
    out["teacher_visit"] = _as_bool(data.get("teacher_visit"))
    out["activities"] = _opt(data.get("activities"))
    out["notes"] = _opt(data.get("notes"))

    status = (data.get("status") or "planned").strip().lower()
    if status not in STATUSES:
        raise ValidationError(f"Status must be one of {', '.join(STATUSES)}")
    out["status"] = status
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_transition_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT transition_id FROM transitions").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing transition ids")
        raise
    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"
    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        tid = f"{ID_PREFIX}{n}"
        if tid not in existing:
            return tid
    raise RuntimeError("Could not allocate a unique transition id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_transitions(*, statuses: tuple[str, ...] | None = None) -> list[Transition]:
    _ensure_schema()
    sql = _SELECT
    params: list[Any] = []
    if statuses:
        sql += " WHERE t.status IN (%s)" % ", ".join("?" for _ in statuses)
        params.extend(statuses)
    sql += " ORDER BY t.expected_start, child_name"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_transitions failed")
        raise
    return [_row(r) for r in rows]


def get_transition(transition_id: str) -> Transition | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE t.transition_id = ?", (transition_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_transition(%s) failed", transition_id)
        raise
    return _row(row) if row else None


def list_pupil_choices() -> list[tuple[str, str]]:
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT pupil_id, first_name, last_name, room FROM pupils "
                "WHERE status = 'active' ORDER BY last_name, first_name").fetchall()
    except sqlite3.Error:
        logger.exception("list_pupil_choices failed")
        raise
    out = []
    for r in rows:
        room = f" — {r['room']}" if r["room"] else ""
        out.append((r["pupil_id"],
                    f"{r['first_name']} {r['last_name']} ({r['pupil_id']}){room}"))
    return out


def counts_by_status() -> dict[str, int]:
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS n FROM transitions GROUP BY status"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("counts_by_status failed")
        raise
    return {r["status"]: r["n"] for r in rows}


# ── Writes ───────────────────────────────────────────────────────────────────

def create_transition(data: dict[str, Any]) -> Transition:
    _ensure_schema()
    payload = _validate(data, require_pupil=True)
    tid = generate_transition_id()
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM pupils WHERE pupil_id = ?",
                                (payload["pupil_id"],)).fetchone():
                raise ValidationError(
                    f"No child on roll with id {payload['pupil_id']}")
            conn.execute(
                """
                INSERT INTO transitions (
                    transition_id, pupil_id, destination_school, expected_start,
                    transition_report_sent, report_sent_date, teacher_visit,
                    activities, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (tid, payload["pupil_id"], payload["destination_school"],
                 payload["expected_start"], payload["transition_report_sent"],
                 payload["report_sent_date"], payload["teacher_visit"],
                 payload["activities"], payload["status"], payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for transition id=%s", tid)
        raise ValidationError(f"Could not create transition — {e}") from e
    t = get_transition(tid)
    assert t is not None
    logger.info("Created transition %s for pupil %s", tid, payload["pupil_id"])
    return t


def update_transition(transition_id: str, data: dict[str, Any]) -> Transition:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE transitions SET
                    destination_school = ?, expected_start = ?,
                    transition_report_sent = ?, report_sent_date = ?,
                    teacher_visit = ?, activities = ?, status = ?, notes = ?
                WHERE transition_id = ?
                """,
                (payload["destination_school"], payload["expected_start"],
                 payload["transition_report_sent"], payload["report_sent_date"],
                 payload["teacher_visit"], payload["activities"],
                 payload["status"], payload["notes"], transition_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No transition with id {transition_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for transition id=%s", transition_id)
        raise ValidationError(f"Could not update transition — {e}") from e
    t = get_transition(transition_id)
    assert t is not None
    logger.info("Updated transition %s", transition_id)
    return t


def delete_transition(transition_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM transitions WHERE transition_id = ?", (transition_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting transition id=%s", transition_id)
        raise
    if deleted:
        logger.info("Deleted transition %s", transition_id)
    return deleted


def set_status(transition_id: str, status: str) -> Transition:
    _ensure_schema()
    status = (status or "").strip().lower()
    if status not in STATUSES:
        raise ValidationError(f"Status must be one of {', '.join(STATUSES)}")
    try:
        with connect() as conn:
            cur = conn.execute(
                "UPDATE transitions SET status = ? WHERE transition_id = ?",
                (status, transition_id))
            if cur.rowcount == 0:
                raise ValidationError(f"No transition with id {transition_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("Database error setting status for %s", transition_id)
        raise
    t = get_transition(transition_id)
    assert t is not None
    return t


# ── Transfer notifications ─────────────────────────────────────────────────────

def _pupil_details(pupil_id: str) -> dict[str, Any]:
    """Fetch the receiving-school-relevant fields for a child, for the email."""
    try:
        with connect() as conn:
            row = conn.execute(
                """
                SELECT p.date_of_birth, p.parent_name, p.parent_email,
                       TRIM(COALESCE(s.first_name, '') || ' '
                            || COALESCE(s.last_name, '')) AS key_person_name
                FROM pupils p
                LEFT JOIN staff s ON s.staff_id = p.key_person
                WHERE p.pupil_id = ?
                """,
                (pupil_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("_pupil_details(%s) failed", pupil_id)
        raise
    if row is None:
        return {}
    return {
        "date_of_birth": row["date_of_birth"],
        "parent_name": row["parent_name"],
        "parent_email": row["parent_email"],
        "key_person_name": (row["key_person_name"] or None),
    }


def transfer_context(t: Transition, *, nursery_name: str | None = None,
                     sender_name: str | None = None) -> dict[str, Any]:
    """Build the ``{{placeholder}}`` context for the transfer email.

    Pulls the child's DOB, key person and parent/carer details from the pupil
    record and merges them with the transition's own fields. Missing values are
    rendered as ``"-"`` so the email reads cleanly rather than leaving raw
    ``{{tokens}}`` behind.
    """
    details = _pupil_details(t.pupil_id)

    def _v(value: Any) -> str:
        s = "" if value is None else str(value).strip()
        return s or "-"

    return {
        "child_name": _v(t.child_name),
        "pupil_id": _v(t.pupil_id),
        "date_of_birth": _v(details.get("date_of_birth")),
        "room": _v(t.room),
        "key_person_name": _v(details.get("key_person_name")),
        "destination_school": _v(t.destination_school),
        "start_date": _v(t.expected_start),
        "parent_name": _v(details.get("parent_name")),
        "parent_email": _v(details.get("parent_email")),
        "report_sent": "Yes" if t.transition_report_sent else "No",
        "report_sent_date": _v(t.report_sent_date),
        "teacher_visit": "Yes" if t.teacher_visit else "No",
        "activities": _v(t.activities),
        "notes": _v(t.notes),
        "nursery_name": _v(nursery_name) if nursery_name else DEFAULT_NURSERY_NAME,
        "sender_name": _v(sender_name) if sender_name else "Nursery Office",
    }


def notify_transfer(
    transition_id: str,
    *,
    nursery_admin_name: str,
    nursery_admin_email: str,
    primary_school_name: str,
    primary_school_email: str,
    nursery_name: str | None = None,
    sender_name: str | None = None,
) -> list[Any]:
    """Email the transfer details to both the nursery admin and primary school.

    Renders the ``nursery_to_primary_transfer`` JSON template once per recipient
    (so each gets a personalised greeting) and logs both as outgoing messages in
    the Email centre. Returns the two created ``EmailMessage`` objects.

    Raises ``ValidationError`` if the transition is unknown or has no destination
    school recorded — you can't hand a child over to a school that isn't named.
    """
    # Imported lazily to keep this domain module free of an email dependency at
    # import time (email_templates imports the email_centre domain).
    from education_system.systems.nursery.domain.operations.communications.email_centre import (
        email_templates,
    )

    t = get_transition(transition_id)
    if t is None:
        raise ValidationError(f"No transition with id {transition_id}")
    if not t.destination_school:
        raise ValidationError(
            "Record the destination primary school before sending the transfer "
            "email.")

    context = transfer_context(t, nursery_name=nursery_name,
                               sender_name=sender_name)

    recipients = [
        (nursery_admin_name or "Nursery Admin", nursery_admin_email),
        (primary_school_name or t.destination_school, primary_school_email),
    ]

    sent: list[Any] = []
    for name, address in recipients:
        msg = email_templates.send_from_template(
            TRANSFER_TEMPLATE,
            {**context, "recipient_name": name},
            to_name=name,
            to_address=address,
            pupil_id=t.pupil_id,
        )
        sent.append(msg)

    logger.info("Sent transfer notifications for %s (pupil %s) to %s and %s",
                transition_id, t.pupil_id, nursery_admin_email,
                primary_school_email)
    return sent
