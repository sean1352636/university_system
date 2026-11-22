"""Sixth-form alumni — Events, RSVPs and the event extensions (#27-#30).

Split out of :mod:`education_system.systems.sixth_form.domain.learners.alumni.alumni`, which re-exports
every name; import from there.
"""

from __future__ import annotations

import datetime as _dt
import secrets
from dataclasses import dataclass
from typing import Any
from education_system.systems.sixth_form.infrastructure import database as db

from .models import (
    DEFAULT_EVENT_STATUS,
    DEFAULT_RSVP_STATUS,
    EVENT_STATUSES,
    EVENT_TYPES,
    RSVP_STATUSES,
    _log_action,
)
from .db import (
    ValidationError,
    _connect,
    _opt,
    _require,
    _validate_date,
    init_db,
)


# ── Events ───────────────────────────────────────────────────────

@dataclass
class Event:
    event_id: int
    name: str
    event_type: str
    event_date: str | None
    end_date: str | None
    location: str | None
    capacity: int | None
    cost_pence: int
    status: str
    notes: str | None
    created_at: str


def _row_event(r: db.Row) -> Event:
    return Event(
        event_id=r["event_id"], name=r["name"],
        event_type=r["event_type"], event_date=r["event_date"],
        end_date=r["end_date"], location=r["location"],
        capacity=r["capacity"], cost_pence=int(r["cost_pence"] or 0),
        status=r["status"], notes=r["notes"],
        created_at=r["created_at"],
    )


def _validate_event(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["name"] = _require(payload.get("name"), "Name").strip()
    et = (payload.get("event_type") or EVENT_TYPES[0]).strip()
    if et not in EVENT_TYPES:
        raise ValidationError(
            f"Event type must be one of: {', '.join(EVENT_TYPES)}")
    out["event_type"] = et
    out["event_date"] = _validate_date(payload.get("event_date"),
                                          "Event date")
    out["end_date"]   = _validate_date(payload.get("end_date"),
                                          "End date")
    out["location"] = (payload.get("location") or "").strip() or None
    cap = payload.get("capacity")
    if cap in (None, ""):
        out["capacity"] = None
    else:
        try:
            out["capacity"] = max(0, int(cap))
        except (TypeError, ValueError):
            raise ValidationError("Capacity must be a number") from None
    out["cost_pence"] = _resolve_money(payload, "cost_pence", "cost",
                                          "Cost", allow_zero=True,
                                          required=False)
    status = (payload.get("status") or DEFAULT_EVENT_STATUS).strip()
    if status not in EVENT_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(EVENT_STATUSES)}")
    out["status"] = status
    out["notes"] = (payload.get("notes") or "").strip() or None
    return out


def create_event(payload: dict[str, Any]) -> Event:
    init_db()
    p = _validate_event(payload)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO alumni_events
                   (name, event_type, event_date, end_date, location,
                    capacity, cost_pence, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (p["name"], p["event_type"], p["event_date"], p["end_date"],
             p["location"], p["capacity"], p["cost_pence"],
             p["status"], p["notes"]))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_events WHERE event_id = ?",
            (cur.lastrowid,)).fetchone()
    out = _row_event(r)
    _log_action("event.create", event_id=out.event_id,
                  name=out.name, event_type=out.event_type,
                  event_date=out.event_date)
    return out


def get_event(event_id: int) -> Event | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_events WHERE event_id = ?",
            (event_id,)).fetchone()
    return _row_event(r) if r else None


def list_events(*, status: str | None = None,
                  upcoming_only: bool = False) -> list[Event]:
    init_db()
    clauses, args = [], []
    if status:
        if status not in EVENT_STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(EVENT_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if upcoming_only:
        clauses.append("(event_date IS NULL OR event_date >= ?)")
        args.append(_dt.date.today().isoformat())
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM alumni_events {where} "
            "ORDER BY COALESCE(event_date, '9999') ASC, event_id DESC")
    with _connect() as conn:
        return [_row_event(r)
                  for r in conn.execute(sql, args).fetchall()]


