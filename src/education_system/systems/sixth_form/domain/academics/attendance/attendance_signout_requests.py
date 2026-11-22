"""Sign-out requests — a learner asking ahead to leave site.

Sibling to :mod:`attendance_signout`. A sixth former with a dentist at
eleven used to have to turn up at reception and argue the case on the
spot; now they ask from the student portal, a member of staff approves
or declines it, and at the desk an approved request becomes the real
sign-out (:func:`use_request`) with the approver named as authorising it.

A request never takes anybody off site by itself. The college still
needs to know the moment somebody leaves, so the sign-out happens at the
desk or kiosk as before — the request only settles *whether* they may.

States: Requested → Approved / Declined, Requested or Approved →
Cancelled (by the learner, or staff), Approved → Used (signed out).
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass
from typing import Any

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_register as reg,
    attendance_signout as signout,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

ValidationError = core.ValidationError

REQUESTED: str = "Requested"
APPROVED: str = "Approved"
DECLINED: str = "Declined"
CANCELLED: str = "Cancelled"
USED: str = "Used"
STATES: tuple[str, ...] = (REQUESTED, APPROVED, DECLINED, CANCELLED, USED)
OPEN_STATES: frozenset[str] = frozenset({REQUESTED, APPROVED})

# How far ahead a learner may ask.
MAX_DAYS_AHEAD: int = 28

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_signout_requests (
    request_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id     TEXT NOT NULL,
    date           TEXT NOT NULL,
    leave_time     TEXT NOT NULL,
    reason         TEXT NOT NULL,
    detail         TEXT,
    expected_back  TEXT,
    parent_aware   INTEGER NOT NULL DEFAULT 0,
    state          TEXT NOT NULL DEFAULT 'Requested',
    requested_by   TEXT,
    decided_by     TEXT,
    decided_at     TEXT,
    decision_note  TEXT,
    signout_id     INTEGER,
    created_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (signout_id) REFERENCES attendance_signouts(signout_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_att_soreq_student
    ON attendance_signout_requests(student_id, date);
CREATE INDEX IF NOT EXISTS idx_att_soreq_state
    ON attendance_signout_requests(state, date);
"""


@dataclass
class SignOutRequest:
    request_id: int
    student_id: str
    date: str
    leave_time: str
    reason: str
    detail: str | None
    expected_back: str | None
    parent_aware: bool
    state: str
    requested_by: str | None
    decided_by: str | None
    decided_at: str | None
    decision_note: str | None
    signout_id: int | None
    created_at: str | None
    student_name: str | None = None

    @property
    def is_open(self) -> bool:
        return self.state in OPEN_STATES

    def describe(self) -> str:
        why = self.reason + (f" ({self.detail})" if self.detail else "")
        back = (f", back {self.expected_back}" if self.expected_back
                else "")
        return f"{self.date} {self.leave_time}: {why}{back} — {self.state}"


# ── DB plumbing ─────────────────────────────────────────────────────

def _connect() -> Any:
    return core._connect()


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    signout.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    _DB_READY = True


def _row(r: Any) -> SignOutRequest:
    return SignOutRequest(
        request_id=r["request_id"], student_id=r["student_id"],
        date=r["date"], leave_time=r["leave_time"], reason=r["reason"],
        detail=r["detail"], expected_back=r["expected_back"],
        parent_aware=bool(r["parent_aware"]), state=r["state"],
        requested_by=r["requested_by"], decided_by=r["decided_by"],
        decided_at=r["decided_at"], decision_note=r["decision_note"],
        signout_id=r["signout_id"], created_at=r["created_at"])


def _get(conn: Any, request_id: int) -> SignOutRequest:
    r = conn.execute(
        "SELECT * FROM attendance_signout_requests WHERE request_id = ?",
        (int(request_id),)).fetchone()
    if r is None:
        raise ValidationError(f"No sign-out request #{request_id}")
    return _row(r)


def _actor(name: str | None, what: str) -> str:
    name = (name or "").strip()
    if not name:
        raise ValidationError(f"{what} must name who did it")
    return name


