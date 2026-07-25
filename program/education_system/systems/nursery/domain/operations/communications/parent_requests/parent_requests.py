"""Domain layer for Parent Self-Service Requests (Nursery System).

The staff side of parent self-service. Owns the ``parent_requests`` table — one
row per thing a parent submits for themselves instead of phoning the office:

* **session** — request an extra session, or cancel a contracted one,
* **absence** — report a child off sick or on holiday,
* **contact-update** — change a phone number, email or address,
* **consent** — grant or refuse a permission (photographs, outings, …).

The point of the module is ``approve``: approving a request **applies** it to
the real domain table (``session_bookings``, ``attendance_records``, ``pupils``
/ ``parent_contacts``, ``consents``) and stamps the resulting record's id into
``applied_ref``. Staff never re-key what the parent already typed, and every
change carries a decided-by / decided-at audit trail back to the submission.

``list_invoices`` and ``list_statement`` round out the read side so a portal can
show a parent their invoices and payments without a second integration.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``parent_requests_cli.py``, Tk GUI in ``parent_requests_views.py``.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.nursery.infrastructure.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Parent Self-Service Requests"
CATEGORY = "Parents & Communication"

ID_PREFIX = "NPR"
ID_DIGITS = 3

REQUEST_TYPES = ("session", "absence", "contact-update", "consent", "general")
STATUSES = ("pending", "approved", "declined", "withdrawn")

# Fields on the child's record a parent is allowed to change themselves. Names
# and dates of birth are deliberately not in here — those need evidence.
CONTACT_FIELDS = ("parent_name", "parent_phone", "parent_email")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^[0-9 +()\-]{6,20}$")


class ValidationError(ValueError):
    """Raised for invalid parent-request input."""


@dataclass
class ParentRequest:
    request_id: str
    pupil_id: str
    request_type: str
    submitted_by: str | None
    submitted_at: str
    payload: dict[str, Any]
    status: str
    decided_by: str | None
    decided_at: str | None
    decision_note: str | None
    applied_ref: str | None
    notes: str | None
    child_name: str | None = None
    decided_by_name: str | None = None

    @property
    def is_open(self) -> bool:
        return self.status == "pending"

    @property
    def summary_line(self) -> str:
        """A one-line human description of what the parent actually asked for."""
        p = self.payload
        if self.request_type == "session":
            kind = p.get("kind", "extra")
            verb = "Cancel" if kind == "cancellation" else "Book"
            return (f"{verb} {p.get('session_type', 'all-day')} on "
                    f"{p.get('session_date', '?')}")
        if self.request_type == "absence":
            return (f"Absent {p.get('absence_date', '?')} "
                    f"({p.get('status', 'absent')}) — "
                    f"{p.get('reason') or 'no reason given'}")
        if self.request_type == "contact-update":
            changes = ", ".join(f"{k} → {v}" for k, v in p.items()
                                if k in CONTACT_FIELDS)
            return changes or "Contact details update"
        if self.request_type == "consent":
            return (f"{p.get('consent_type', '?')}: "
                    f"{p.get('consent_status', 'granted')}")
        return (p.get("message") or "General enquiry")[:80]


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for parent requests")
        raise


# ── Validation helpers ───────────────────────────────────────────────────────

def _opt(value: Any) -> str | None:
    v = "" if value is None else str(value).strip()
    return v or None


def _today() -> str:
    return _dt.date.today().isoformat()


def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _check_date(value: Any, label: str, *, required: bool = True) -> str | None:
    v = _opt(value)
    if v is None:
        if required:
            raise ValidationError(f"{label} is required")
        return None
    if not _DATE_RE.match(v):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(v)
    except ValueError as e:
        raise ValidationError(f"{label} is not a real date") from e
    return v


def _loads(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        out = json.loads(raw)
    except (TypeError, ValueError):
        logger.warning("Malformed parent-request payload — treating as empty")
        return {}
    return out if isinstance(out, dict) else {}


def _row(r: sqlite3.Row) -> ParentRequest:
    keys = r.keys()
    return ParentRequest(
        request_id=r["request_id"], pupil_id=r["pupil_id"],
        request_type=r["request_type"], submitted_by=r["submitted_by"],
        submitted_at=r["submitted_at"], payload=_loads(r["payload"]),
        status=r["status"], decided_by=r["decided_by"],
        decided_at=r["decided_at"], decision_note=r["decision_note"],
        applied_ref=r["applied_ref"], notes=r["notes"],
        child_name=r["child_name"] if "child_name" in keys else None,
        decided_by_name=(
            r["decided_by_name"] if "decided_by_name" in keys else None),
    )


_SELECT = """
SELECT q.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       TRIM(st.first_name || ' ' || st.last_name) AS decided_by_name
FROM parent_requests q
LEFT JOIN pupils p ON p.pupil_id = q.pupil_id
LEFT JOIN staff st ON st.staff_id = q.decided_by
"""


def generate_request_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT request_id FROM parent_requests").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing parent-request ids")
        raise
    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"
    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        candidate = f"{ID_PREFIX}{n}"
        if candidate not in existing:
            return candidate
    raise RuntimeError("Could not allocate a unique parent-request id")


# ── Per-type payload validation ──────────────────────────────────────────────
# Each request type is checked at *submission* time, so a parent gets told what
# is wrong immediately rather than a week later when staff try to approve it.

def _validate_session_payload(p: dict[str, Any]) -> dict[str, Any]:
    from education_system.systems.nursery.domain.operations.sessions import (
        sessions as _sessions,
    )
    out: dict[str, Any] = {}
    out["session_date"] = _check_date(p.get("session_date"), "Session date")
    session_type = str(p.get("session_type") or "all-day").strip().lower()
    if session_type not in _sessions.SESSION_TYPES:
        raise ValidationError("Session must be one of: "
                              + ", ".join(_sessions.SESSION_TYPES))
    out["session_type"] = session_type
    kind = str(p.get("kind") or "extra").strip().lower()
    if kind not in _sessions.BOOKING_KINDS:
        raise ValidationError("Kind must be one of: "
                              + ", ".join(_sessions.BOOKING_KINDS))
    out["kind"] = kind
    out["room"] = _opt(p.get("room"))
    out["reason"] = _opt(p.get("reason"))
    return out


def _validate_absence_payload(p: dict[str, Any]) -> dict[str, Any]:
    from education_system.systems.nursery.domain.operations.reporting.attendance_report import (
        attendance_report as _att,
    )
    out: dict[str, Any] = {}
    out["absence_date"] = _check_date(p.get("absence_date"), "Absence date")
    status = str(p.get("status") or "absent").strip().lower()
    if status not in _att.STATUSES:
        raise ValidationError("Absence status must be one of: "
                              + ", ".join(_att.STATUSES))
    if status == "present":
        raise ValidationError("Use 'absent', 'sick' or 'holiday' to report a "
                              "child off")
    out["status"] = status
    out["session"] = str(p.get("session") or "all-day").strip().lower()
    out["reason"] = _opt(p.get("reason"))
    out["expected_return"] = _check_date(p.get("expected_return"),
                                         "Expected return", required=False)
    return out


def _validate_contact_payload(p: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field in CONTACT_FIELDS:
        value = _opt(p.get(field))
        if value is None:
            continue
        if field == "parent_email" and not _EMAIL_RE.match(value):
            raise ValidationError("Email is not a valid address")
        if field == "parent_phone" and not _PHONE_RE.match(value):
            raise ValidationError(
                "Phone must be 6–20 digits / spaces / + ( ) -")
        out[field] = value
    if not out:
        raise ValidationError(
            "Give at least one detail to change: " + ", ".join(CONTACT_FIELDS))
    contact_id = _opt(p.get("contact_id"))
    if contact_id:
        out["contact_id"] = contact_id
    return out


def _validate_consent_payload(p: dict[str, Any]) -> dict[str, Any]:
    from education_system.systems.nursery.domain.governance.consents import (
        consents as _consents,
    )
    consent_type = _opt(p.get("consent_type"))
    if not consent_type:
        raise ValidationError("Consent type is required")
    if consent_type not in _consents.CONSENT_TYPES:
        raise ValidationError("Consent type must be one of: "
                              + ", ".join(_consents.CONSENT_TYPES))
    status = str(p.get("consent_status") or "granted").strip().lower()
    if status not in ("granted", "refused"):
        raise ValidationError("Consent answer must be 'granted' or 'refused'")
    return {
        "consent_type": consent_type,
        "consent_status": status,
        "expiry_date": _check_date(p.get("expiry_date"), "Expiry date",
                                   required=False),
    }


def _validate_general_payload(p: dict[str, Any]) -> dict[str, Any]:
    message = _opt(p.get("message"))
    if not message:
        raise ValidationError("Message is required")
    return {"message": message}


_PAYLOAD_VALIDATORS = {
    "session": _validate_session_payload,
    "absence": _validate_absence_payload,
    "contact-update": _validate_contact_payload,
    "consent": _validate_consent_payload,
    "general": _validate_general_payload,
}


# ── Submission (the parent-facing write) ─────────────────────────────────────

def submit(data: dict[str, Any]) -> ParentRequest:
    """Record a request a parent has made. Validated on the way in."""
    _ensure_schema()
    pupil_id = _opt(data.get("pupil_id"))
    if not pupil_id:
        raise ValidationError("Child (pupil ID) is required")

    request_type = str(data.get("request_type") or "").strip().lower()
    if request_type not in REQUEST_TYPES:
        raise ValidationError("Request type must be one of: "
                              + ", ".join(REQUEST_TYPES))

    payload = data.get("payload")
    if not isinstance(payload, dict):
        payload = {k: v for k, v in data.items()
                   if k not in ("pupil_id", "request_type", "submitted_by",
                                "submitted_at", "notes", "payload")}
    payload = _PAYLOAD_VALIDATORS[request_type](payload)

    rid = generate_request_id()
    submitted_at = _opt(data.get("submitted_at")) or _now()
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM pupils WHERE pupil_id = ?",
                                (pupil_id,)).fetchone():
                raise ValidationError(f"No child on roll with id {pupil_id}")
            conn.execute(
                """
                INSERT INTO parent_requests (
                    request_id, pupil_id, request_type, submitted_by,
                    submitted_at, payload, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
                """,
                (rid, pupil_id, request_type, _opt(data.get("submitted_by")),
                 submitted_at, json.dumps(payload), _opt(data.get("notes"))),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for parent request %s", rid)
        raise ValidationError(f"Could not submit request — {e}") from e
    req = get_request(rid)
    assert req is not None
    logger.info("Parent request %s submitted (%s) for pupil %s",
                rid, request_type, pupil_id)
    return req


def request_session(pupil_id: str, session_date: str,
                    session_type: str = "all-day", **extra: Any) -> ParentRequest:
    return submit({"pupil_id": pupil_id, "request_type": "session",
                   "payload": {"session_date": session_date,
                               "session_type": session_type, **extra}})


def report_absence(pupil_id: str, absence_date: str,
                   status: str = "sick", **extra: Any) -> ParentRequest:
    return submit({"pupil_id": pupil_id, "request_type": "absence",
                   "payload": {"absence_date": absence_date, "status": status,
                               **extra}})


# ── Reads ────────────────────────────────────────────────────────────────────

def list_requests(*, pupil_id: str | None = None, status: str | None = None,
                  request_type: str | None = None,
                  date_from: str | None = None) -> list[ParentRequest]:
    _ensure_schema()
    clauses: list[str] = []
    params: list[Any] = []
    if pupil_id:
        clauses.append("q.pupil_id = ?")
        params.append(pupil_id)
    if status:
        clauses.append("q.status = ?")
        params.append(status)
    if request_type:
        clauses.append("q.request_type = ?")
        params.append(request_type)
    if date_from:
        clauses.append("q.submitted_at >= ?")
        params.append(date_from)
    sql = _SELECT
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    # Pending first, then newest — the inbox order staff actually want.
    sql += (" ORDER BY CASE q.status WHEN 'pending' THEN 0 ELSE 1 END, "
            "q.submitted_at DESC, q.request_id DESC")
    try:
        with connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_requests failed")
        raise
    return [_row(r) for r in rows]


def get_request(request_id: str) -> ParentRequest | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(_SELECT + " WHERE q.request_id = ?",
                               (request_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_request(%s) failed", request_id)
        raise
    return _row(row) if row else None


def pending(*, request_type: str | None = None) -> list[ParentRequest]:
    return list_requests(status="pending", request_type=request_type)


# ── Applying an approved request ─────────────────────────────────────────────
# One applier per request type. Each returns the id of the record it created or
# updated, which is stored as ``applied_ref`` so the trail is followable.

def _apply_session(req: ParentRequest) -> str:
    from education_system.systems.nursery.domain.operations.sessions import (
        sessions as _sessions,
    )
    p = req.payload
    booking = _sessions.create_booking({
        "pupil_id": req.pupil_id,
        "session_date": p["session_date"],
        "session_type": p.get("session_type", "all-day"),
        "kind": p.get("kind", "extra"),
        "room": p.get("room"),
        "reason": p.get("reason"),
        "chargeable": p.get("kind", "extra") == "extra",
        "status": "confirmed",
        "notes": f"Requested by parent ({req.request_id}).",
    })
    return booking.booking_id


def _apply_absence(req: ParentRequest) -> str:
    from education_system.systems.nursery.domain.operations.reporting.attendance_report import (
        attendance_report as _att,
    )
    p = req.payload
    reason = p.get("reason")
    if p.get("expected_return"):
        reason = f"{reason or 'Reported by parent'} (back {p['expected_return']})"
    _att.mark_attendance(
        req.pupil_id, p["absence_date"], p.get("status", "absent"),
        session=p.get("session", "all-day"), absence_reason=reason,
        notes=f"Reported by parent ({req.request_id}).")
    return f"{req.pupil_id}@{p['absence_date']}"


def _apply_contact_update(req: ParentRequest) -> str:
    p = req.payload
    fields = {k: v for k, v in p.items() if k in CONTACT_FIELDS}
    if not fields:
        raise ValidationError("Nothing to apply — no contact fields given")
    assignments = ", ".join(f"{k} = ?" for k in fields)
    try:
        with connect() as conn:
            conn.execute(
                f"UPDATE pupils SET {assignments} WHERE pupil_id = ?",  # noqa: S608
                (*fields.values(), req.pupil_id))
            # Keep the richer parent_contacts record in step where it exists.
            contact_id = p.get("contact_id")
            if contact_id:
                mapping = {"parent_name": "full_name",
                           "parent_phone": "phone", "parent_email": "email"}
                contact_fields = {mapping[k]: v for k, v in fields.items()
                                  if k in mapping}
                if contact_fields:
                    sets = ", ".join(f"{k} = ?" for k in contact_fields)
                    conn.execute(
                        f"UPDATE parent_contacts SET {sets} "  # noqa: S608
                        "WHERE contact_id = ?",
                        (*contact_fields.values(), contact_id))
            conn.commit()
    except sqlite3.Error:
        logger.exception("Could not apply contact update %s", req.request_id)
        raise
    return req.payload.get("contact_id") or req.pupil_id


def _apply_consent(req: ParentRequest) -> str:
    from education_system.systems.nursery.domain.governance.consents import (
        consents as _consents,
    )
    p = req.payload
    fields = {
        "pupil_id": req.pupil_id,
        "consent_type": p["consent_type"],
        "status": p["consent_status"],
        "date_recorded": _today(),
        "expiry_date": p.get("expiry_date"),
        "notes": f"Answered by parent ({req.request_id}).",
    }
    # Answering the same permission again updates it rather than stacking rows.
    existing = next((c for c in _consents.list_consents(pupil_id=req.pupil_id)
                     if c.consent_type == p["consent_type"]), None)
    if existing is not None:
        return _consents.update_consent(existing.consent_id, fields).consent_id
    return _consents.create_consent(fields).consent_id


def _apply_general(req: ParentRequest) -> str:
    # A general enquiry has nothing to write through; approving it just closes
    # the loop for the parent.
    return req.request_id


_APPLIERS = {
    "session": _apply_session,
    "absence": _apply_absence,
    "contact-update": _apply_contact_update,
    "consent": _apply_consent,
    "general": _apply_general,
}


def preview(request_id: str) -> str:
    """What approving this request would do, in words, without doing it."""
    req = get_request(request_id)
    if req is None:
        raise ValidationError(f"No request with id {request_id}")
    p = req.payload
    child = req.child_name or req.pupil_id
    if req.request_type == "session":
        kind = p.get("kind", "extra")
        verb = ("cancel the contracted session" if kind == "cancellation"
                else "book an extra session")
        return (f"Will {verb} for {child} on {p.get('session_date')} "
                f"({p.get('session_type')}) in the booking calendar.")
    if req.request_type == "absence":
        return (f"Will mark {child} '{p.get('status')}' on "
                f"{p.get('absence_date')} in the daily register.")
    if req.request_type == "contact-update":
        changes = "; ".join(f"{k} → {v}" for k, v in p.items()
                            if k in CONTACT_FIELDS)
        return f"Will update {child}'s record: {changes}."
    if req.request_type == "consent":
        return (f"Will record '{p.get('consent_type')}' as "
                f"{p.get('consent_status')} for {child}.")
    return "Will close the enquiry — nothing is written to another record."


def approve(request_id: str, decided_by: str | None = None,
            note: str | None = None) -> ParentRequest:
    """Approve a request **and apply it**, so staff never re-key the details.

    The write-through happens first; only if it succeeds is the request marked
    approved. A failure leaves the request pending with nothing half-applied.
    """
    _ensure_schema()
    req = get_request(request_id)
    if req is None:
        raise ValidationError(f"No request with id {request_id}")
    if req.status != "pending":
        raise ValidationError(
            f"Request {request_id} is already {req.status} — only pending "
            "requests can be approved.")

    applied_ref = _APPLIERS[req.request_type](req)

    try:
        with connect() as conn:
            conn.execute(
                "UPDATE parent_requests SET status = 'approved', "
                "decided_by = ?, decided_at = ?, decision_note = ?, "
                "applied_ref = ? WHERE request_id = ?",
                (_opt(decided_by), _now(), _opt(note), applied_ref, request_id))
            conn.commit()
    except sqlite3.Error:
        logger.exception("Could not mark parent request %s approved", request_id)
        raise
    out = get_request(request_id)
    assert out is not None
    logger.info("Approved parent request %s (%s) -> %s",
                request_id, req.request_type, applied_ref)
    return out


def decline(request_id: str, decided_by: str | None = None,
            note: str | None = None) -> ParentRequest:
    """Turn a request down. Nothing is written through."""
    _ensure_schema()
    req = get_request(request_id)
    if req is None:
        raise ValidationError(f"No request with id {request_id}")
    if req.status != "pending":
        raise ValidationError(f"Request {request_id} is already {req.status}")
    if not _opt(note):
        raise ValidationError("Give the parent a reason for declining")
    try:
        with connect() as conn:
            conn.execute(
                "UPDATE parent_requests SET status = 'declined', "
                "decided_by = ?, decided_at = ?, decision_note = ? "
                "WHERE request_id = ?",
                (_opt(decided_by), _now(), _opt(note), request_id))
            conn.commit()
    except sqlite3.Error:
        logger.exception("Could not decline parent request %s", request_id)
        raise
    out = get_request(request_id)
    assert out is not None
    logger.info("Declined parent request %s", request_id)
    return out


def withdraw(request_id: str) -> ParentRequest:
    """The parent has taken the request back."""
    _ensure_schema()
    req = get_request(request_id)
    if req is None:
        raise ValidationError(f"No request with id {request_id}")
    if req.status != "pending":
        raise ValidationError(f"Request {request_id} is already {req.status}")
    try:
        with connect() as conn:
            conn.execute(
                "UPDATE parent_requests SET status = 'withdrawn', "
                "decided_at = ? WHERE request_id = ?", (_now(), request_id))
            conn.commit()
    except sqlite3.Error:
        logger.exception("Could not withdraw parent request %s", request_id)
        raise
    out = get_request(request_id)
    assert out is not None
    return out


def delete_request(request_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM parent_requests WHERE request_id = ?",
                (request_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting parent request %s", request_id)
        raise
    if deleted:
        logger.info("Deleted parent request %s", request_id)
    return deleted


# ── Parent-facing reads (what a portal shows back) ───────────────────────────

def list_invoices(pupil_id: str) -> list[dict[str, Any]]:
    """A child's invoices, for the parent to view without asking the office."""
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT * FROM invoices WHERE pupil_id = ? "
                "ORDER BY issue_date DESC, invoice_id DESC",
                (pupil_id,)).fetchall()
    except sqlite3.Error:
        logger.exception("list_invoices(%s) failed", pupil_id)
        raise
    return [dict(r) for r in rows]


