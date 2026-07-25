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

from education_system.systems.university.infrastructure.database.db import (
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
        from education_system.systems.university.interfaces.gui.academics._event_bus import publish
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
              *, fee: float = 0.0,
              ignore_holds: bool = False) -> int | None:
    """Add a club_memberships row + (optionally) a finance charge.

    Refuses the join if the student has an active finance hold and the
    club has a non-zero fee (so we don't pile charges onto a blocked
    account). Pass ``ignore_holds=True`` to override — e.g. an SU
    welfare officer manually waiving the gate.
    """
    sid = str(student_id)
    if fee and fee > 0 and not ignore_holds:
        try:
            from education_system.systems.university.services.bus import (
                finance_bus,
            )
            if finance_bus.has_active_hold(sid):
                logger.info(
                    "join_club refused for %s: active finance hold", sid
                )
                _publish("su.membership.refused",
                         student_id=sid, club_id=int(club_id),
                         reason="finance_hold")
                return None
        except Exception as exc:
            logger.debug("join_club hold check failed: %s", exc)

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

    # Cross-domain: joining a fitness/sports SU club auto-grants
    # gym day-passes so the SU and gym memberships reinforce each
    # other instead of competing. Best-effort.
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT category FROM student_union_clubs WHERE id = ?",
                (int(club_id),),
            ).fetchone()
        if row and row[0]:
            cat = str(row[0]).lower()
            if any(k in cat for k in ("sport", "fitness", "athletic")):
                _grant_gym_day_passes(sid, count=3,
                                      reason=f"su_club:{club_id}")
    except Exception as exc:
        logger.debug("fitness club perk failed: %s", exc)

    return membership_id


def _grant_gym_day_passes(student_id: str, *, count: int,
                          reason: str) -> None:
    """Insert N day-pass rows in ``gym_day_passes`` (created on demand).
    Decoupled from gym_core so SU doesn't import gym; gym reads this
    table when the student tries to enter without a membership."""
    if not student_id or count <= 0:
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with get_connection() as conn:
            conn.executescript(
                "CREATE TABLE IF NOT EXISTS gym_day_passes ("
                " pass_id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " student_id TEXT NOT NULL,"
                " granted_at TEXT NOT NULL,"
                " used_at TEXT,"
                " reason TEXT)"
            )
            for _ in range(int(count)):
                conn.execute(
                    "INSERT INTO gym_day_passes "
                    "(student_id, granted_at, reason) VALUES (?, ?, ?)",
                    (student_id, now, reason),
                )
            conn.commit()
        _publish("gym.day_pass.granted",
                 student_id=student_id, count=int(count), reason=reason)
    except Exception as exc:
        logger.debug("_grant_gym_day_passes failed: %s", exc)


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
        from education_system.systems.university.services.bus.finance_bus import (
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
                  organizer_id: str | int | None = None,
                  tags: list[str] | None = None) -> str | None:
    """Persist an SU event as an academic_calendar_events row.

    Hits the same path H&S evacuation drills and AM/DP hearings use,
    so the SU event shows up automatically on every calendar view
    that subscribes to ``EVENT_CALENDAR_CHANGED``.

    ``tags`` (e.g. ``["large", "alcohol", "external"]``) drives
    cross-domain pre-clearance:

    * Any tag triggering "large"/"alcohol"/"external" opens a
      ``cases_bus`` ``event_clearance`` case for the security desk
      and a date-bounded ``risks`` row that auto-expires after the
      event. The calendar row is still written (so it shows up on
      planning views) but is published with
      ``approval_status='pending'`` so subscribers can hide it from
      public-facing views until the case closes with
      ``outcome='approved'``.
    """
    if not name or not when:
        return None
    event_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    needs_clearance = bool(tags) and any(
        str(t).lower() in ("large", "alcohol", "external")
        for t in tags
    )
    approval_status = "pending" if needs_clearance else "approved"

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
        from education_system.systems.university.interfaces.gui.academics._event_bus import (
            publish, EVENT_CALENDAR_CHANGED,
        )
        publish(EVENT_CALENDAR_CHANGED, event_id=event_id,
                event_type="su_event", action="created",
                date=when[:10], name=name,
                approval_status=approval_status,
                tags=list(tags) if tags else [])
    except Exception:
        pass

    if needs_clearance:
        # Open a security-desk clearance case and a date-bounded
        # risk register entry. Both reference back to the event_id
        # so closing the case folds the risk and the calendar
        # subscriber can flip approval_status to 'approved'.
        try:
            from education_system.systems.university.services.bus import (
                cases_bus,
            )
            cases_bus.open_case(
                kind="event_clearance",
                subject_id=str(organizer_id or event_id),
                opened_by="student_union_bus",
                description=(f"SU event '{name}' on {when[:10]} "
                             f"requires security pre-clearance "
                             f"(tags: {sorted(set(tags or []))})."),
                severity="High",
                offense_type="Event clearance",
                location=location,
            )
        except Exception as exc:
            logger.debug("event clearance case failed: %s", exc)

        try:
            from education_system.systems.university.services.bus import (
                risk_bus,
            )
            risk_bus.raise_event_clearance_risk(
                event_id, name=name, when=when, tags=tags or [],
                organizer_id=str(organizer_id) if organizer_id else None,
            )
        except Exception as exc:
            logger.debug("event clearance risk failed: %s", exc)

    return event_id


