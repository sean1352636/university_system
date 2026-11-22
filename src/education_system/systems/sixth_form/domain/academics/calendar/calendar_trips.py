"""Trip details behind the Sixth Form Calendar's Trip events.

Sibling to :mod:`calendar`. "Trip" has been a first-class event type
from the start, carrying nothing a trip actually needs: no risk
assessment reference, no staffing ratio, no transport, nothing about
consent. The calendar knew *when* the coach left and nothing else.

The money side already exists and is not rebuilt here:
:mod:`finance.trips` runs the ledger — per-student bookings, consent,
deposits, payment states. This module adds the two missing pieces:

* **The trip record** (:class:`TripDetail`) — one row of operational
  fact per Trip event: risk assessment ref, staff-to-student ratio,
  transport, emergency contact, first aider. The things the EVC asks
  for and the calendar could never answer.
* **The finance link** — an explicit joint between a calendar event
  and a ledger trip, plus :func:`publish_to_finance` to mint the
  ledger entry from the event so the two start from the same facts.

:func:`readiness` is why the linkage earns its keep: one call that
answers "can this trip actually run?" — risk assessment on file,
consent coverage from the ledger, headcount against the ratio — a
fortnight before departure rather than in the car park.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from education_system import paths
from education_system.systems.sixth_form.domain.academics.calendar import (
    calendar as core,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_CALENDAR_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

TRANSPORT_MODES: tuple[str, ...] = (
    "Coach", "Minibus", "Train", "Walking", "Public transport",
    "Parents drop-off", "Flight", "Other",
)
DEFAULT_TRANSPORT: str = "Coach"

# One member of staff per this many students unless the record says
# otherwise. The EVC sets the real number per trip; this is only the
# default the form opens with.
DEFAULT_RATIO: int = 15


_SCHEMA = """
CREATE TABLE IF NOT EXISTS calendar_trip_details (
    detail_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id            INTEGER NOT NULL UNIQUE,
    risk_assessment_ref TEXT,
    risk_assessment_ok  INTEGER NOT NULL DEFAULT 0,
    ratio_students      INTEGER NOT NULL DEFAULT 15,
    staff_count         INTEGER NOT NULL DEFAULT 0,
    transport           TEXT NOT NULL DEFAULT 'Coach',
    emergency_contact   TEXT,
    first_aider         TEXT,
    finance_trip_id     INTEGER,
    notes               TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_cal_trip_event
    ON calendar_trip_details(event_id);
CREATE INDEX IF NOT EXISTS idx_cal_trip_finance
    ON calendar_trip_details(finance_trip_id);
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class TripDetail:
    detail_id: int
    event_id: int
    risk_assessment_ref: str | None
    risk_assessment_ok: bool
    ratio_students: int
    staff_count: int
    transport: str
    emergency_contact: str | None
    first_aider: str | None
    finance_trip_id: int | None
    notes: str | None
    created_at: str
    updated_at: str

    def staff_needed(self, student_count: int) -> int:
        if student_count <= 0:
            return 0
        return -(-student_count // self.ratio_students)   # ceil div

    @property
    def is_linked(self) -> bool:
        return self.finance_trip_id is not None


@dataclass
class ReadinessReport:
    """Can this trip run? Each blocker is one plain sentence."""

    event_id: int
    blockers: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return not self.blockers

    @property
    def summary(self) -> str:
        if self.ready:
            head = "Ready to run."
        else:
            head = "\n".join(f"✗ {b}" for b in self.blockers)
        tail = "\n".join(f"· {n}" for n in self.notes)
        return f"{head}\n{tail}".strip()


# ── DB plumbing ─────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    core.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    logger.debug("Calendar trip-detail schema ready at %s", DB_PATH)
    _DB_READY = True


def _row(r: sqlite3.Row) -> TripDetail:
    return TripDetail(
        detail_id=r["detail_id"], event_id=r["event_id"],
        risk_assessment_ref=r["risk_assessment_ref"],
        risk_assessment_ok=bool(r["risk_assessment_ok"]),
        ratio_students=r["ratio_students"],
        staff_count=r["staff_count"], transport=r["transport"],
        emergency_contact=r["emergency_contact"],
        first_aider=r["first_aider"],
        finance_trip_id=r["finance_trip_id"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"])


# ── Validation ──────────────────────────────────────────────────────

def _trip_event(event_id: int) -> core.Event:
    event = core.get_event(event_id)
    if event is None or event.is_deleted:
        raise ValidationError(f"No event #{event_id}")
    if event.event_type != "Trip":
        raise ValidationError(
            f"Event #{event_id} is a {event.event_type}, not a Trip")
    return event


def _validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["risk_assessment_ref"] = (
        payload.get("risk_assessment_ref") or "").strip() or None
    out["risk_assessment_ok"] = bool(payload.get("risk_assessment_ok"))
    if out["risk_assessment_ok"] and not out["risk_assessment_ref"]:
        raise ValidationError(
            "A risk assessment cannot be signed off without a "
            "reference")

    ratio = payload.get("ratio_students", DEFAULT_RATIO)
    try:
        n = int(ratio if ratio not in (None, "") else DEFAULT_RATIO)
    except (TypeError, ValueError):
        raise ValidationError("Ratio must be a whole number") from None
    if not 1 <= n <= 30:
        raise ValidationError("Ratio must be between 1 and 30 "
                              "students per staff member")
    out["ratio_students"] = n

    staff = payload.get("staff_count", 0)
    try:
        s = int(staff if staff not in (None, "") else 0)
    except (TypeError, ValueError):
        raise ValidationError(
            "Staff count must be a whole number") from None
    if s < 0:
        raise ValidationError("Staff count cannot be negative")
    out["staff_count"] = s

    transport = (payload.get("transport")
                 or DEFAULT_TRANSPORT).strip()
    if transport not in TRANSPORT_MODES:
        raise ValidationError(
            f"Transport must be one of: {', '.join(TRANSPORT_MODES)}")
    out["transport"] = transport

    out["emergency_contact"] = (
        payload.get("emergency_contact") or "").strip() or None
    out["first_aider"] = (
        payload.get("first_aider") or "").strip() or None
    out["notes"] = (payload.get("notes") or "").strip() or None
    return out


# ── CRUD ────────────────────────────────────────────────────────────

def set_detail(event_id: int,
               payload: dict[str, Any]) -> TripDetail:
    """Create or update the trip record for a Trip event."""
    init_db()
    _trip_event(event_id)
    existing = get_detail(event_id)
    if existing is not None:
        merged = {
            "risk_assessment_ref": payload.get(
                "risk_assessment_ref", existing.risk_assessment_ref),
            "risk_assessment_ok": payload.get(
                "risk_assessment_ok", existing.risk_assessment_ok),
            "ratio_students": payload.get(
                "ratio_students", existing.ratio_students),
            "staff_count": payload.get(
                "staff_count", existing.staff_count),
            "transport": payload.get("transport", existing.transport),
            "emergency_contact": payload.get(
                "emergency_contact", existing.emergency_contact),
            "first_aider": payload.get(
                "first_aider", existing.first_aider),
            "notes": payload.get("notes", existing.notes),
        }
        p = _validate_payload(merged)
        with _connect() as conn:
            conn.execute(
                """UPDATE calendar_trip_details SET
                       risk_assessment_ref = ?, risk_assessment_ok = ?,
                       ratio_students = ?, staff_count = ?,
                       transport = ?, emergency_contact = ?,
                       first_aider = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE event_id = ?""",
                (p["risk_assessment_ref"],
                 1 if p["risk_assessment_ok"] else 0,
                 p["ratio_students"], p["staff_count"], p["transport"],
                 p["emergency_contact"], p["first_aider"], p["notes"],
                 event_id))
            conn.commit()
    else:
        p = _validate_payload(payload)
        with _connect() as conn:
            conn.execute(
                """INSERT INTO calendar_trip_details
                       (event_id, risk_assessment_ref,
                        risk_assessment_ok, ratio_students,
                        staff_count, transport, emergency_contact,
                        first_aider, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (event_id, p["risk_assessment_ref"],
                 1 if p["risk_assessment_ok"] else 0,
                 p["ratio_students"], p["staff_count"], p["transport"],
                 p["emergency_contact"], p["first_aider"], p["notes"]))
            conn.commit()
    out = get_detail(event_id)
    assert out is not None
    return out


def get_detail(event_id: int) -> TripDetail | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM calendar_trip_details WHERE event_id = ?",
            (event_id,)).fetchone()
    return _row(r) if r else None


def list_details() -> list[TripDetail]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT d.* FROM calendar_trip_details d "
            "JOIN calendar_events e ON e.event_id = d.event_id "
            "WHERE e.deleted_at IS NULL "
            "ORDER BY e.start_date, d.event_id").fetchall()
    return [_row(r) for r in rows]


# ── The finance link ────────────────────────────────────────────────

def _finance():
    try:
        from education_system.systems.sixth_form.domains.finance.domain.trips import (
            trips as fin,
        )
        return fin
    except Exception:                       # pragma: no cover - optional dep
        logger.debug("Finance trips module unavailable", exc_info=True)
        return None


def link_finance(event_id: int, finance_trip_id: int) -> TripDetail:
    """Point a Trip event at an existing ledger trip."""
    init_db()
    _trip_event(event_id)
    fin = _finance()
    if fin is not None and fin.get_trip(finance_trip_id) is None:
        raise ValidationError(
            f"No finance trip #{finance_trip_id}")
    if get_detail(event_id) is None:
        set_detail(event_id, {})
    with _connect() as conn:
        conn.execute(
            "UPDATE calendar_trip_details SET finance_trip_id = ?, "
            "updated_at = datetime('now') WHERE event_id = ?",
            (finance_trip_id, event_id))
        conn.commit()
    out = get_detail(event_id)
    assert out is not None
    logger.info("Event #%d linked to finance trip #%d", event_id,
                finance_trip_id)
    return out


def publish_to_finance(event_id: int, *,
                       deposit: float = 0.0) -> TripDetail:
    """Mint the ledger trip from the calendar event and link the two.

    The event's title, dates, cost and capacity become the ledger
    trip's opening facts. From then on the ledger owns the money and
    the calendar owns the day.
    """
    init_db()
    event = _trip_event(event_id)
    fin = _finance()
    if fin is None:
        raise ValidationError(
            "The finance trips module is not available")
    detail = get_detail(event_id)
    if detail is not None and detail.finance_trip_id is not None:
        raise ValidationError(
            f"Event #{event_id} is already linked to finance trip "
            f"#{detail.finance_trip_id}")
    # The organiser is free text here and a staff_id there, so it
    # travels in the description rather than failing validation.
    desc = event.description or ""
    if event.organiser:
        desc = (f"{desc}\nOrganiser: {event.organiser}").strip()
    trip = fin.create_trip({
        "name": event.title,
        "destination": event.location or "TBC",
        "start_date": event.start_date,
        "end_date": event.end_date,
        "cost_per_place": event.cost or 0.0,
        "deposit": deposit,
        "capacity": event.capacity,
        "description": desc or None,
    })
    return link_finance(event_id, trip.trip_id)


# ── Readiness ───────────────────────────────────────────────────────

def readiness(event_id: int) -> ReadinessReport:
    """Can this trip run? Checks the record, and — when the finance
    link is in place — consent and headcount from the ledger."""
    init_db()
    event = _trip_event(event_id)
    report = ReadinessReport(event_id=event_id)
    detail = get_detail(event_id)

    if detail is None:
        report.blockers.append(
            "No trip record — risk assessment, ratio and transport "
            "are all unrecorded")
        return report

    if not detail.risk_assessment_ok:
        if detail.risk_assessment_ref:
            report.blockers.append(
                f"Risk assessment {detail.risk_assessment_ref} is "
                "on file but not signed off")
        else:
            report.blockers.append("No risk assessment on file")
    if not detail.emergency_contact:
        report.blockers.append("No emergency contact recorded")
    if event.cost and detail.finance_trip_id is None:
        report.notes.append(
            f"Event has a cost (£{event.cost:.2f}) but no finance "
            "link — nobody can pay")

    fin = _finance()
    if detail.finance_trip_id is not None and fin is not None:
        bookings = [b for b in
                    fin.list_bookings(trip_id=detail.finance_trip_id)
                    if b.status in fin.ACTIVE_BOOKING_STATUSES]
        going = len(bookings)
        without_consent = [b.student_id for b in bookings
                           if not b.consent_received]
        if without_consent:
            report.blockers.append(
                f"{len(without_consent)} of {going} students have no "
                f"consent ({', '.join(without_consent[:5])}"
                f"{'…' if len(without_consent) > 5 else ''})")
        needed = detail.staff_needed(going)
        if detail.staff_count < needed:
            report.blockers.append(
                f"{going} students at 1:{detail.ratio_students} "
                f"needs {needed} staff; {detail.staff_count} "
                "recorded")
        report.notes.append(f"{going} active booking(s) on the "
                            "finance ledger")
    return report
