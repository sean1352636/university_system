"""Retro-marking window for Sixth Form Attendance.

Sibling to :mod:`attendance`. Answers one question every write path has
to ask: *is this register still young enough to be edited like a
register, or is it now history?*

A register that was taken six weeks ago is evidence. It can still be
corrected — a doctor's note turns up late, a learner was marked against
the wrong class — but the correction should be a deliberate, reasoned,
attributable act, not a silent overwrite by somebody who happened to
open last half-term's roster and hit save. So a date passes through
three states as it ages:

* **Open** — inside ``open_days``. Ordinary register-taking. No ceremony.
* **Reason required** — past ``open_days`` but inside ``close_days``. A
  write still goes through, but only if the caller says why, and the
  amendment trail in :mod:`attendance_audit` records the change.
* **Closed** — past ``close_days``. Refused outright. The only way
  through is an explicit retrospective correction (``allow_retro``),
  which is logged with the actor who forced it.

Dates in the *future* get the same treatment from the other end: marking
a known absence for next week is normal (study leave, a booked trip), so
that is allowed up to ``future_days``, which exists to catch the typo
that puts a register in 2035.

**What this does not police.** The curated amendment paths — authorising
an absence, recoding a mark, voiding a row — pass ``allow_retro`` and go
through, because each of them already stamps who did it and writes to
the amendment trail. That is the whole point: after the window closes,
those paths are the *only* way in. Statutory AM/PM session marks in
:mod:`attendance_sessions` are likewise outside this policy — they are
derived from lesson marks and re-run over historical windows by design.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

# The states a date can be in. `Open` is the only one that needs no
# justification; `Closed` is the only one that refuses outright.
OPEN: str = "Open"
REASON_REQUIRED: str = "Reason required"
CLOSED: str = "Closed"
TOO_FAR_AHEAD: str = "Too far ahead"

STATES: tuple[str, ...] = (OPEN, REASON_REQUIRED, CLOSED, TOO_FAR_AHEAD)

# Shipped defaults. Two working weeks of free editing covers the usual
# "I forgot to submit Thursday"; two months of reasoned amendment covers
# a late medical note; past that a correction should be a decision
# somebody's name is on.
DEFAULT_OPEN_DAYS: int = 14
DEFAULT_CLOSE_DAYS: int = 60
DEFAULT_FUTURE_DAYS: int = 180

# Nothing outside these bounds is a policy, it is a mistake.
_MAX_DAYS: int = 3650

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_window_policy (
    policy_id   INTEGER PRIMARY KEY CHECK (policy_id = 1),
    enabled     INTEGER NOT NULL DEFAULT 1,
    open_days   INTEGER NOT NULL DEFAULT 14,
    close_days  INTEGER NOT NULL DEFAULT 60,
    future_days INTEGER NOT NULL DEFAULT 180,
    updated_at  TEXT DEFAULT (datetime('now')),
    updated_by  TEXT
);

CREATE TABLE IF NOT EXISTS attendance_window_overrides (
    override_id INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    slot_id     INTEGER,
    actor       TEXT,
    days_late   INTEGER NOT NULL,
    state       TEXT NOT NULL,
    reason      TEXT,
    source      TEXT,
    recorded_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_att_window_ovr_date
    ON attendance_window_overrides(date);
CREATE INDEX IF NOT EXISTS idx_att_window_ovr_actor
    ON attendance_window_overrides(actor);
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class WindowPolicy:
    """The college's retro-marking rules."""

    enabled: bool = True
    open_days: int = DEFAULT_OPEN_DAYS
    close_days: int = DEFAULT_CLOSE_DAYS
    future_days: int = DEFAULT_FUTURE_DAYS
    updated_at: str | None = None
    updated_by: str | None = None

    @property
    def summary(self) -> str:
        if not self.enabled:
            return "Retro-marking window disabled — any date can be edited."
        return (f"Free editing for {self.open_days} day(s); reasoned "
                f"amendment to {self.close_days} day(s); closed after that. "
                f"Up to {self.future_days} day(s) ahead.")


