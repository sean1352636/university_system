"""Signing out of and back into the site, for the Sixth Form System.

Sibling to :mod:`attendance_kiosk` and :mod:`attendance_rollcall`. Sixth
formers come and go in a way younger pupils do not: a free period spent
in town, a dentist at eleven, lunch off site, a learner sent home ill at
two. Each of those is a moment the college stops knowing where somebody
is, and the register — which records lessons, not the building — cannot
say so.

So leaving is recorded as an event with a reason, and coming back closes
it:

* **Sign-out** (:func:`sign_out`) — why (free period off site,
  appointment, lunch, early leave, other), whether a parent gave
  permission and who confirmed it, and when they are due back. Early
  leave does not expect a return, and stamps a departure on the rest of
  the day's register so the lessons they miss read as an early leave
  rather than a mystery.
* **Sign-in** (:func:`sign_in`) — closes the open sign-out. An entrance
  kiosk tap does the same (:mod:`attendance_kiosk`), because coming
  through the front door *is* coming back.
* **Who is off site now** (:func:`currently_off_site`) — the list a fire
  marshal needs. :mod:`attendance_rollcall` reads it: a signed-out
  learner is not expected at the assembly point, and a roll call marks
  them "Confirmed off site" with the reason from here.
* **Late returns** (:func:`late_returns`, :func:`raise_late_alerts`) —
  somebody due back at 13:30 who has not signed in by 13:45. The alert
  is recorded on the sign-out, and optionally queued to home through
  :mod:`attendance_notifications`.

Policy is light on purpose. Early leave without a parent's permission is
allowed, but only with a member of staff named as authorising it —
a sixth former going home ill should not be stuck at the desk because a
parent is in a meeting, and nobody should be able to leave on nobody's
say-so.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass
from typing import Any

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_register as reg,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

FREE_PERIOD: str = "Free period off site"
APPOINTMENT: str = "Appointment"
LUNCH: str = "Lunch off site"
EARLY_LEAVE: str = "Early leave"
OTHER: str = "Other"
REASONS: tuple[str, ...] = (FREE_PERIOD, APPOINTMENT, LUNCH, EARLY_LEAVE,
                            OTHER)

# Reasons that need a few words of detail — "appointment" with whom,
# "early leave" why.
DETAIL_REQUIRED: frozenset[str] = frozenset({APPOINTMENT, EARLY_LEAVE,
                                             OTHER})

# Reasons that do not expect the learner back today.
NO_RETURN: frozenset[str] = frozenset({EARLY_LEAVE})

OUT: str = "Off site"
BACK: str = "Returned"
LEFT_FOR_DAY: str = "Left for the day"
STATES: tuple[str, ...] = (OUT, BACK, LEFT_FOR_DAY)

# Minutes past the expected return before a late-return alert is due.
LATE_GRACE_MINUTES: int = 15

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_signouts (
    signout_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id        TEXT NOT NULL,
    date              TEXT NOT NULL,
    out_time          TEXT NOT NULL,
    reason            TEXT NOT NULL,
    detail            TEXT,
    parent_permission INTEGER NOT NULL DEFAULT 0,
    permission_from   TEXT,
    authorised_by     TEXT,
    expected_back     TEXT,
    will_return       INTEGER NOT NULL DEFAULT 1,
    state             TEXT NOT NULL DEFAULT 'Off site',
    in_time           TEXT,
    signed_out_via    TEXT,
    signed_in_via     TEXT,
    recorded_by       TEXT,
    late_alert_at     TEXT,
    late_alert_by     TEXT,
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_att_signout_date
    ON attendance_signouts(date, state);
CREATE INDEX IF NOT EXISTS idx_att_signout_student
    ON attendance_signouts(student_id, date);
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class SignOut:
    """One trip off site, open until the learner signs back in."""

    signout_id: int
    student_id: str
    date: str
    out_time: str
    reason: str
    detail: str | None
    parent_permission: bool
    permission_from: str | None
    authorised_by: str | None
    expected_back: str | None
    returning: bool
    state: str
    in_time: str | None
    signed_out_via: str | None
    signed_in_via: str | None
    recorded_by: str | None
    late_alert_at: str | None
    late_alert_by: str | None
    notes: str | None
    created_at: str | None
    student_name: str | None = None

    @property
    def is_out(self) -> bool:
        return self.state == OUT

    def minutes_overdue(self, *, at_time: str | None = None) -> int:
        """How long past the expected return, 0 if not (yet) late."""
        if not self.is_out or not self.expected_back:
            return 0
        now = at_time or _now_time()
        return max(0, _minutes(now) - _minutes(self.expected_back))

    @property
    def label(self) -> str:
        who = self.student_name or self.student_id
        back = (f", due back {self.expected_back}" if self.expected_back
                else "" if self.returning else ", not returning")
        why = self.reason + (f" ({self.detail})" if self.detail else "")
        return f"{who} — out {self.out_time}: {why}{back}"


# ── DB plumbing ─────────────────────────────────────────────────────

def _connect() -> Any:
    """The attendance database (same file and settings as the register).

    Borrowed from :mod:`attendance` rather than opened here, so this
    module carries no database driver import of its own.
    """
    return core._connect()


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    reg.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    logger.debug("Sign-out schema ready at %s", DB_PATH)
    _DB_READY = True


def _row(r: Any) -> SignOut:
    return SignOut(
        signout_id=r["signout_id"], student_id=r["student_id"],
        date=r["date"], out_time=r["out_time"], reason=r["reason"],
        detail=r["detail"], parent_permission=bool(r["parent_permission"]),
        permission_from=r["permission_from"],
        authorised_by=r["authorised_by"], expected_back=r["expected_back"],
        returning=bool(r["will_return"]), state=r["state"],
        in_time=r["in_time"], signed_out_via=r["signed_out_via"],
        signed_in_via=r["signed_in_via"], recorded_by=r["recorded_by"],
        late_alert_at=r["late_alert_at"], late_alert_by=r["late_alert_by"],
        notes=r["notes"], created_at=r["created_at"])


def _now_time() -> str:
    return _dt.datetime.now().strftime("%H:%M")


def _today() -> str:
    return _dt.date.today().isoformat()


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")[:2]
    return int(h) * 60 + int(m)


def _names(rows: list[SignOut]) -> list[SignOut]:
    if rows:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        index = {s.student_id: s.full_name for s in _students.list_students()}
        for row in rows:
            row.student_name = index.get(row.student_id)
    return rows


# ── Validation ──────────────────────────────────────────────────────

def validate_reason(value: Any) -> str:
    s = (value or "").strip() if isinstance(value, str) else ""
    if not s:
        raise ValidationError("Say why the learner is leaving site")
    for reason in REASONS:
        if s.lower() == reason.lower():
            return reason
    raise ValidationError(f"Reason must be one of: {', '.join(REASONS)}")


def _require_student(student_id: str) -> Any:
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    student = _students.get_student((student_id or "").strip())
    if student is None:
        raise ValidationError(f"No student with id {student_id}")
    return student


# ── Signing out and in ──────────────────────────────────────────────

def sign_out(
    student_id: str,
    reason: str,
    *,
    detail: str | None = None,
    expected_back: str | None = None,
    parent_permission: bool = False,
    permission_from: str | None = None,
    authorised_by: str | None = None,
    via: str | None = None,
    recorded_by: str | None = None,
    notes: str | None = None,
    date: str | None = None,
    at_time: str | None = None,
) -> SignOut:
    """Record a learner leaving site.

    Refuses a second sign-out while one is open (sign them in first),
    an early leave with neither a parent's permission nor a named member
    of staff authorising it, and a return time earlier than the
    departure.
    """
    init_db()
    student = _require_student(student_id)
    reason = validate_reason(reason)
    date = core._validate_date(date or _today())
    at_time = reg._validate_time(at_time or _now_time(), "Time out")
    detail = (detail or "").strip() or None
    if reason in DETAIL_REQUIRED and not detail:
        raise ValidationError(f"{reason} needs a few words of detail")

    returning = reason not in NO_RETURN
    if expected_back:
        expected_back = reg._validate_time(expected_back, "Expected back")
        if not returning:
            raise ValidationError(
                "Early leave is for the rest of the day — use Appointment "
                "or Other if the learner is coming back")
        if _minutes(expected_back) <= _minutes(at_time):
            raise ValidationError(
                f"Expected back ({expected_back}) must be after the time "
                f"out ({at_time})")
    else:
        expected_back = None

    authorised_by = (authorised_by or "").strip() or None
    permission_from = (permission_from or "").strip() or None
    if reason == EARLY_LEAVE and not parent_permission and not authorised_by:
        raise ValidationError(
            "Early leave needs either a parent's permission or a member of "
            "staff named as authorising it")
    if parent_permission and not permission_from:
        permission_from = "Parent/carer"

    existing = open_signout_for(student.student_id)
    if existing is not None:
        raise ValidationError(
            f"{student.student_id} is already signed out ({existing.reason} "
            f"at {existing.out_time}) — sign them back in first")

    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO attendance_signouts
                   (student_id, date, out_time, reason, detail,
                    parent_permission, permission_from, authorised_by,
                    expected_back, will_return, state, signed_out_via,
                    recorded_by, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (student.student_id, date, at_time, reason, detail,
             1 if parent_permission else 0, permission_from, authorised_by,
             expected_back, 1 if returning else 0,
             OUT if returning else LEFT_FOR_DAY,
             (via or "").strip() or None,
             (recorded_by or "").strip() or None,
             (notes or "").strip() or None))
        conn.commit()
        signout_id = int(cur.lastrowid or 0)

    if not returning:
        stamped = _stamp_early_leave(student.student_id, date, at_time,
                                     reason=detail, actor=recorded_by)
        logger.info("Early leave: %s at %s (%d lesson(s) stamped)",
                    student.student_id, at_time, stamped)
    else:
        logger.info("Signed out: %s at %s (%s, back %s)", student.student_id,
                    at_time, reason, expected_back or "?")
    out = get_signout(signout_id)
    assert out is not None
    return out


def _stamp_early_leave(student_id: str, date: str, at_time: str, *,
                       reason: str | None, actor: str | None) -> int:
    """Put the departure on the lesson the learner leaves part-way through.

    ``record_departure`` only accepts a time inside the lesson, so later
    lessons are left for the register — the teacher marks them absent and
    the sign-out explains why.
    """
    stamped = 0
    for record in core.list_records(student_id=student_id, date=date):
        if record.voided or record.departure_time:
            continue
        try:
            start, end = reg.slot_window(record.slot_id)
        except ValidationError:
            continue
        if _minutes(start) <= _minutes(at_time) < _minutes(end):
            try:
                reg.record_departure(record.slot_id, date, student_id,
                                     at_time, reason=reason or EARLY_LEAVE,
                                     actor=actor)
                stamped += 1
            except ValidationError as e:
                logger.debug("Could not stamp departure on slot #%d: %s",
                             record.slot_id, e)
    return stamped


def sign_in(
    student_id: str,
    *,
    via: str | None = None,
    at_time: str | None = None,
    notes: str | None = None,
) -> SignOut:
    """Close the learner's open sign-out. Raises if they are not out."""
    init_db()
    open_row = open_signout_for((student_id or "").strip())
    if open_row is None:
        raise ValidationError(f"{student_id} is not signed out")
    at_time = reg._validate_time(at_time or _now_time(), "Time in")
    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_signouts
                  SET state = ?, in_time = ?, signed_in_via = ?,
                      notes = COALESCE(?, notes)
                WHERE signout_id = ?""",
            (BACK, at_time, (via or "").strip() or None,
             (notes or "").strip() or None, open_row.signout_id))
        conn.commit()
    logger.info("Signed back in: %s at %s", student_id, at_time)
    out = get_signout(open_row.signout_id)
    assert out is not None
    return out


def sign_in_if_out(student_id: str, *, via: str | None = None,
                   at_time: str | None = None) -> SignOut | None:
    """Sign in when there is an open sign-out; otherwise do nothing.

    For the entrance kiosk, which must never raise at the door.
    """
    try:
        if open_signout_for(student_id) is None:
            return None
        return sign_in(student_id, via=via, at_time=at_time)
    except ValidationError as e:
        logger.debug("Auto sign-in skipped for %s: %s", student_id, e)
        return None


def toggle(student_id: str, *, reason: str = FREE_PERIOD,
           via: str | None = None, at_time: str | None = None
           ) -> tuple[str, SignOut]:
    """One tap at a sign-out terminal: out if in, in if out.

    Returns ``("in" | "out", the sign-out)``. Only reasons that need no
    detail can be used from a bare tap.
    """
    if open_signout_for(student_id) is not None:
        return "in", sign_in(student_id, via=via, at_time=at_time)
    return "out", sign_out(student_id, reason, via=via, at_time=at_time)


# ── Reads ───────────────────────────────────────────────────────────

def get_signout(signout_id: int) -> SignOut | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_signouts WHERE signout_id = ?",
            (signout_id,)).fetchone()
    return _row(r) if r else None


def open_signout_for(student_id: str, *,
                     date: str | None = None) -> SignOut | None:
    """The learner's open sign-out today, if they are off site."""
    init_db()
    date = core._validate_date(date or _today())
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_signouts WHERE student_id = ? "
            "AND date = ? AND state = ? ORDER BY signout_id DESC LIMIT 1",
            (student_id.strip(), date, OUT)).fetchone()
    return _row(r) if r else None


