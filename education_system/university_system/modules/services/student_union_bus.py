"""Cross-domain Student Union services.

The SU sits semi-autonomously alongside the university — it has its
own clubs, events, elections, advocacy team. We don't auto-feed it
every disciplinary case (privacy), but we do let it plug into the
shared infra (calendar, finance, DM, cases_bus) on a per-action
basis when the student opts in or the SU initiates.

Public surface:

* Membership: ``list_clubs_for``, ``is_member_of``, ``join_club``,
  ``leave_club``  (publishes ``EVENT_MEMBERSHIP_CHANGED``).
* Finance:    ``charge_membership_fee`` — wraps finance_bus.raise_charge.
* Advocacy:   ``request_advocacy``, ``record_advocacy``, plus a
  hook for ``schedule_hearing`` to add SU support attendees.
* Events:     ``publish_event`` — writes to the academic calendar,
  fires ``EVENT_CALENDAR_CHANGED``.
* Internal discipline: handled via existing cases_bus
  (``kind='su_internal'``).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from education_system.university_system.infrastructure.database.db import (
    sqlite3, get_connection,
)

logger = logging.getLogger(__name__)


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS su_advocacy_requests (
    request_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL,
    case_id      INTEGER NOT NULL,
    case_kind    TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending',
    su_rep_id    TEXT,
    requested_at TEXT NOT NULL,
    claimed_at   TEXT,
    notes        TEXT
)
"""

_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_su_advocacy_student "
    "ON su_advocacy_requests(student_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_su_advocacy_case "
    "ON su_advocacy_requests(case_id, case_kind)",
)


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA_SQL)
    for sql in _INDEX_SQL:
        conn.execute(sql)


def _publish(event: str, **payload: Any) -> None:
    try:
        from education_system.university_system.modules.domain.academics.gui._event_bus import publish
        publish(event, **payload)
    except Exception as exc:
        logger.debug("su bus publish failed: %s", exc)


# ---------------------------------------------------------------------------
# Membership
# ---------------------------------------------------------------------------

def list_clubs_for(student_id: str | int) -> list[dict[str, Any]]:
    """Return clubs the student is currently a member of."""
    if not student_id:
        return []
    out: list[dict[str, Any]] = []
    try:
        with get_connection() as conn:
            for r in conn.execute(
                "SELECT cm.id AS membership_id, cm.club_id, cm.join_date, "
                "       cm.status, c.name, c.category "
                "FROM club_memberships cm "
                "LEFT JOIN student_union_clubs c ON c.id = cm.club_id "
                "WHERE cm.student_id = ? "
                "  AND LOWER(COALESCE(cm.status, 'active')) = 'active' "
                "ORDER BY cm.join_date DESC",
                (str(student_id),),
            ).fetchall():
                out.append(dict(r))
    except Exception as exc:
        logger.warning("list_clubs_for(%s) failed: %s", student_id, exc)
    return out


def is_member_of(student_id: str | int, club_id: int) -> bool:
    if not student_id or not club_id:
        return False
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM club_memberships "
                "WHERE student_id = ? AND club_id = ? "
                "  AND LOWER(COALESCE(status, 'active')) = 'active' LIMIT 1",
                (str(student_id), int(club_id)),
            ).fetchone()
            return row is not None
    except Exception as exc:
        logger.warning("is_member_of(%s, %s) failed: %s",
                       student_id, club_id, exc)
        return False


def join_club(student_id: str | int, club_id: int,
              *, fee: float = 0.0) -> int | None:
    """Add a club_memberships row + (optionally) a finance charge."""
    sid = str(student_id)
    today = datetime.now().strftime("%Y-%m-%d")
    membership_id: int | None = None
    try:
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO club_memberships "
                "(club_id, student_id, join_date, status) "
                "VALUES (?, ?, ?, 'active')",
                (int(club_id), sid, today),
            )
            membership_id = cur.lastrowid
            conn.commit()
    except Exception as exc:
        logger.warning("join_club failed: %s", exc)
        return None

    _publish("su.membership.changed",
             student_id=sid, club_id=int(club_id),
             action="joined", membership_id=membership_id)

    if fee and fee > 0:
        charge_membership_fee(sid, club_id, float(fee))
    return membership_id