def list_payments(pupil_id: str) -> list[dict[str, Any]]:
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT * FROM payments WHERE pupil_id = ? "
                "ORDER BY payment_date DESC, payment_id DESC",
                (pupil_id,)).fetchall()
    except sqlite3.Error:
        logger.exception("list_payments(%s) failed", pupil_id)
        raise
    return [dict(r) for r in rows]


def statement(pupil_id: str) -> dict[str, Any]:
    """Invoices, payments and the resulting balance for one child."""
    invoices = list_invoices(pupil_id)
    payments = list_payments(pupil_id)
    # Draft invoices haven't been issued to the parent, so they don't count
    # towards what is owed.
    invoiced = sum(float(i.get("total_amount") or 0) for i in invoices
                   if i.get("status") != "draft")
    paid = sum(float(p.get("amount") or 0) for p in payments)
    return {
        "pupil_id": pupil_id,
        "invoices": invoices,
        "payments": payments,
        "total_invoiced": round(invoiced, 2),
        "total_paid": round(paid, 2),
        "balance": round(invoiced - paid, 2),
    }


# ── Pickers / summary ────────────────────────────────────────────────────────

def list_pupil_choices() -> list[tuple[str, str]]:
    """Return ``(pupil_id, "Name (id) — room")`` pairs for child pickers."""
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT pupil_id, first_name, last_name, room FROM pupils "
                "WHERE status = 'active' ORDER BY last_name, first_name"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("list_pupil_choices failed")
        raise
    out = []
    for r in rows:
        room = f" — {r['room']}" if r["room"] else ""
        out.append((r["pupil_id"],
                    f"{r['first_name']} {r['last_name']} ({r['pupil_id']}){room}"))
    return out


def summary() -> dict[str, Any]:
    """Headline counts for the request inbox."""
    rows = list_requests()
    open_rows = [r for r in rows if r.is_open]
    today = _today()
    return {
        "total": len(rows),
        "pending": len(open_rows),
        "approved": sum(1 for r in rows if r.status == "approved"),
        "declined": sum(1 for r in rows if r.status == "declined"),
        "pending_by_type": {t: sum(1 for r in open_rows if r.request_type == t)
                            for t in REQUEST_TYPES},
        "submitted_today": sum(1 for r in rows
                               if (r.submitted_at or "").startswith(today)),
        # Anything a parent asked about a date that has now passed still sitting
        # in the inbox is a self-service promise the setting has broken.
        "overdue": sum(
            1 for r in open_rows if r.request_type in ("session", "absence")
            and (r.payload.get("session_date")
                 or r.payload.get("absence_date") or today) < today),
    }