def update_event(event_id: int, payload: dict[str, Any]) -> Event:
    existing = get_event(event_id)
    if existing is None:
        raise ValidationError(f"No event #{event_id}")
    merged = {
        "name":       payload.get("name", existing.name),
        "event_type": payload.get("event_type", existing.event_type),
        "event_date": payload.get("event_date", existing.event_date),
        "end_date":   payload.get("end_date", existing.end_date),
        "location":   payload.get("location", existing.location),
        "capacity":   payload.get("capacity", existing.capacity),
        "cost_pence": payload.get("cost_pence", existing.cost_pence),
        "status":     payload.get("status", existing.status),
        "notes":      payload.get("notes", existing.notes),
    }
    p = _validate_event(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE alumni_events SET
                   name = ?, event_type = ?, event_date = ?, end_date = ?,
                   location = ?, capacity = ?, cost_pence = ?,
                   status = ?, notes = ?
               WHERE event_id = ?""",
            (p["name"], p["event_type"], p["event_date"], p["end_date"],
             p["location"], p["capacity"], p["cost_pence"],
             p["status"], p["notes"], event_id))
        conn.commit()
    out = get_event(event_id)
    assert out is not None
    return out


def delete_event(event_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_events WHERE event_id = ?",
            (event_id,))
        conn.commit()
        return cur.rowcount > 0


# ── RSVPs ────────────────────────────────────────────────────────

@dataclass
class Rsvp:
    rsvp_id: int
    event_id: int
    alumni_id: int
    status: str
    attended: bool
    guests: int
    notes: str | None
    created_at: str


def _row_rsvp(r: db.Row) -> Rsvp:
    return Rsvp(
        rsvp_id=r["rsvp_id"], event_id=r["event_id"],
        alumni_id=r["alumni_id"], status=r["status"],
        attended=bool(r["attended"]),
        guests=int(r["guests"] or 0),
        notes=r["notes"], created_at=r["created_at"],
    )


def _original_set_rsvp(event_id: int, alumni_id: int, *,
              status: str = DEFAULT_RSVP_STATUS,
              attended: bool | None = None,
              guests: int | None = None,
              notes: str | None = None) -> Rsvp:
    """Create or update an RSVP. Upserts on the unique
    (event_id, alumni_id) key."""
    init_db()
    if status not in RSVP_STATUSES:
        raise ValidationError(
            f"RSVP status must be one of: {', '.join(RSVP_STATUSES)}")
    with _connect() as conn:
        if get_event(event_id) is None:
            raise ValidationError(f"No event #{event_id}")
        _require_alumnus(conn, alumni_id)
        existing = conn.execute(
            "SELECT * FROM alumni_event_rsvps "
            "WHERE event_id = ? AND alumni_id = ?",
            (event_id, alumni_id)).fetchone()
        if existing:
            new_status   = status
            new_attended = (existing["attended"]
                              if attended is None
                              else (1 if attended else 0))
            new_guests   = (existing["guests"]
                              if guests is None
                              else max(0, int(guests)))
            new_notes    = (existing["notes"]
                              if notes is None
                              else (notes.strip() or None))
            conn.execute(
                "UPDATE alumni_event_rsvps SET status = ?, "
                "attended = ?, guests = ?, notes = ? "
                "WHERE rsvp_id = ?",
                (new_status, new_attended, new_guests, new_notes,
                 existing["rsvp_id"]))
            conn.commit()
            r = conn.execute(
                "SELECT * FROM alumni_event_rsvps WHERE rsvp_id = ?",
                (existing["rsvp_id"],)).fetchone()
        else:
            conn.execute(
                """INSERT INTO alumni_event_rsvps
                       (event_id, alumni_id, status, attended,
                        guests, notes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (event_id, alumni_id, status,
                 1 if attended else 0,
                 max(0, int(guests or 0)),
                 (notes or "").strip() or None))
            conn.commit()
            r = conn.execute(
                "SELECT * FROM alumni_event_rsvps "
                "WHERE event_id = ? AND alumni_id = ?",
                (event_id, alumni_id)).fetchone()
    return _row_rsvp(r)


def list_rsvps_for_event(event_id: int) -> list[Rsvp]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_event_rsvps WHERE event_id = ? "
            "ORDER BY status, rsvp_id",
            (event_id,)).fetchall()
    return [_row_rsvp(r) for r in rows]


