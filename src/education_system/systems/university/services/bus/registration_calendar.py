"""Registration periods and add/drop deadlines.

``academic_terms`` records when teaching runs (start_date/end_date) but nothing
recorded when *registration* runs: when it opens, when late additions stop,
after which date a drop becomes a transcript-visible withdrawal, and after
which date a student cannot leave a module unilaterally at all. Every
enrolment was therefore accepted whatever the date, every drop was recorded as
plain ``Dropped``, and nothing captured *when* a drop happened relative to a
deadline — all 198 rows in ``student_modules`` read ``Enrolled``.

This module owns those dates and the two verdicts derived from them:

``registration_state(...)``  may an enrolment be accepted right now?
``classify_drop(...)``       is leaving a module a Drop, a Withdrawal, or
                             something that needs the formal process?

Both fail **open when unconfigured**: with no period rows — the state today —
registration behaves exactly as it did before. Configure a period and the
deadlines start applying. Every status change is recorded in
``enrolment_status_changes`` with the deadline context that produced it, so
"when did they drop, and was it before the deadline?" becomes answerable.

Dates are ISO ``YYYY-MM-DD`` strings, compared as dates; a period may leave
any deadline blank, in which case the next one out is used (a blank
``add_deadline`` means additions run to ``registration_closes``).
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Optional

from education_system.systems.university.infrastructure.database.db import (
    sqlite3,
    get_connection,
)

logger = logging.getLogger(__name__)

# Phases of the registration cycle.
PHASE_UNCONFIGURED = "unconfigured"   # no period defined — everything allowed
PHASE_BEFORE_OPEN = "before_open"     # registration has not opened yet
PHASE_OPEN = "open"                   # normal registration
PHASE_LATE_ADD = "late_add"           # past add deadline, late adds permitted
PHASE_CLOSED = "closed"               # registration has closed

# What leaving a module means at a given date.
DROP_CLEAN = "Dropped"                # before the drop deadline; no record
DROP_WITHDRAWN = "Withdrawn"          # after it; shows on the transcript
DROP_REFUSED = "refused"              # past the withdrawal deadline

_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS registration_periods (
        period_id           INTEGER PRIMARY KEY AUTOINCREMENT,
        term_id             INTEGER,
        academic_year       TEXT NOT NULL DEFAULT '',
        name                TEXT NOT NULL DEFAULT '',
        registration_opens  TEXT NOT NULL,
        registration_closes TEXT NOT NULL,
        add_deadline        TEXT,
        drop_deadline       TEXT,
        withdraw_deadline   TEXT,
        late_add_allowed    INTEGER NOT NULL DEFAULT 0,
        is_active           INTEGER NOT NULL DEFAULT 1,
        notes               TEXT,
        created_at          TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS enrolment_status_changes (
        change_id        INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id       TEXT NOT NULL,
        module_code      TEXT NOT NULL,
        from_status      TEXT,
        to_status        TEXT NOT NULL,
        changed_at       TEXT NOT NULL DEFAULT (datetime('now')),
        changed_by       TEXT,
        period_id        INTEGER,
        phase            TEXT,
        deadline_applied TEXT,
        source           TEXT,
        note             TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_enrolment_changes_student "
    "ON enrolment_status_changes (student_id, module_code)",
    "CREATE INDEX IF NOT EXISTS idx_registration_periods_active "
    "ON registration_periods (is_active, registration_opens)",
)


def ensure_schema(conn=None) -> bool:
    """Create the period and audit tables. Idempotent; safe to call often."""
    own = conn is None
    try:
        if own:
            conn = get_connection()
        for stmt in _SCHEMA:
            conn.execute(stmt)
        conn.commit()
        return True
    except Exception as exc:
        logger.warning("registration calendar schema init failed: %s", exc)
        return False
    finally:
        if own and conn is not None:
            try:
                conn.close()
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------

def _as_date(value) -> Optional[date]:
    """Parse an ISO date (or datetime) string; None when absent or unparseable."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text[:len(fmt) + 2].strip(), fmt).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        logger.debug("unparseable registration date: %r", value)
        return None


def _today(when=None) -> date:
    return _as_date(when) or date.today()


# ---------------------------------------------------------------------------
# Periods
# ---------------------------------------------------------------------------