# ---------------------------------------------------------------------------
# Housing ↔ SU: hall-scoped clubs and residents
# ---------------------------------------------------------------------------

def _ensure_hall_column(conn: sqlite3.Connection) -> None:
    """Add a nullable ``hall_id`` column to ``student_union_clubs``
    on first use. Idempotent — silently does nothing if the column
    already exists or the table is missing."""
    try:
        cols = {r[1] for r in conn.execute(
            "PRAGMA table_info(student_union_clubs)"
        ).fetchall()}
        if cols and "hall_id" not in cols:
            conn.execute(
                "ALTER TABLE student_union_clubs ADD COLUMN hall_id TEXT"
            )
    except Exception as exc:
        logger.debug("_ensure_hall_column: %s", exc)


def student_hall(student_id: str | int) -> str | None:
    """Return the building_id of the student's active housing
    assignment, or ``None`` if they have no current room."""
    if not student_id:
        return None
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT r.building_id "
                "FROM housing_assignments a "
                "JOIN housing_rooms r ON r.room_id = a.room_id "
                "WHERE a.student_id = ? AND a.status = 'Active' "
                "ORDER BY a.created_at DESC LIMIT 1",
                (str(student_id),),
            ).fetchone()
            return str(row[0]) if row else None
    except Exception as exc:
        logger.warning("student_hall(%s) failed: %s", student_id, exc)
        return None


def list_hall_residents(building_id: str | int) -> list[str]:
    """Return active resident student_ids for a building. Used by
    SU elections to scope hall-rep ballots."""
    if not building_id:
        return []
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT a.student_id "
                "FROM housing_assignments a "
                "JOIN housing_rooms r ON r.room_id = a.room_id "
                "WHERE r.building_id = ? AND a.status = 'Active'",
                (str(building_id),),
            ).fetchall()
            return [str(r[0]) for r in rows]
    except Exception as exc:
        logger.warning("list_hall_residents(%s) failed: %s",
                       building_id, exc)
        return []


def list_hall_clubs(building_id: str | int) -> list[dict[str, Any]]:
    """Return SU clubs scoped to a specific hall."""
    if not building_id:
        return []
    out: list[dict[str, Any]] = []
    try:
        with get_connection() as conn:
            _ensure_hall_column(conn)
            for r in conn.execute(
                "SELECT id, name, category, hall_id "
                "FROM student_union_clubs "
                "WHERE hall_id = ?",
                (str(building_id),),
            ).fetchall():
                out.append(dict(r))
    except Exception as exc:
        logger.warning("list_hall_clubs(%s) failed: %s", building_id, exc)
    return out


def set_club_hall(club_id: int, building_id: str | int | None) -> bool:
    """Mark an SU club as hall-scoped (or clear the scope with
    ``building_id=None``)."""
    if not club_id:
        return False
    try:
        with get_connection() as conn:
            _ensure_hall_column(conn)
            conn.execute(
                "UPDATE student_union_clubs SET hall_id = ? WHERE id = ?",
                (str(building_id) if building_id is not None else None,
                 int(club_id)),
            )
            conn.commit()
        return True
    except Exception as exc:
        logger.warning("set_club_hall(%s, %s) failed: %s",
                       club_id, building_id, exc)
        return False


def hall_eligible_for(student_id: str | int, club_id: int) -> bool:
    """Return True if either the club is open (no hall_id) or the
    student lives in the matching hall. Used by ``join_club`` to
    enforce hall-scoped membership."""
    if not student_id or not club_id:
        return False
    try:
        with get_connection() as conn:
            _ensure_hall_column(conn)
            row = conn.execute(
                "SELECT hall_id FROM student_union_clubs WHERE id = ?",
                (int(club_id),),
            ).fetchone()
            if not row:
                return False
            club_hall = row[0]
            if not club_hall:
                return True
            return student_hall(student_id) == str(club_hall)
    except Exception as exc:
        logger.warning("hall_eligible_for failed: %s", exc)
        return False


__all__ = [
    "list_clubs_for", "is_member_of", "join_club", "leave_club",
    "charge_membership_fee", "list_outstanding_su_charges",
    "request_advocacy", "record_advocacy", "list_advocacy_requests_for",
    "publish_event",
    "student_hall", "list_hall_residents", "list_hall_clubs",
    "set_club_hall", "hall_eligible_for",
]