def list_rsvps_for_alumnus(alumni_id: int) -> list[Rsvp]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_event_rsvps WHERE alumni_id = ? "
            "ORDER BY rsvp_id DESC",
            (alumni_id,)).fetchall()
    return [_row_rsvp(r) for r in rows]


def delete_rsvp(rsvp_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_event_rsvps WHERE rsvp_id = ?",
            (rsvp_id,))
        conn.commit()
        return cur.rowcount > 0


@dataclass
class EventAttendance:
    event_id: int
    invited: int
    accepted: int
    declined: int
    attended: int
    headcount: int     # attended + sum of guests for attended rows


def event_attendance(event_id: int) -> EventAttendance:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT status, attended, guests "
            "FROM alumni_event_rsvps WHERE event_id = ?",
            (event_id,)).fetchall()
    invited = accepted = declined = attended = headcount = 0
    for r in rows:
        invited += 1
        if r["status"] == "Accepted":
            accepted += 1
        if r["status"] == "Declined":
            declined += 1
        if r["attended"]:
            attended += 1
            headcount += 1 + int(r["guests"] or 0)
    return EventAttendance(
        event_id=event_id, invited=invited, accepted=accepted,
        declined=declined, attended=attended, headcount=headcount)


# ── #27 Event ticketing, waitlist, refunds ───────────────────────

@dataclass
class TicketedRsvp:
    rsvp_id: int
    event_id: int
    alumni_id: int
    status: str
    waitlisted: bool
    guests: int
    amount_paid_pence: int


def _row_ticketed(r: db.Row) -> TicketedRsvp:
    return TicketedRsvp(
        rsvp_id=r["rsvp_id"], event_id=r["event_id"],
        alumni_id=r["alumni_id"], status=r["status"],
        waitlisted=bool(_opt(r, "waitlisted") or 0),
        guests=int(r["guests"]),
        amount_paid_pence=int(_opt(r, "amount_paid_pence") or 0))