def current_period(*, when=None, term_id: Optional[int] = None, conn=None) -> Optional[dict]:
    """The period governing *when*.

    The rule is "the most recent period that has started", falling back to the
    soonest period still ahead. A period must keep governing after its last
    deadline passes: picking only periods whose window *contains* the date
    meant that the day after the withdrawal deadline the period vanished, the
    calendar read as unconfigured, and late withdrawals were waved through as
    ordinary drops. Pass ``term_id`` to ask about a specific term instead.
    """
    today = _today(when)
    own = conn is None
    try:
        if own:
            conn = get_connection()
        ensure_schema(conn)
        clause = "WHERE is_active = 1"
        params: list[Any] = []
        if term_id is not None:
            clause += " AND (term_id = ? OR term_id IS NULL)"
            params.append(term_id)
        rows = conn.execute(
            "SELECT period_id, term_id, academic_year, name, registration_opens, "
            "registration_closes, add_deadline, drop_deadline, withdraw_deadline, "
            "late_add_allowed FROM registration_periods "
            f"{clause} ORDER BY registration_opens",
            params,
        ).fetchall()
    except Exception as exc:
        logger.warning("registration period lookup failed: %s", exc)
        return None
    finally:
        if own and conn is not None:
            try:
                conn.close()
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

    periods = [_row_to_period(r) for r in rows]  # ordered by registration_opens
    started = [p for p in periods
               if (_as_date(p["registration_opens"]) or today) <= today]
    if started:
        return started[-1]
    upcoming = [p for p in periods
                if (_as_date(p["registration_opens"]) or today) > today]
    return upcoming[0] if upcoming else None


def _row_to_period(row) -> dict:
    keys = ("period_id", "term_id", "academic_year", "name", "registration_opens",
            "registration_closes", "add_deadline", "drop_deadline",
            "withdraw_deadline", "late_add_allowed")
    if hasattr(row, "keys"):
        return {k: row[k] for k in keys}
    return dict(zip(keys, row))


def add_period(*, academic_year: str, registration_opens: str, registration_closes: str,
               name: str = "", term_id: Optional[int] = None,
               add_deadline: Optional[str] = None, drop_deadline: Optional[str] = None,
               withdraw_deadline: Optional[str] = None, late_add_allowed: bool = False,
               notes: str = "", conn=None) -> Optional[int]:
    """Define a registration period. Returns its id."""
    own = conn is None
    try:
        if own:
            conn = get_connection()
        ensure_schema(conn)
        cur = conn.execute(
            "INSERT INTO registration_periods (term_id, academic_year, name, "
            "registration_opens, registration_closes, add_deadline, drop_deadline, "
            "withdraw_deadline, late_add_allowed, notes) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (term_id, academic_year, name, registration_opens, registration_closes,
             add_deadline, drop_deadline, withdraw_deadline,
             1 if late_add_allowed else 0, notes),
        )
        conn.commit()
        return cur.lastrowid
    except Exception as exc:
        logger.warning("could not add registration period: %s", exc)
        return None
    finally:
        if own and conn is not None:
            try:
                conn.close()
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)


# ---------------------------------------------------------------------------
# Verdicts
# ---------------------------------------------------------------------------

def registration_state(*, when=None, term_id: Optional[int] = None, conn=None) -> dict[str, Any]:
    """May an enrolment be accepted now?

    Returns ``{open, phase, reason, period, deadline}``. With no period
    configured the phase is ``unconfigured`` and ``open`` is True — the
    behaviour before this module existed.
    """
    today = _today(when)
    period = current_period(when=today, term_id=term_id, conn=conn)
    if not period:
        return {"open": True, "phase": PHASE_UNCONFIGURED, "reason": "",
                "period": None, "deadline": None}

    opens = _as_date(period["registration_opens"])
    closes = _as_date(period["registration_closes"])
    add_deadline = _as_date(period["add_deadline"]) or closes
    label = period["name"] or period["academic_year"] or "this term"

    if opens and today < opens:
        return {"open": False, "phase": PHASE_BEFORE_OPEN, "period": period,
                "deadline": opens.isoformat(),
                "reason": f"Registration for {label} opens on {opens.isoformat()}."}

    if add_deadline and today > add_deadline:
        if period["late_add_allowed"] and closes and today <= closes:
            return {"open": True, "phase": PHASE_LATE_ADD, "period": period,
                    "deadline": closes.isoformat(),
                    "reason": f"Late registration — the add deadline "
                              f"({add_deadline.isoformat()}) has passed."}
        return {"open": False, "phase": PHASE_CLOSED, "period": period,
                "deadline": add_deadline.isoformat(),
                "reason": f"Registration for {label} closed on "
                          f"{add_deadline.isoformat()}."}

    return {"open": True, "phase": PHASE_OPEN, "period": period,
            "deadline": add_deadline.isoformat() if add_deadline else None,
            "reason": ""}


