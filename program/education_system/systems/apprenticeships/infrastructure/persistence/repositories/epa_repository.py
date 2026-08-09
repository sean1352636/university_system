"""Gateway records, EPAOs, EPA bookings, results and resits."""

from __future__ import annotations

from typing import Any

from education_system.systems.apprenticeships.domain.end_point_assessment.results import (
    EPAO,
    EPABooking,
    EPAResit,
    EPAResult,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories.base import (
    QueryBuilder,
    col,
    connect,
    init_db,
    to_bool,
)

_BOOKING_FIELDS = (
    "apprentice_id", "epao_id", "method", "scheduled_date", "scheduled_time",
    "location", "assessor_name", "assessor_username", "status", "resit_of", "notes",
)

_EPAO_FIELDS = ("name", "contact_name", "contact_email", "phone", "standards", "active")

_BOOKING_SELECT = """
    SELECT b.*,
           (a.given_name || ' ' || a.family_name) AS apprentice_name,
           a.uln          AS apprentice_uln,
           e.name         AS epao_name,
           p.title        AS programme_title,
           p.reference    AS programme_reference
      FROM epa_bookings b
      JOIN apprentices a ON a.apprentice_id = b.apprentice_id
      LEFT JOIN epaos      e ON e.epao_id      = b.epao_id
      LEFT JOIN programmes p ON p.programme_id = a.programme_id
"""


def _map_booking(row: Any) -> EPABooking:
    return EPABooking(
        booking_id=row["booking_id"],
        apprentice_id=row["apprentice_id"],
        method=row["method"],
        epao_id=col(row, "epao_id"),
        scheduled_date=col(row, "scheduled_date"),
        scheduled_time=col(row, "scheduled_time"),
        location=col(row, "location"),
        assessor_name=col(row, "assessor_name"),
        assessor_username=col(row, "assessor_username"),
        status=col(row, "status", "Requested"),
        resit_of=col(row, "resit_of"),
        notes=col(row, "notes"),
        created_at=col(row, "created_at", ""),
        updated_at=col(row, "updated_at", ""),
    )


def _map_result(row: Any) -> EPAResult:
    return EPAResult(
        result_id=row["result_id"],
        booking_id=row["booking_id"],
        apprentice_id=row["apprentice_id"],
        method=row["method"],
        grade=row["grade"],
        assessed_date=row["assessed_date"],
        assessor_name=col(row, "assessor_name"),
        feedback=col(row, "feedback"),
        attempt=col(row, "attempt", 1),
        created_at=col(row, "created_at", ""),
    )


def _map_epao(row: Any) -> EPAO:
    return EPAO(
        epao_id=row["epao_id"],
        name=row["name"],
        contact_name=col(row, "contact_name"),
        contact_email=col(row, "contact_email"),
        phone=col(row, "phone"),
        standards=col(row, "standards"),
        active=to_bool(col(row, "active"), True),
        created_at=col(row, "created_at", ""),
    )


def _map_resit(row: Any) -> EPAResit:
    return EPAResit(
        resit_id=row["resit_id"],
        apprentice_id=row["apprentice_id"],
        result_id=row["result_id"],
        resit_type=row["resit_type"],
        reason=col(row, "reason"),
        training_plan=col(row, "training_plan"),
        requested_at=col(row, "requested_at", ""),
        requested_by=col(row, "requested_by"),
        status=col(row, "status", "Requested"),
        booking_id=col(row, "booking_id"),
    )


# ── Gateway ─────────────────────────────────────────────────────────

def get_gateway_row(apprentice_id: int) -> dict[str, Any] | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM gateway_records WHERE apprentice_id = ?", (apprentice_id,)
        ).fetchone()
    return dict(row) if row else None


def ensure_gateway(apprentice_id: int) -> int:
    """Get this apprentice's gateway row, creating a blank one if needed.

    Every apprentice conceptually has a gateway state from day one, but
    materialising a row at enrolment would litter the table for people
    who withdraw in week two. It is created on first read instead.
    """
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT gateway_id FROM gateway_records WHERE apprentice_id = ?",
            (apprentice_id,),
        ).fetchone()
        if row:
            return int(row["gateway_id"])
        cur = conn.execute(
            "INSERT INTO gateway_records (apprentice_id) VALUES (?)", (apprentice_id,)
        )
        return int(cur.lastrowid)