@dataclass
class WindowDecision:
    """What the policy says about one date."""

    date: str
    days_late: int          # negative for a future date
    state: str
    allowed: bool
    requires_reason: bool
    message: str

    @property
    def is_open(self) -> bool:
        return self.state == OPEN

    @property
    def is_future(self) -> bool:
        return self.days_late < 0


@dataclass
class Override:
    """One write that was forced through a closed window."""

    override_id: int
    date: str
    slot_id: int | None
    actor: str | None
    days_late: int
    state: str
    reason: str | None
    source: str | None
    recorded_at: str | None


@dataclass
class ClosingSoon:
    """A register whose free-editing window runs out shortly."""

    slot_id: int
    date: str
    state: str            # the register's own Draft/Submitted state
    closes_on: str
    days_remaining: int


# ── DB plumbing ─────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    core.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.execute(
            "INSERT OR IGNORE INTO attendance_window_policy "
            "(policy_id, enabled, open_days, close_days, future_days) "
            "VALUES (1, 1, ?, ?, ?)",
            (DEFAULT_OPEN_DAYS, DEFAULT_CLOSE_DAYS, DEFAULT_FUTURE_DAYS))
        conn.commit()
    logger.debug("Attendance window schema ready at %s", DB_PATH)
    _DB_READY = True


# ── Policy ──────────────────────────────────────────────────────────

def _validate_days(value: Any, label: str, *, minimum: int = 0) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a whole number") from None
    if n < minimum or n > _MAX_DAYS:
        raise ValidationError(
            f"{label} must be between {minimum} and {_MAX_DAYS}")
    return n


def get_policy() -> WindowPolicy:
    """The current rules, falling back to the shipped defaults."""
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_window_policy WHERE policy_id = 1"
        ).fetchone()
    if r is None:                              # pragma: no cover - defensive
        return WindowPolicy()
    return WindowPolicy(
        enabled=bool(r["enabled"]),
        open_days=r["open_days"],
        close_days=r["close_days"],
        future_days=r["future_days"],
        updated_at=r["updated_at"],
        updated_by=r["updated_by"],
    )