def buy_ticket(event_id: int, alumni_id: int, *,
                  guests: int = 0,
                  amount_paid_pence: int | None = None,
                  actor: str | None = None) -> TicketedRsvp:
    """Sell a ticket: creates/updates the RSVP to 'Accepted', stamps
    the amount paid, and auto-waitlists if the event capacity is
    full. The caller decides ``amount_paid_pence`` (which may differ
    from the event's listed ``cost_pence`` for early-bird or comp
    tickets); when omitted it defaults to ``cost_pence * (1+guests)``."""
    init_db()
    if guests < 0:
        raise ValidationError("guests must be ≥ 0")
    with _connect() as conn:
        ev = conn.execute(
            "SELECT capacity, cost_pence FROM alumni_events "
            "WHERE event_id = ?", (event_id,)).fetchone()
        if ev is None:
            raise ValidationError(f"No event #{event_id}")
        if amount_paid_pence is None:
            amount_paid_pence = int(ev["cost_pence"] or 0) * (1 + guests)
        seats_used = conn.execute(
            "SELECT COALESCE(SUM(1 + guests), 0) FROM alumni_event_rsvps "
            "WHERE event_id = ? AND status = 'Accepted' "
            "  AND COALESCE(waitlisted, 0) = 0",
            (event_id,)).fetchone()[0]
        capacity = ev["capacity"]
        waitlist = (capacity is not None
                       and seats_used + 1 + guests > int(capacity))
        existing = conn.execute(
            "SELECT * FROM alumni_event_rsvps "
            "WHERE event_id = ? AND alumni_id = ?",
            (event_id, alumni_id)).fetchone()
        if existing:
            conn.execute(
                """UPDATE alumni_event_rsvps SET
                       status = 'Accepted',
                       guests = ?,
                       amount_paid_pence = ?,
                       waitlisted = ?
                   WHERE rsvp_id = ?""",
                (guests, amount_paid_pence,
                 1 if waitlist else 0, existing["rsvp_id"]))
            rsvp_id = existing["rsvp_id"]
        else:
            cur = conn.execute(
                """INSERT INTO alumni_event_rsvps
                       (event_id, alumni_id, status, guests,
                        amount_paid_pence, waitlisted)
                   VALUES (?, ?, 'Accepted', ?, ?, ?)""",
                (event_id, alumni_id, guests,
                 amount_paid_pence, 1 if waitlist else 0))
            rsvp_id = cur.lastrowid
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_event_rsvps WHERE rsvp_id = ?",
            (rsvp_id,)).fetchone()
    _log_action("event.ticket", actor=actor, event_id=event_id,
                  alumni_id=alumni_id, amount_pence=amount_paid_pence,
                  waitlisted=waitlist)
    return _row_ticketed(r)


def promote_from_waitlist(event_id: int, *,
                             actor: str | None = None
                             ) -> list[TicketedRsvp]:
    """Promote waitlisted RSVPs (oldest first) into the open ticket
    pool while capacity allows. Returns the newly seated RSVPs."""
    init_db()
    promoted: list[TicketedRsvp] = []
    with _connect() as conn:
        ev = conn.execute(
            "SELECT capacity FROM alumni_events WHERE event_id = ?",
            (event_id,)).fetchone()
        if ev is None or ev["capacity"] is None:
            return []
        capacity = int(ev["capacity"])
        seats_used = int(conn.execute(
            "SELECT COALESCE(SUM(1 + guests), 0) FROM alumni_event_rsvps "
            "WHERE event_id = ? AND status = 'Accepted' "
            "  AND COALESCE(waitlisted, 0) = 0",
            (event_id,)).fetchone()[0])
        waitlist = conn.execute(
            "SELECT * FROM alumni_event_rsvps "
            "WHERE event_id = ? AND COALESCE(waitlisted, 0) = 1 "
            "ORDER BY created_at, rsvp_id", (event_id,)).fetchall()
        for r in waitlist:
            need = 1 + int(r["guests"])
            if seats_used + need > capacity:
                continue
            conn.execute(
                "UPDATE alumni_event_rsvps SET waitlisted = 0 "
                "WHERE rsvp_id = ?", (r["rsvp_id"],))
            seats_used += need
            promoted.append(_row_ticketed(r))
        conn.commit()
    if promoted:
        _log_action("event.waitlist.promote", actor=actor,
                      event_id=event_id, count=len(promoted))
    return promoted


@dataclass
class EventRefund:
    refund_id: int
    event_id: int
    alumni_id: int
    amount_pence: int
    reason: str | None
    refunded_at: str