def leave_club(student_id: str | int, club_id: int) -> bool:
    sid = str(student_id)
    try:
        with get_connection() as conn:
            conn.execute(
                "UPDATE club_memberships SET status = 'inactive' "
                "WHERE student_id = ? AND club_id = ? "
                "  AND LOWER(COALESCE(status, 'active')) = 'active'",
                (sid, int(club_id)),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("leave_club failed: %s", exc)
        return False

    _publish("su.membership.changed",
             student_id=sid, club_id=int(club_id), action="left")
    return True


# ---------------------------------------------------------------------------
# Finance
# ---------------------------------------------------------------------------

def charge_membership_fee(student_id: str | int, club_id: int,
                          amount: float,
                          *, description: str | None = None) -> int | None:
    """Post the SU membership fee through the canonical finance writer."""
    if not amount or amount <= 0:
        return None
    try:
        from education_system.university_system.modules.services.finance_bus import (
            raise_charge,
        )
        return raise_charge(
            student_id, float(amount),
            source="su_membership",
            description=description or f"SU club membership (club:{club_id})",
            reference_id=f"club:{club_id}",
            processed_by="student_union",
        )
    except Exception as exc:
        logger.warning("charge_membership_fee failed: %s", exc)
        return None


def list_outstanding_su_charges(student_id: str | int) -> list[dict[str, Any]]:
    """Return SU-source charges within the last 12 months for display."""
    if not student_id:
        return []
    out: list[dict[str, Any]] = []
    try:
        with get_connection() as conn:
            for r in conn.execute(
                "SELECT transaction_id, amount, description, reference_id, "
                "       created_at "
                "FROM student_finance_transactions "
                "WHERE student_id = ? "
                "  AND transaction_type = 'charge' "
                "  AND COALESCE(reference_id, '') LIKE 'club:%' "
                "  AND created_at >= date('now', '-365 days') "
                "ORDER BY created_at DESC",
                (str(student_id),),
            ).fetchall():
                out.append(dict(r))
    except Exception as exc:
        logger.warning("list_outstanding_su_charges(%s) failed: %s",
                       student_id, exc)
    return out


# ---------------------------------------------------------------------------
# Advocacy (opt-in)
# ---------------------------------------------------------------------------

def request_advocacy(student_id: str | int, case_id: int,
                     case_kind: str = "disciplinary",
                     *, notes: str | None = None) -> int | None:
    """Student opts into SU representation for an open case.

    The chatbot's existing case-opened notification asks the student
    if they want this; only on user reply does this fire. SU's
    welfare team subscribes to ``EVENT_SU_ADVOCACY_REQUESTED``.
    """
    if not student_id or not case_id:
        return None
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rid: int | None = None
    try:
        with get_connection() as conn:
            _ensure_schema(conn)
            cur = conn.execute(
                "INSERT INTO su_advocacy_requests "
                "(student_id, case_id, case_kind, status, "
                " requested_at, notes) "
                "VALUES (?, ?, ?, 'pending', ?, ?)",
                (str(student_id), int(case_id), case_kind, now, notes),
            )
            rid = cur.lastrowid
            conn.commit()
    except Exception as exc:
        logger.warning("request_advocacy failed: %s", exc)
        return None

    _publish(
        "su.advocacy.requested",
        request_id=rid, student_id=str(student_id),
        case_id=int(case_id), case_kind=case_kind,
    )
    return rid


def record_advocacy(request_id: int, su_rep_id: str | int,
                    *, notes: str | None = None) -> bool:
    """SU officer claims a pending advocacy request."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with get_connection() as conn:
            _ensure_schema(conn)
            conn.execute(
                "UPDATE su_advocacy_requests "
                "SET su_rep_id = ?, status = 'claimed', claimed_at = ?, "
                "    notes = COALESCE(?, notes) "
                "WHERE request_id = ? AND status = 'pending'",
                (str(su_rep_id), now, notes, int(request_id)),
            )
            conn.commit()
        return True
    except Exception as exc:
        logger.warning("record_advocacy failed: %s", exc)
        return False


def list_advocacy_requests_for(student_id: str | int,
                               *, only_active: bool = True
                               ) -> list[dict[str, Any]]:
    if not student_id:
        return []
    out: list[dict[str, Any]] = []
    try:
        with get_connection() as conn:
            _ensure_schema(conn)
            sql = (
                "SELECT request_id, case_id, case_kind, status, "
                "       su_rep_id, requested_at, claimed_at, notes "
                "FROM su_advocacy_requests "
                "WHERE student_id = ? "
            )
            if only_active:
                sql += "AND status IN ('pending', 'claimed') "
            sql += "ORDER BY requested_at DESC"
            for r in conn.execute(sql, (str(student_id),)).fetchall():
                out.append(dict(r))
    except Exception as exc:
        logger.warning("list_advocacy_requests_for(%s) failed: %s",
                       student_id, exc)
    return out


# ---------------------------------------------------------------------------
# Events on the academic calendar
# ---------------------------------------------------------------------------

def publish_event(*, name: str, when: str,
                  location: str | None = None,
                  description: str | None = None,
                  organizer_id: str | int | None = None) -> str | None:
    """Persist an SU event as an academic_calendar_events row.

    Hits the same path H&S evacuation drills and AM/DP hearings use,
    so the SU event shows up automatically on every calendar view
    that subscribes to ``EVENT_CALENDAR_CHANGED``.
    """
    if not name or not when:
        return None
    event_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO academic_calendar_events "
                "(id, name, date, description, event_type, "
                " date_added, last_modified, created_by) "
                "VALUES (?, ?, ?, ?, 'su_event', ?, ?, ?)",
                (event_id, name, when[:10],
                 description or "Student Union event",
                 now, now,
                 str(organizer_id) if organizer_id is not None else None),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("publish_event failed: %s", exc)
        return None

    try:
        from education_system.university_system.modules.domain.academics.gui._event_bus import (
            publish, EVENT_CALENDAR_CHANGED,
        )
        publish(EVENT_CALENDAR_CHANGED, event_id=event_id,
                event_type="su_event", action="created",
                date=when[:10], name=name)
    except Exception:
        pass
    return event_id


__all__ = [
    "list_clubs_for", "is_member_of", "join_club", "leave_club",
    "charge_membership_fee", "list_outstanding_su_charges",
    "request_advocacy", "record_advocacy", "list_advocacy_requests_for",
    "publish_event",
]