def list_signouts(*, date: str | None = None, date_from: str | None = None,
                  date_to: str | None = None, student_id: str | None = None,
                  state: str | None = None, reason: str | None = None,
                  limit: int = 500) -> list[SignOut]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if date:
        clauses.append("date = ?")
        args.append(core._validate_date(date))
    if date_from:
        clauses.append("date >= ?")
        args.append(core._validate_date(date_from))
    if date_to:
        clauses.append("date <= ?")
        args.append(core._validate_date(date_to))
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if state:
        if state not in STATES:
            raise ValidationError(f"State must be one of: {', '.join(STATES)}")
        clauses.append("state = ?")
        args.append(state)
    if reason:
        clauses.append("reason = ?")
        args.append(validate_reason(reason))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(max(1, int(limit)))
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_signouts {where} "
            "ORDER BY date DESC, out_time DESC, signout_id DESC LIMIT ?",
            args).fetchall()
    return _names([_row(r) for r in rows])


def currently_off_site(*, date: str | None = None,
                       at_time: str | None = None) -> list[SignOut]:
    """Everybody signed out and not yet back — the fire roll-call list.

    Includes today's early leavers (they are off site too), and with
    ``at_time`` only those who had left by then.
    """
    date = core._validate_date(date or _today())
    rows = [r for r in list_signouts(date=date, limit=5000)
            if r.state in (OUT, LEFT_FOR_DAY)]
    if at_time:
        cutoff = _minutes(reg._validate_time(at_time, "Time"))
        rows = [r for r in rows if _minutes(r.out_time) <= cutoff]
    rows.sort(key=lambda r: (r.out_time, r.student_name or r.student_id))
    return rows