def set_gateway_status(
    apprentice_id: int,
    status: str,
    *,
    requested_at: str | None = None,
    requested_by: str | None = None,
    decided_at: str | None = None,
    decided_by: str | None = None,
    decision_notes: str | None = None,
) -> None:
    gateway_id = ensure_gateway(apprentice_id)
    assignments = ["status = ?"]
    args: list[Any] = [status]
    for column, value in (
        ("requested_at", requested_at), ("requested_by", requested_by),
        ("decided_at", decided_at), ("decided_by", decided_by),
        ("decision_notes", decision_notes),
    ):
        if value is not None:
            assignments.append(f"{column} = ?")
            args.append(value)
    with connect() as conn:
        conn.execute(
            f"UPDATE gateway_records SET {', '.join(assignments)}, "
            "updated_at = datetime('now') WHERE gateway_id = ?",
            [*args, gateway_id],
        )


def get_manual_check(apprentice_id: int, requirement_key: str) -> dict[str, Any] | None:
    """Read a human-recorded gateway check.

    Only the manual requirements are stored; the automatic ones are
    recomputed from live data on every read, so persisting them would
    only create something to go stale.
    """
    init_db()
    with connect() as conn:
        row = conn.execute(
            """SELECT c.* FROM gateway_checks c
                 JOIN gateway_records g ON g.gateway_id = c.gateway_id
                WHERE g.apprentice_id = ? AND c.requirement_key = ?""",
            (apprentice_id, requirement_key),
        ).fetchone()
    return dict(row) if row else None


def set_manual_check(
    apprentice_id: int,
    requirement_key: str,
    *,
    met: bool,
    evidence_note: str | None,
    checked_by: str | None,
    checked_at: str,
) -> None:
    gateway_id = ensure_gateway(apprentice_id)
    with connect() as conn:
        conn.execute(
            """INSERT INTO gateway_checks
                   (gateway_id, requirement_key, met, automatic,
                    evidence_note, checked_by, checked_at)
               VALUES (?, ?, ?, 0, ?, ?, ?)
               ON CONFLICT(gateway_id, requirement_key) DO UPDATE SET
                   met = excluded.met,
                   evidence_note = excluded.evidence_note,
                   checked_by = excluded.checked_by,
                   checked_at = excluded.checked_at""",
            (gateway_id, requirement_key, 1 if met else 0,
             evidence_note, checked_by, checked_at),
        )


def list_gateway_queue(
    *, status: str | None = None, tutor_id: int | None = None
) -> list[dict[str, Any]]:
    """Apprentices at or approaching gateway, for the provider queues."""
    init_db()
    qb = QueryBuilder()
    qb.add_if(status, "COALESCE(g.status, 'Not Ready') = ?", status)
    qb.add_if(tutor_id, "a.tutor_id = ?", tutor_id)
    qb.add("a.status IN ('On Programme', 'Gateway', 'EPA')")
    with connect() as conn:
        rows = conn.execute(
            f"""SELECT a.apprentice_id,
                       (a.given_name || ' ' || a.family_name) AS apprentice_name,
                       a.uln, a.status AS apprentice_status,
                       COALESCE(g.status, 'Not Ready') AS gateway_status,
                       g.requested_at, g.decided_at,
                       p.title AS programme_title, p.reference AS programme_reference,
                       e.name  AS employer_name,
                       s.full_name AS tutor_name
                  FROM apprentices a
                  LEFT JOIN gateway_records g ON g.apprentice_id = a.apprentice_id
                  LEFT JOIN programmes      p ON p.programme_id  = a.programme_id
                  LEFT JOIN employers       e ON e.employer_id   = a.employer_id
                  LEFT JOIN staff           s ON s.staff_id      = a.tutor_id
                  {qb.where}
                 ORDER BY a.family_name, a.given_name""",
            qb.args,
        ).fetchall()
    return [dict(r) for r in rows]


# ── EPAOs ───────────────────────────────────────────────────────────

def get_epao(epao_id: int) -> EPAO | None:
    init_db()
    with connect() as conn:
        row = conn.execute("SELECT * FROM epaos WHERE epao_id = ?", (epao_id,)).fetchone()
    return _map_epao(row) if row else None


def list_epaos(*, active_only: bool = False) -> list[EPAO]:
    init_db()
    qb = QueryBuilder()
    qb.add_if(active_only, "active = 1")
    with connect() as conn:
        rows = conn.execute(f"SELECT * FROM epaos {qb.where} ORDER BY name", qb.args).fetchall()
    return [_map_epao(r) for r in rows]