# ── Asking ──────────────────────────────────────────────────────────

def request_signout(
    student_id: str,
    reason: str,
    *,
    date: str,
    leave_time: str,
    detail: str | None = None,
    expected_back: str | None = None,
    parent_aware: bool = False,
    requested_by: str | None = None,
) -> SignOutRequest:
    """A learner (or someone for them) asks to leave site at a time.

    Same rules as signing out: detail for an appointment / early leave /
    other, a return after the departure, no return time for early
    leave. Today or up to :data:`MAX_DAYS_AHEAD` days ahead; one open
    request per learner per day.
    """
    init_db()
    student = signout._require_student(student_id)
    reason = signout.validate_reason(reason)
    date = core._validate_date(date)
    today = _dt.date.today()
    day = _dt.date.fromisoformat(date)
    if day < today:
        raise ValidationError("A sign-out request cannot be for a past day")
    if day > today + _dt.timedelta(days=MAX_DAYS_AHEAD):
        raise ValidationError(
            f"Requests can be made up to {MAX_DAYS_AHEAD} days ahead")
    leave_time = reg._validate_time(leave_time, "Leaving at")
    if day == today and signout._minutes(leave_time) < signout._minutes(
            signout._now_time()) - 5:
        raise ValidationError("That time today has already passed")
    detail = (detail or "").strip() or None
    if reason in signout.DETAIL_REQUIRED and not detail:
        raise ValidationError(f"{reason} needs a few words of detail")
    if expected_back:
        if reason in signout.NO_RETURN:
            raise ValidationError(
                "Early leave is for the rest of the day — choose "
                "Appointment or Other if you are coming back")
        expected_back = reg._validate_time(expected_back, "Back by")
        if signout._minutes(expected_back) <= signout._minutes(leave_time):
            raise ValidationError("Back by must be after the leaving time")
    else:
        expected_back = None

    with _connect() as conn:
        clash = conn.execute(
            "SELECT request_id FROM attendance_signout_requests "
            "WHERE student_id = ? AND date = ? AND state IN (?, ?)",
            (student.student_id, date, REQUESTED, APPROVED)).fetchone()
        if clash is not None:
            raise ValidationError(
                f"You already have an open request for {date} "
                f"(#{clash['request_id']}) — cancel it first")
        cur = conn.execute(
            """INSERT INTO attendance_signout_requests
                   (student_id, date, leave_time, reason, detail,
                    expected_back, parent_aware, state, requested_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (student.student_id, date, leave_time, reason, detail,
             expected_back, 1 if parent_aware else 0, REQUESTED,
             (requested_by or "").strip() or None))
        conn.commit()
        out = _get(conn, int(cur.lastrowid or 0))
    logger.info("Sign-out request #%s from %s for %s %s", out.request_id,
                out.student_id, date, leave_time)
    return out


def cancel_request(request_id: int, *, by: str,
                   student_id: str | None = None) -> SignOutRequest:
    """Withdraw an open request. ``student_id`` limits it to their own."""
    init_db()
    by = _actor(by, "A cancellation")
    with _connect() as conn:
        req = _get(conn, request_id)
        if student_id is not None and req.student_id != student_id:
            raise ValidationError(f"No sign-out request #{request_id}")
        if not req.is_open:
            raise ValidationError(f"Request #{request_id} is {req.state}")
        conn.execute(
            "UPDATE attendance_signout_requests SET state = ?, "
            "decided_by = COALESCE(decided_by, ?), "
            "decided_at = COALESCE(decided_at, datetime('now')) "
            "WHERE request_id = ?", (CANCELLED, by, req.request_id))
        conn.commit()
        return _get(conn, req.request_id)


# ── Deciding ────────────────────────────────────────────────────────

def _decide(request_id: int, state: str, *, by: str,
            note: str | None) -> SignOutRequest:
    init_db()
    by = _actor(by, "A decision")
    with _connect() as conn:
        req = _get(conn, request_id)
        if req.state != REQUESTED:
            raise ValidationError(f"Request #{request_id} is {req.state}")
        conn.execute(
            "UPDATE attendance_signout_requests SET state = ?, "
            "decided_by = ?, decided_at = datetime('now'), "
            "decision_note = ? WHERE request_id = ?",
            (state, by, (note or "").strip() or None, req.request_id))
        conn.commit()
        out = _get(conn, req.request_id)
    logger.info("Sign-out request #%s %s by %s", request_id, state.lower(),
                by)
    return out


def approve(request_id: int, *, by: str,
            note: str | None = None) -> SignOutRequest:
    return _decide(request_id, APPROVED, by=by, note=note)


def decline(request_id: int, *, by: str,
            note: str | None = None) -> SignOutRequest:
    if not (note or "").strip():
        raise ValidationError("Say why the request is declined — the "
                              "learner sees it")
    return _decide(request_id, DECLINED, by=by, note=note)


def use_request(request_id: int, *, recorded_by: str,
                via: str = "Desk",
                parent_permission: bool = False,
                permission_from: str | None = None) -> signout.SignOut:
    """Turn an approved request for today into the actual sign-out."""
    init_db()
    recorded_by = _actor(recorded_by, "A sign-out")
    with _connect() as conn:
        req = _get(conn, request_id)
    if req.state != APPROVED:
        raise ValidationError(f"Request #{request_id} is {req.state}, "
                              "not Approved")
    if req.date != _dt.date.today().isoformat():
        raise ValidationError(f"Request #{request_id} is for {req.date}")
    trip = signout.sign_out(
        req.student_id, req.reason, detail=req.detail,
        expected_back=req.expected_back,
        parent_permission=parent_permission,
        permission_from=permission_from,
        authorised_by=req.decided_by, via=via, recorded_by=recorded_by,
        notes=f"Pre-approved request #{req.request_id}")
    with _connect() as conn:
        conn.execute(
            "UPDATE attendance_signout_requests SET state = ?, "
            "signout_id = ? WHERE request_id = ?",
            (USED, trip.signout_id, req.request_id))
        conn.commit()
    return trip


# ── Reading ─────────────────────────────────────────────────────────

def get_request(request_id: int) -> SignOutRequest | None:
    init_db()
    with _connect() as conn:
        try:
            return _get(conn, request_id)
        except ValidationError:
            return None


def list_requests(*, student_id: str | None = None,
                  state: str | None = None, date: str | None = None,
                  open_only: bool = False, limit: int = 200,
                  with_names: bool = False) -> list[SignOutRequest]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id)
    if state:
        clauses.append("state = ?")
        args.append(state)
    if date:
        clauses.append("date = ?")
        args.append(core._validate_date(date))
    if open_only:
        clauses.append("state IN (?, ?)")
        args.extend((REQUESTED, APPROVED))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = [_row(r) for r in conn.execute(
            f"SELECT * FROM attendance_signout_requests {where} "  # noqa: S608
            "ORDER BY date DESC, leave_time DESC, request_id DESC LIMIT ?",
            (*args, int(limit))).fetchall()]
    if with_names and rows:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        index = {s.student_id: s.full_name for s in _students.list_students()}
        for r in rows:
            r.student_name = index.get(r.student_id)
    return rows


def pending(*, with_names: bool = True) -> list[SignOutRequest]:
    """Requests waiting for a decision, soonest first."""
    rows = list_requests(state=REQUESTED, with_names=with_names)
    return sorted(rows, key=lambda r: (r.date, r.leave_time))


def approved_for_today(*, with_names: bool = True) -> list[SignOutRequest]:
    """Approved requests the desk should expect today."""
    rows = list_requests(state=APPROVED, date=_dt.date.today().isoformat(),
                         with_names=with_names)
    return sorted(rows, key=lambda r: r.leave_time)


__all__ = [
    "REQUESTED", "APPROVED", "DECLINED", "CANCELLED", "USED", "STATES",
    "SignOutRequest", "ValidationError", "request_signout",
    "cancel_request", "approve", "decline", "use_request", "get_request",
    "list_requests", "pending", "approved_for_today",
]