def off_site_index(*, date: str | None = None,
                   at_time: str | None = None) -> dict[str, SignOut]:
    """``currently_off_site`` keyed by student id, for the roll call."""
    return {r.student_id: r for r in currently_off_site(date=date,
                                                        at_time=at_time)}


def late_returns(*, date: str | None = None, at_time: str | None = None,
                 grace_minutes: int = LATE_GRACE_MINUTES) -> list[SignOut]:
    """Learners past their expected return (plus grace), most overdue first."""
    date = core._validate_date(date or _today())
    now = reg._validate_time(at_time or _now_time(), "Time")
    rows = [r for r in list_signouts(date=date, state=OUT, limit=5000)
            if r.expected_back
            and r.minutes_overdue(at_time=now) > max(0, grace_minutes)]
    rows.sort(key=lambda r: -r.minutes_overdue(at_time=now))
    return rows


@dataclass
class LateAlertResult:
    raised: int = 0
    already: int = 0
    queued_home: int = 0

    @property
    def summary(self) -> str:
        return (f"{self.raised} late-return alert(s) raised, "
                f"{self.already} already raised, "
                f"{self.queued_home} message(s) queued home")


def raise_late_alerts(*, raised_by: str | None = None,
                      notify_guardian: bool = False,
                      date: str | None = None, at_time: str | None = None,
                      grace_minutes: int = LATE_GRACE_MINUTES
                      ) -> LateAlertResult:
    """Flag every overdue return, once each.

    The alert is stamped on the sign-out so the list shows who has been
    chased. With ``notify_guardian`` a message is queued (not sent)
    through :mod:`attendance_notifications`, de-duplicated per sign-out.
    """
    date = core._validate_date(date or _today())
    now = reg._validate_time(at_time or _now_time(), "Time")
    result = LateAlertResult()
    for row in late_returns(date=date, at_time=now,
                            grace_minutes=grace_minutes):
        if row.late_alert_at:
            result.already += 1
            continue
        with _connect() as conn:
            conn.execute(
                "UPDATE attendance_signouts SET late_alert_at = ?, "
                "late_alert_by = ? WHERE signout_id = ?",
                (f"{date} {now}", (raised_by or "").strip() or None,
                 row.signout_id))
            conn.commit()
        result.raised += 1
        logger.warning("Late return: %s due back %s, not signed in by %s",
                       row.student_id, row.expected_back, now)
        if notify_guardian:
            try:
                from education_system.systems.sixth_form.domain.academics.attendance import (  # noqa: E501
                    attendance_notifications as _notify,
                )
                queued = _notify.queue(
                    row.student_id, _notify.LATE_ALERT,
                    f"{row.student_name or row.student_id} signed out of "
                    f"college at {row.out_time} ({row.reason}) and was due "
                    f"back at {row.expected_back}, but has not signed back "
                    "in. Please contact the college.",
                    subject="Not back on site",
                    covers_date=date,
                    dedupe_key=f"signout:{row.signout_id}")
                if queued is not None:
                    result.queued_home += 1
            except Exception:               # pragma: no cover - optional dep
                logger.exception("Could not queue late-return message for %s",
                                 row.student_id)
    return result


def outstanding_alerts(*, date: str | None = None) -> list[SignOut]:
    """Late-return alerts raised today where the learner is still out."""
    return [r for r in list_signouts(date=date or _today(), state=OUT,
                                     limit=5000) if r.late_alert_at]


def day_summary(*, date: str | None = None) -> dict[str, int]:
    """Today's sign-outs counted by reason, plus who is out now."""
    rows = list_signouts(date=date or _today(), limit=5000)
    out: dict[str, int] = {}
    for row in rows:
        out[row.reason] = out.get(row.reason, 0) + 1
    out["Off site now"] = sum(1 for r in rows if r.is_out)
    out["Left for the day"] = sum(1 for r in rows if r.state == LEFT_FOR_DAY)
    out["Late-return alerts"] = sum(1 for r in rows if r.late_alert_at)
    return out


def without_permission(*, date_from: str | None = None,
                       date_to: str | None = None) -> list[SignOut]:
    """Sign-outs with no parent permission recorded — for review."""
    return [r for r in list_signouts(date_from=date_from, date_to=date_to,
                                     limit=5000)
            if not r.parent_permission]