def classify_drop(*, when=None, term_id: Optional[int] = None, conn=None) -> dict[str, Any]:
    """What does leaving a module mean at this date?

    ``status`` is the value to write to ``student_modules.status``:
    ``Dropped`` before the drop deadline (no academic record), ``Withdrawn``
    between the drop and withdrawal deadlines (transcript-visible), and
    ``allowed=False`` after the withdrawal deadline, where leaving needs the
    formal process rather than a self-service click.
    """
    today = _today(when)
    period = current_period(when=today, term_id=term_id, conn=conn)
    if not period:
        return {"allowed": True, "status": DROP_CLEAN, "phase": PHASE_UNCONFIGURED,
                "reason": "", "period": None, "deadline": None,
                "on_transcript": False}

    drop_deadline = _as_date(period["drop_deadline"])
    withdraw_deadline = _as_date(period["withdraw_deadline"])

    if drop_deadline and today <= drop_deadline:
        return {"allowed": True, "status": DROP_CLEAN, "phase": PHASE_OPEN,
                "period": period, "deadline": drop_deadline.isoformat(),
                "on_transcript": False,
                "reason": f"Dropped before the deadline of {drop_deadline.isoformat()};"
                          " it will not appear on the transcript."}

    if withdraw_deadline and today <= withdraw_deadline:
        return {"allowed": True, "status": DROP_WITHDRAWN, "phase": PHASE_CLOSED,
                "period": period, "deadline": withdraw_deadline.isoformat(),
                "on_transcript": True,
                "reason": "The drop deadline"
                          + (f" ({drop_deadline.isoformat()})" if drop_deadline else "")
                          + " has passed, so this is recorded as a withdrawal and"
                            " will appear on the transcript."}

    if withdraw_deadline and today > withdraw_deadline:
        return {"allowed": False, "status": DROP_REFUSED, "phase": PHASE_CLOSED,
                "period": period, "deadline": withdraw_deadline.isoformat(),
                "on_transcript": True,
                "reason": f"The withdrawal deadline ({withdraw_deadline.isoformat()})"
                          " has passed. Leaving this module now needs approval"
                          " through the formal withdrawal process."}

    # A period with no drop dates configured: treat as an ordinary drop.
    return {"allowed": True, "status": DROP_CLEAN, "phase": PHASE_OPEN,
            "period": period, "deadline": None, "on_transcript": False, "reason": ""}


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

def record_status_change(student_id, module_code, to_status, *, from_status=None,
                         changed_by=None, source=None, verdict: Optional[dict] = None,
                         note: str = "", conn=None) -> Optional[int]:
    """Record an enrolment status change with the deadline context behind it.

    ``verdict`` is the dict from ``registration_state`` / ``classify_drop``;
    its phase, period and deadline are stored so a later query can answer
    whether a drop was inside the window without recomputing history from
    dates that may since have been edited.
    """
    own = conn is None
    try:
        if own:
            conn = get_connection()
        ensure_schema(conn)
        period = (verdict or {}).get("period") or {}
        cur = conn.execute(
            "INSERT INTO enrolment_status_changes (student_id, module_code, "
            "from_status, to_status, changed_by, period_id, phase, "
            "deadline_applied, source, note) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (str(student_id), module_code, from_status, to_status,
             str(changed_by) if changed_by else None,
             period.get("period_id"), (verdict or {}).get("phase"),
             (verdict or {}).get("deadline"), source, note),
        )
        conn.commit()
        return cur.lastrowid
    except Exception as exc:
        logger.warning("could not record enrolment status change: %s", exc)
        return None
    finally:
        if own and conn is not None:
            try:
                conn.close()
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)


def history_for(student_id, module_code: Optional[str] = None, *, conn=None) -> list[dict]:
    """Recorded status changes for a student, newest first."""
    own = conn is None
    try:
        if own:
            conn = get_connection()
        ensure_schema(conn)
        sql = ("SELECT change_id, student_id, module_code, from_status, to_status, "
               "changed_at, changed_by, period_id, phase, deadline_applied, source, note "
               "FROM enrolment_status_changes WHERE student_id = ?")
        params: list[Any] = [str(student_id)]
        if module_code:
            sql += " AND module_code = ?"
            params.append(module_code)
        sql += " ORDER BY changed_at DESC, change_id DESC"
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) if hasattr(r, "keys") else r for r in rows]
    except Exception as exc:
        logger.warning("enrolment history lookup failed: %s", exc)
        return []
    finally:
        if own and conn is not None:
            try:
                conn.close()
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)