def refund_ticket(event_id: int, alumni_id: int, *,
                     amount_pence: int | None = None,
                     reason: str | None = None,
                     actor: str | None = None) -> EventRefund:
    """Record a refund row and zero-out the corresponding ticket's
    paid amount. ``amount_pence=None`` refunds the full amount on
    file."""
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT rsvp_id, amount_paid_pence FROM alumni_event_rsvps "
            "WHERE event_id = ? AND alumni_id = ?",
            (event_id, alumni_id)).fetchone()
        if r is None:
            raise ValidationError("No matching RSVP")
        paid = int(_opt(r, "amount_paid_pence") or 0)
        amt = paid if amount_pence is None else int(amount_pence)
        if amt <= 0 or amt > paid:
            raise ValidationError(
                f"Refund amount must be between 1 and {paid}p")
        cur = conn.execute(
            """INSERT INTO alumni_event_refunds
                   (event_id, alumni_id, amount_pence, reason)
               VALUES (?, ?, ?, ?)""",
            (event_id, alumni_id, amt,
             (reason or "").strip() or None))
        conn.execute(
            "UPDATE alumni_event_rsvps "
            "SET amount_paid_pence = amount_paid_pence - ? "
            "WHERE rsvp_id = ?", (amt, r["rsvp_id"]))
        conn.commit()
        row = conn.execute(
            "SELECT * FROM alumni_event_refunds WHERE refund_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("event.refund", actor=actor, event_id=event_id,
                  alumni_id=alumni_id, amount_pence=amt)
    return EventRefund(
        refund_id=row["refund_id"], event_id=row["event_id"],
        alumni_id=row["alumni_id"],
        amount_pence=int(row["amount_pence"]),
        reason=row["reason"], refunded_at=row["refunded_at"])


def list_event_refunds(event_id: int) -> list[EventRefund]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_event_refunds WHERE event_id = ? "
            "ORDER BY refunded_at DESC", (event_id,)).fetchall()
    return [EventRefund(
        refund_id=r["refund_id"], event_id=r["event_id"],
        alumni_id=r["alumni_id"],
        amount_pence=int(r["amount_pence"]),
        reason=r["reason"], refunded_at=r["refunded_at"])
            for r in rows]


@dataclass
class EventFinance:
    event_id: int
    tickets_sold: int
    seats_used: int
    waitlist: int
    gross_pence: int
    refunds_pence: int
    net_pence: int


def event_finance(event_id: int) -> EventFinance:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            """SELECT
                 COUNT(*) FILTER (
                   WHERE status='Accepted'
                     AND COALESCE(waitlisted,0)=0)  AS tickets,
                 COALESCE(SUM(CASE WHEN status='Accepted'
                                AND COALESCE(waitlisted,0)=0
                              THEN 1 + guests ELSE 0 END), 0) AS seats,
                 COUNT(*) FILTER (
                   WHERE COALESCE(waitlisted,0)=1) AS waitlist,
                 COALESCE(SUM(amount_paid_pence), 0) AS gross
               FROM alumni_event_rsvps WHERE event_id = ?""",
            (event_id,)).fetchone()
        refunds = int(conn.execute(
            "SELECT COALESCE(SUM(amount_pence), 0) "
            "FROM alumni_event_refunds WHERE event_id = ?",
            (event_id,)).fetchone()[0])
    gross = int(r["gross"])
    return EventFinance(
        event_id=event_id, tickets_sold=int(r["tickets"]),
        seats_used=int(r["seats"]), waitlist=int(r["waitlist"]),
        gross_pence=gross, refunds_pence=refunds,
        net_pence=gross - refunds)


# ── #28 QR check-in ──────────────────────────────────────────────

def issue_checkin_token(rsvp_id: int, *,
                            actor: str | None = None) -> str:
    """Mint a unique check-in token for one RSVP. Idempotent — if a
    token already exists it is returned unchanged."""
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT checkin_token FROM alumni_event_rsvps "
            "WHERE rsvp_id = ?", (rsvp_id,)).fetchone()
        if r is None:
            raise ValidationError(f"No RSVP #{rsvp_id}")
        existing = _opt(r, "checkin_token")
        if existing:
            return existing
        token = secrets.token_urlsafe(12)
        conn.execute(
            "UPDATE alumni_event_rsvps SET checkin_token = ? "
            "WHERE rsvp_id = ?", (token, rsvp_id))
        conn.commit()
    _log_action("event.checkin.token", actor=actor, rsvp_id=rsvp_id)
    return token