def set_policy(
    *,
    enabled: bool | None = None,
    open_days: int | None = None,
    close_days: int | None = None,
    future_days: int | None = None,
    actor: str | None = None,
) -> WindowPolicy:
    """Change the rules. Anything left out keeps its current value."""
    init_db()
    current = get_policy()
    new_open = (current.open_days if open_days is None
                else _validate_days(open_days, "Open days"))
    new_close = (current.close_days if close_days is None
                 else _validate_days(close_days, "Close days"))
    new_future = (current.future_days if future_days is None
                  else _validate_days(future_days, "Future days"))
    if new_close < new_open:
        # Otherwise there is a band of dates that are simultaneously past
        # the amendment cutoff and inside the free-editing window.
        raise ValidationError(
            f"Close days ({new_close}) cannot be less than open days "
            f"({new_open})")
    new_enabled = current.enabled if enabled is None else bool(enabled)

    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_window_policy
                  SET enabled = ?, open_days = ?, close_days = ?,
                      future_days = ?, updated_at = datetime('now'),
                      updated_by = ?
                WHERE policy_id = 1""",
            (1 if new_enabled else 0, new_open, new_close, new_future,
             (actor or "").strip() or None))
        conn.commit()
    logger.info("Attendance window policy set: open=%d close=%d future=%d "
                "enabled=%s by %s", new_open, new_close, new_future,
                new_enabled, actor or "?")
    return get_policy()


def reset_policy(*, actor: str | None = None) -> WindowPolicy:
    """Put the shipped defaults back."""
    return set_policy(enabled=True, open_days=DEFAULT_OPEN_DAYS,
                      close_days=DEFAULT_CLOSE_DAYS,
                      future_days=DEFAULT_FUTURE_DAYS, actor=actor)


# ── Evaluation ──────────────────────────────────────────────────────

def _today() -> _dt.date:
    return _dt.date.today()


def days_late(date: str, *, today: str | None = None) -> int:
    """How many days old a register date is. Negative means the future."""
    target = _dt.date.fromisoformat(core._validate_date(date))
    now = (_dt.date.fromisoformat(core._validate_date(today))
           if today else _today())
    return (now - target).days


def closes_on(date: str, *, policy: WindowPolicy | None = None) -> str:
    """The last date on which ``date`` can be freely edited."""
    policy = policy or get_policy()
    target = _dt.date.fromisoformat(core._validate_date(date))
    return (target + _dt.timedelta(days=policy.open_days)).isoformat()


def final_deadline(date: str, *, policy: WindowPolicy | None = None) -> str:
    """The last date on which ``date`` can be amended at all."""
    policy = policy or get_policy()
    target = _dt.date.fromisoformat(core._validate_date(date))
    return (target + _dt.timedelta(days=policy.close_days)).isoformat()


def evaluate(
    date: str,
    *,
    reason: str | None = None,
    today: str | None = None,
    policy: WindowPolicy | None = None,
) -> WindowDecision:
    """Classify a register date against the policy.

    Pure: nothing is written and nothing is raised, so a UI can call this
    to grey out a save button before the user reaches for it.
    """
    date = core._validate_date(date)
    policy = policy or get_policy()
    late = days_late(date, today=today)
    has_reason = bool((reason or "").strip())

    if not policy.enabled:
        return WindowDecision(
            date=date, days_late=late, state=OPEN, allowed=True,
            requires_reason=False,
            message="Retro-marking window is disabled.")

    if late < 0:
        ahead = -late
        if ahead > policy.future_days:
            return WindowDecision(
                date=date, days_late=late, state=TOO_FAR_AHEAD,
                allowed=False, requires_reason=False,
                message=(f"{date} is {ahead} day(s) ahead — registers can "
                         f"only be marked up to {policy.future_days} day(s) "
                         f"in advance. Check the date."))
        return WindowDecision(
            date=date, days_late=late, state=OPEN, allowed=True,
            requires_reason=False,
            message=f"{date} is {ahead} day(s) ahead, which is allowed.")

    if late <= policy.open_days:
        return WindowDecision(
            date=date, days_late=late, state=OPEN, allowed=True,
            requires_reason=False,
            message=(f"{date} is {late} day(s) old and still open "
                     f"(closes on {closes_on(date, policy=policy)})."))

    if late <= policy.close_days:
        return WindowDecision(
            date=date, days_late=late, state=REASON_REQUIRED,
            allowed=has_reason, requires_reason=True,
            message=(f"{date} is {late} day(s) old — past the "
                     f"{policy.open_days}-day editing window. An amendment "
                     f"needs a reason; it will be recorded against your "
                     f"name."))

    return WindowDecision(
        date=date, days_late=late, state=CLOSED, allowed=False,
        requires_reason=True,
        message=(f"{date} is {late} day(s) old and past the "
                 f"{policy.close_days}-day amendment cutoff. Only a "
                 f"retrospective correction can change it now."))


def is_open(date: str, *, today: str | None = None) -> bool:
    """Whether ordinary register-taking is still allowed for a date."""
    return evaluate(date, today=today).state == OPEN


def assert_open(
    date: str,
    *,
    reason: str | None = None,
    actor: str | None = None,
    slot_id: int | None = None,
    allow_retro: bool = False,
    source: str | None = None,
    today: str | None = None,
) -> WindowDecision:
    """Gate a write. Raises ``ValidationError`` when the policy says no.

    ``allow_retro`` is the deliberate override used by the curated
    amendment paths and by bulk historical import. It never silently
    succeeds: every use is written to the override log with the actor,
    so "who backdated this register" has an answer.
    """
    decision = evaluate(date, reason=reason, today=today)
    if decision.state == OPEN:
        return decision

    if allow_retro:
        _log_override(decision, actor=actor, slot_id=slot_id,
                      reason=reason, source=source)
        return decision

    if decision.allowed:
        # Reason-required band, and a reason was given.
        _log_override(decision, actor=actor, slot_id=slot_id,
                      reason=reason, source=source)
        return decision

    raise ValidationError(decision.message)


# ── Override log ────────────────────────────────────────────────────

def _log_override(
    decision: WindowDecision,
    *,
    actor: str | None,
    slot_id: int | None,
    reason: str | None,
    source: str | None,
) -> int:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO attendance_window_overrides
                   (date, slot_id, actor, days_late, state, reason, source)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (decision.date, slot_id, (actor or "").strip() or None,
             decision.days_late, decision.state,
             (reason or "").strip() or None,
             (source or "").strip() or None))
        conn.commit()
    logger.info("Retro write allowed: %s (%d day(s) old, %s) by %s",
                decision.date, decision.days_late, decision.state,
                actor or "?")
    return int(cur.lastrowid or 0)


def _row_override(r: sqlite3.Row) -> Override:
    return Override(
        override_id=r["override_id"],
        date=r["date"],
        slot_id=r["slot_id"],
        actor=r["actor"],
        days_late=r["days_late"],
        state=r["state"],
        reason=r["reason"],
        source=r["source"],
        recorded_at=r["recorded_at"],
    )


def list_overrides(
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    actor: str | None = None,
    state: str | None = None,
    limit: int = 200,
) -> list[Override]:
    """The retro-write log — who edited history, when, and why."""
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if date_from:
        clauses.append("date >= ?")
        args.append(core._validate_date(date_from))
    if date_to:
        clauses.append("date <= ?")
        args.append(core._validate_date(date_to))
    if actor:
        clauses.append("actor = ?")
        args.append(actor.strip())
    if state:
        if state not in STATES:
            raise ValidationError(f"State must be one of: {', '.join(STATES)}")
        clauses.append("state = ?")
        args.append(state)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(max(1, int(limit)))
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_window_overrides {where} "
            "ORDER BY override_id DESC LIMIT ?", args).fetchall()
    return [_row_override(r) for r in rows]


def override_count(**kwargs: Any) -> int:
    kwargs.setdefault("limit", _MAX_DAYS)
    return len(list_overrides(**kwargs))


# ── Chase list ──────────────────────────────────────────────────────

def closing_soon(
    *,
    within_days: int = 3,
    include_submitted: bool = False,
    today: str | None = None,
) -> list[ClosingSoon]:
    """Registers whose free-editing window runs out shortly.

    The point of a deadline nobody can see is lost, so this is what a
    dashboard shows on a Monday morning: fix these before they need a
    reason and a signature.
    """
    init_db()
    # The register headers live next door; late-imported because that
    # module's write paths call back into this one.
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_register as _reg,
    )
    _reg.init_db()
    policy = get_policy()
    within = _validate_days(within_days, "Within days")
    now = (_dt.date.fromisoformat(core._validate_date(today))
           if today else _today())
    # Only dates that are still open can be *closing*; anything older is
    # already past it.
    oldest = (now - _dt.timedelta(days=policy.open_days)).isoformat()
    newest = (now - _dt.timedelta(
        days=max(0, policy.open_days - within))).isoformat()

    with _connect() as conn:
        rows = conn.execute(
            "SELECT slot_id, date, state FROM register_sessions "
            "WHERE date >= ? AND date <= ? ORDER BY date, slot_id",
            (oldest, newest)).fetchall()

    out: list[ClosingSoon] = []
    for r in rows:
        if not include_submitted and r["state"] == "Submitted":
            continue
        deadline = closes_on(r["date"], policy=policy)
        remaining = (_dt.date.fromisoformat(deadline) - now).days
        if remaining < 0:
            continue
        out.append(ClosingSoon(
            slot_id=r["slot_id"], date=r["date"], state=r["state"],
            closes_on=deadline, days_remaining=remaining))
    out.sort(key=lambda c: (c.days_remaining, c.date, c.slot_id))
    return out


def describe(date: str, *, today: str | None = None) -> str:
    """One line a CLI or tooltip can print about a date."""
    decision = evaluate(date, today=today)
    return f"{decision.state}: {decision.message}"