def create_epao(payload: dict[str, Any]) -> int:
    init_db()
    columns = [f for f in _EPAO_FIELDS if f in payload]
    placeholders = ", ".join("?" for _ in columns)
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO epaos ({', '.join(columns)}) VALUES ({placeholders})",
            [payload[c] for c in columns],
        )
        return int(cur.lastrowid)


def update_epao(epao_id: int, payload: dict[str, Any]) -> None:
    init_db()
    columns = [f for f in _EPAO_FIELDS if f in payload]
    if not columns:
        return
    assignments = ", ".join(f"{c} = ?" for c in columns)
    with connect() as conn:
        conn.execute(
            f"UPDATE epaos SET {assignments} WHERE epao_id = ?",
            [*[payload[c] for c in columns], epao_id],
        )


def delete_epao(epao_id: int) -> None:
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM epaos WHERE epao_id = ?", (epao_id,))


# ── Bookings ────────────────────────────────────────────────────────

def get_booking(booking_id: int) -> EPABooking | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            f"{_BOOKING_SELECT} WHERE b.booking_id = ?", (booking_id,)
        ).fetchone()
    return _map_booking(row) if row else None


def get_booking_row(booking_id: int) -> dict[str, Any] | None:
    """The booking plus its joined labels, for screens that show context."""
    init_db()
    with connect() as conn:
        row = conn.execute(
            f"{_BOOKING_SELECT} WHERE b.booking_id = ?", (booking_id,)
        ).fetchone()
    return dict(row) if row else None