def issue_event_checkin_tokens(event_id: int, *,
                                    actor: str | None = None) -> int:
    """Bulk-issue tokens for every accepted, non-waitlisted RSVP on
    an event that doesn't already have one. Returns count minted."""
    init_db()
    minted = 0
    with _connect() as conn:
        rows = conn.execute(
            "SELECT rsvp_id FROM alumni_event_rsvps "
            "WHERE event_id = ? AND status = 'Accepted' "
            "  AND COALESCE(waitlisted, 0) = 0 "
            "  AND (checkin_token IS NULL OR checkin_token = '')",
            (event_id,)).fetchall()
        for r in rows:
            token = secrets.token_urlsafe(12)
            conn.execute(
                "UPDATE alumni_event_rsvps SET checkin_token = ? "
                "WHERE rsvp_id = ?", (token, r["rsvp_id"]))
            minted += 1
        conn.commit()
    _log_action("event.checkin.bulk_token", actor=actor,
                  event_id=event_id, minted=minted)
    return minted


@dataclass
class CheckinResult:
    rsvp_id: int
    event_id: int
    alumni_id: int
    already_checked_in: bool
    checked_in_at: str


def check_in_by_token(token: str, *,
                         actor: str | None = None) -> CheckinResult:
    """Scan a check-in token: mark ``attended=1`` and stamp
    ``checkin_at``. If already checked in, returns the existing
    record without modification."""
    init_db()
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_event_rsvps "
            "WHERE checkin_token = ?", (token,)).fetchone()
        if r is None:
            raise ValidationError("Unknown check-in token")
        already = bool(_opt(r, "checkin_at"))
        if not already:
            conn.execute(
                "UPDATE alumni_event_rsvps SET attended = 1, "
                "    checkin_at = ? WHERE rsvp_id = ?",
                (now, r["rsvp_id"]))
            conn.commit()
    _log_action("event.checkin", actor=actor,
                  rsvp_id=r["rsvp_id"], event_id=r["event_id"],
                  already=already)
    return CheckinResult(
        rsvp_id=r["rsvp_id"], event_id=r["event_id"],
        alumni_id=r["alumni_id"], already_checked_in=already,
        checked_in_at=_opt(r, "checkin_at") or now)


# ── #29 Auto-feedback surveys on event close ─────────────────────

def close_event_with_feedback(event_id: int, *,
                                  survey_questions: list[dict[str, Any]]
                                  | None = None,
                                  invite_actor: str | None = None
                                  ) -> tuple[Event, Survey]:
    """Mark the event as ``Completed`` and auto-create a survey whose
    invitations are sent to every alumnus who actually attended.
    ``survey_questions`` follows the same shape used by
    :func:`create_survey`; a sensible default is supplied if omitted."""
    init_db()
    ev = get_event(event_id)
    if ev is None:
        raise ValidationError(f"No event #{event_id}")
    if "Completed" not in EVENT_STATUSES:
        raise ValidationError("'Completed' event status is not configured")
    update_event(event_id, {"status": "Completed"})
    questions = survey_questions or [
        {"key": "overall", "type": "freeform",
            "label": "Overall, how was the event? (1-5 or free text)"},
        {"key": "comments", "type": "freeform",
            "label": "Comments / what could be better?"},
    ]
    survey = create_survey(
        name=f"Feedback — {ev.name}",
        description=(
            f"Auto-generated feedback survey for event #{event_id}."),
        questions=questions)
    with _connect() as conn:
        rows = conn.execute(
            "SELECT alumni_id FROM alumni_event_rsvps "
            "WHERE event_id = ? AND attended = 1",
            (event_id,)).fetchall()
    for r in rows:
        try:
            invite_to_survey(survey.survey_id, r["alumni_id"])
        except ValidationError:
            continue
    _log_action("event.close.feedback", actor=invite_actor,
                  event_id=event_id, survey_id=survey.survey_id,
                  invited=len(rows))
    return get_event(event_id), survey  # type: ignore[return-value]


# ── #30 Reunion year planner ─────────────────────────────────────

REUNION_INTERVALS: tuple[int, ...] = (5, 10, 15, 20, 25, 30, 40, 50)


@dataclass
class ReunionSuggestion:
    leaving_year: str
    years_since: int
    cohort_size: int
    proposed_name: str
    proposed_date: str  # ISO


def suggest_reunions(*, today: _dt.date | None = None,
                          horizon_months: int = 18
                          ) -> list[ReunionSuggestion]:
    """Look at every distinct leaving cohort and propose a reunion
    event when the next round-year anniversary falls inside the
    given horizon."""
    init_db()
    today = today or _dt.date.today()
    horizon = today + _dt.timedelta(days=30 * horizon_months)
    out: list[ReunionSuggestion] = []
    with _connect() as conn:
        rows = conn.execute(
            "SELECT leaving_year, COUNT(*) AS n FROM alumni "
            "WHERE leaving_year IS NOT NULL "
            "  AND deleted_at IS NULL GROUP BY leaving_year"
        ).fetchall()
    for r in rows:
        try:
            ly = int(r["leaving_year"])
        except (TypeError, ValueError):
            continue
        for years in REUNION_INTERVALS:
            anniversary = _dt.date(ly + years, 7, 1)
            if today <= anniversary <= horizon:
                out.append(ReunionSuggestion(
                    leaving_year=str(ly),
                    years_since=years,
                    cohort_size=int(r["n"]),
                    proposed_name=f"Class of {ly} — {years}-year reunion",
                    proposed_date=anniversary.isoformat()))
                break
    out.sort(key=lambda s: s.proposed_date)
    return out


def create_reunion_events(*,
                              today: _dt.date | None = None,
                              horizon_months: int = 18,
                              actor: str | None = None
                              ) -> list[Event]:
    """Materialise the suggestions from :func:`suggest_reunions` into
    draft (``Planning``) events. Skips suggestions where a matching
    event name already exists."""
    init_db()
    created: list[Event] = []
    with _connect() as conn:
        existing = {row["name"] for row in conn.execute(
            "SELECT name FROM alumni_events").fetchall()}
    for s in suggest_reunions(today=today,
                                  horizon_months=horizon_months):
        if s.proposed_name in existing:
            continue
        try:
            created.append(create_event({
                "name": s.proposed_name,
                "event_type": "Reunion",
                "event_date": s.proposed_date,
                "status": "Planning",
                "notes": (f"Auto-suggested by planner — "
                              f"{s.years_since}y anniversary for "
                              f"{s.cohort_size} alumni"),
            }))
        except ValidationError:
            continue
    _log_action("reunion.plan", actor=actor, count=len(created))
    return created


def set_rsvp(event_id: int, alumni_id: int, *,
                status: str | None = None,
                **kwargs):
    """Set an RSVP and publish the ``rsvp.changed`` webhook (the work is
    :func:`_original_set_rsvp`)."""
    # No status means the plain default, as before the webhook wrapper
    # (which passed None through and failed validation).
    if status is None:
        status = DEFAULT_RSVP_STATUS
    r = _original_set_rsvp(event_id, alumni_id, status=status,
                              **kwargs)
    _emit_webhook("rsvp.changed", {
        "event_id": event_id, "alumni_id": alumni_id,
        "status": status})
    return r


# Sibling-module names, bound after this module's own definitions so the
# feature modules can call each other without an import cycle at load time.
# They are only used inside function bodies (and string annotations).
from .profile import (  # noqa: E402,F401
    _require_alumnus,
)
from .linking import (  # noqa: E402,F401
    _resolve_money,
)
from .surveys import (  # noqa: E402,F401
    Survey,
    create_survey,
    invite_to_survey,
)
from .integrations import (  # noqa: E402,F401
    _emit_webhook,
)