def list_bookings(
    *,
    apprentice_id: int | None = None,
    epao_id: int | None = None,
    assessor_username: str | None = None,
    status: str | None = None,
    statuses: list[str] | None = None,
    method: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    open_only: bool = False,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Bookings as row dicts, since every screen wants the joined labels."""
    init_db()
    qb = QueryBuilder()
    qb.add_if(apprentice_id, "b.apprentice_id = ?", apprentice_id)
    qb.add_if(epao_id, "b.epao_id = ?", epao_id)
    qb.add_if(
        assessor_username,
        "LOWER(b.assessor_username) = LOWER(?)",
        assessor_username,
    )
    qb.add_if(status, "b.status = ?", status)
    qb.add_in("b.status", statuses)
    qb.add_if(method, "b.method = ?", method)
    qb.add_if(date_from, "b.scheduled_date >= ?", date_from)
    qb.add_if(date_to, "b.scheduled_date <= ?", date_to)
    qb.add_if(open_only, "b.status IN ('Requested', 'Scheduled', 'In Progress')")
    sql = (
        f"{_BOOKING_SELECT} {qb.where} "
        "ORDER BY COALESCE(b.scheduled_date, '9999-12-31'), b.booking_id"
    )
    args = qb.args
    if limit:
        sql += " LIMIT ?"
        args = [*args, int(limit)]
    with connect() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [dict(r) for r in rows]


def list_bookings_typed(**kwargs: Any) -> list[EPABooking]:
    """The same query, mapped onto the dataclass."""
    return [_map_booking_from_dict(r) for r in list_bookings(**kwargs)]


def _map_booking_from_dict(row: dict[str, Any]) -> EPABooking:
    return EPABooking(
        booking_id=row["booking_id"],
        apprentice_id=row["apprentice_id"],
        method=row["method"],
        epao_id=row.get("epao_id"),
        scheduled_date=row.get("scheduled_date"),
        scheduled_time=row.get("scheduled_time"),
        location=row.get("location"),
        assessor_name=row.get("assessor_name"),
        assessor_username=row.get("assessor_username"),
        status=row.get("status", "Requested"),
        resit_of=row.get("resit_of"),
        notes=row.get("notes"),
        created_at=row.get("created_at", ""),
        updated_at=row.get("updated_at", ""),
    )


def create_booking(payload: dict[str, Any]) -> int:
    init_db()
    columns = [f for f in _BOOKING_FIELDS if f in payload]
    placeholders = ", ".join("?" for _ in columns)
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO epa_bookings ({', '.join(columns)}) VALUES ({placeholders})",
            [payload[c] for c in columns],
        )
        return int(cur.lastrowid)


def update_booking(booking_id: int, payload: dict[str, Any]) -> None:
    init_db()
    columns = [f for f in _BOOKING_FIELDS if f in payload]
    if not columns:
        return
    assignments = ", ".join(f"{c} = ?" for c in columns)
    with connect() as conn:
        conn.execute(
            f"UPDATE epa_bookings SET {assignments}, updated_at = datetime('now') "
            "WHERE booking_id = ?",
            [*[payload[c] for c in columns], booking_id],
        )


def delete_booking(booking_id: int) -> None:
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM epa_bookings WHERE booking_id = ?", (booking_id,))


# ── Results ─────────────────────────────────────────────────────────

def get_result(result_id: int) -> EPAResult | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM epa_results WHERE result_id = ?", (result_id,)
        ).fetchone()
    return _map_result(row) if row else None


def get_result_for_booking(booking_id: int) -> EPAResult | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM epa_results WHERE booking_id = ?", (booking_id,)
        ).fetchone()
    return _map_result(row) if row else None


def list_results(
    *, apprentice_id: int | None = None, method: str | None = None,
    grade: str | None = None, limit: int | None = None,
) -> list[EPAResult]:
    init_db()
    qb = QueryBuilder()
    qb.add_if(apprentice_id, "apprentice_id = ?", apprentice_id)
    qb.add_if(method, "method = ?", method)
    qb.add_if(grade, "grade = ?", grade)
    sql = f"SELECT * FROM epa_results {qb.where} ORDER BY assessed_date DESC, result_id DESC"
    args = qb.args
    if limit:
        sql += " LIMIT ?"
        args = [*args, int(limit)]
    with connect() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [_map_result(r) for r in rows]


def record_result(
    *,
    booking_id: int,
    apprentice_id: int,
    method: str,
    grade: str,
    assessed_date: str,
    assessor_name: str | None,
    feedback: str | None,
    attempt: int,
) -> int:
    """Store a grade and close the booking in one transaction.

    A graded booking that still says 'Scheduled' would show up on the
    assessor's to-do list forever, so the two writes belong together.
    """
    init_db()
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO epa_results
                   (booking_id, apprentice_id, method, grade, assessed_date,
                    assessor_name, feedback, attempt)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (booking_id, apprentice_id, method, grade, assessed_date,
             assessor_name, feedback, attempt),
        )
        conn.execute(
            "UPDATE epa_bookings SET status = 'Assessed', updated_at = datetime('now') "
            "WHERE booking_id = ?",
            (booking_id,),
        )
        return int(cur.lastrowid)


def attempt_count(apprentice_id: int, method: str) -> int:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM epa_results WHERE apprentice_id = ? AND method = ?",
            (apprentice_id, method),
        ).fetchone()
    return int(row["n"])


# ── Resits ──────────────────────────────────────────────────────────

def list_resits(
    *, apprentice_id: int | None = None, status: str | None = None
) -> list[EPAResit]:
    init_db()
    qb = QueryBuilder()
    qb.add_if(apprentice_id, "apprentice_id = ?", apprentice_id)
    qb.add_if(status, "status = ?", status)
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM epa_resits {qb.where} ORDER BY requested_at DESC", qb.args
        ).fetchall()
    return [_map_resit(r) for r in rows]


def get_resit(resit_id: int) -> EPAResit | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM epa_resits WHERE resit_id = ?", (resit_id,)
        ).fetchone()
    return _map_resit(row) if row else None


def create_resit(payload: dict[str, Any]) -> int:
    init_db()
    fields = ("apprentice_id", "result_id", "resit_type", "reason",
              "training_plan", "requested_by", "status", "booking_id")
    columns = [f for f in fields if f in payload]
    placeholders = ", ".join("?" for _ in columns)
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO epa_resits ({', '.join(columns)}) VALUES ({placeholders})",
            [payload[c] for c in columns],
        )
        return int(cur.lastrowid)


def update_resit(resit_id: int, payload: dict[str, Any]) -> None:
    init_db()
    fields = ("resit_type", "reason", "training_plan", "status", "booking_id")
    columns = [f for f in fields if f in payload]
    if not columns:
        return
    assignments = ", ".join(f"{c} = ?" for c in columns)
    with connect() as conn:
        conn.execute(
            f"UPDATE epa_resits SET {assignments} WHERE resit_id = ?",
            [*[payload[c] for c in columns], resit_id],
        )
