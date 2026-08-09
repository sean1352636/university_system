"""Provider staff and the caseload figures that hang off them."""

from __future__ import annotations

from typing import Any

from education_system.systems.apprenticeships.domain.staff.assessors import Caseload, Staff
from education_system.systems.apprenticeships.infrastructure.persistence.repositories.base import (
    QueryBuilder,
    col,
    connect,
    init_db,
    to_bool,
    to_int,
)

_FIELDS = (
    "full_name", "email", "phone", "staff_role", "username", "specialisms", "active",
)


def _map(row: Any) -> Staff:
    return Staff(
        staff_id=row["staff_id"],
        full_name=row["full_name"],
        email=col(row, "email"),
        phone=col(row, "phone"),
        staff_role=col(row, "staff_role", "Tutor"),
        username=col(row, "username"),
        specialisms=col(row, "specialisms"),
        active=to_bool(col(row, "active"), True),
        created_at=col(row, "created_at", ""),
        updated_at=col(row, "updated_at", ""),
    )


def get(staff_id: int) -> Staff | None:
    init_db()
    with connect() as conn:
        row = conn.execute("SELECT * FROM staff WHERE staff_id = ?", (staff_id,)).fetchone()
    return _map(row) if row else None


def get_by_username(username: str) -> Staff | None:
    """Find the staff record a login belongs to.

    This is how a tutor's screens scope to their own caseload, so it is
    case-insensitive to match the shared auth layer's handling.
    """
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM staff WHERE LOWER(username) = LOWER(?)", (username,)
        ).fetchone()
    return _map(row) if row else None


def list_all(
    *, staff_role: str | None = None, active_only: bool = False, search: str | None = None
) -> list[Staff]:
    init_db()
    qb = QueryBuilder()
    qb.add_if(staff_role, "staff_role = ?", staff_role)
    qb.add_if(active_only, "active = 1")
    if search and search.strip():
        term = f"%{search.strip()}%"
        qb.add("(full_name LIKE ? OR email LIKE ? OR specialisms LIKE ?)", term, term, term)
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM staff {qb.where} ORDER BY full_name", qb.args
        ).fetchall()
    return [_map(r) for r in rows]


def create(payload: dict[str, Any]) -> int:
    init_db()
    columns = [f for f in _FIELDS if f in payload]
    placeholders = ", ".join("?" for _ in columns)
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO staff ({', '.join(columns)}) VALUES ({placeholders})",
            [payload[c] for c in columns],
        )
        return int(cur.lastrowid)


def update(staff_id: int, payload: dict[str, Any]) -> None:
    init_db()
    columns = [f for f in _FIELDS if f in payload]
    if not columns:
        return
    assignments = ", ".join(f"{c} = ?" for c in columns)
    with connect() as conn:
        conn.execute(
            f"UPDATE staff SET {assignments}, updated_at = datetime('now') WHERE staff_id = ?",
            [*[payload[c] for c in columns], staff_id],
        )


def delete(staff_id: int) -> None:
    """Remove a staff record.

    Apprentices whose tutor this was keep their record — the foreign key
    is ON DELETE SET NULL — and surface on the admin dashboard as
    unassigned, which is the outcome you want: losing a tutor should
    make the reassignment visible, not silently orphan a caseload.
    """
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM staff WHERE staff_id = ?", (staff_id,))


def caseload_counts(staff_id: int) -> dict[str, int]:
    """Every caseload pressure figure for one tutor, in one query."""
    init_db()
    with connect() as conn:
        row = conn.execute(
            """SELECT
                   COUNT(*) AS total,
                   COALESCE(SUM(CASE WHEN a.status IN ('On Programme', 'Gateway', 'EPA')
                                     THEN 1 ELSE 0 END), 0) AS active,
                   COALESCE(SUM(CASE WHEN a.status = 'Gateway' THEN 1 ELSE 0 END), 0)
                                                            AS at_gateway
                 FROM apprentices a
                WHERE a.tutor_id = ?""",
            (staff_id,),
        ).fetchone()
        overdue = conn.execute(
            """SELECT COUNT(*) AS n FROM reviews r
                 JOIN apprentices a ON a.apprentice_id = r.apprentice_id
                WHERE a.tutor_id = ?
                  AND r.status IN ('Scheduled', 'In Progress')
                  AND r.scheduled_date < date('now')""",
            (staff_id,),
        ).fetchone()
        awaiting = conn.execute(
            """SELECT COUNT(*) AS n FROM portfolio_evidence e
                 JOIN apprentices a ON a.apprentice_id = e.apprentice_id
                WHERE a.tutor_id = ? AND e.status = 'Submitted'""",
            (staff_id,),
        ).fetchone()
    return {
        "total": to_int(row["total"]),
        "active": to_int(row["active"]),
        "at_gateway": to_int(row["at_gateway"]),
        "reviews_overdue": to_int(overdue["n"]),
        "evidence_awaiting_assessment": to_int(awaiting["n"]),
    }


def build_caseload(staff_id: int, *, with_members: bool = False) -> Caseload | None:
    """Assemble one tutor's caseload view.

    ``otj_behind`` needs each apprentice's own target, which depends on
    their dates — that cannot be expressed in a single aggregate, so it
    is computed from the summaries the cohort query already builds.
    """
    member = get(staff_id)
    if member is None:
        return None
    counts = caseload_counts(staff_id)

    from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
        apprentice_repository,
    )

    summaries = apprentice_repository.list_summaries(tutor_id=staff_id, active_only=True)
    behind = sum(1 for s in summaries if s.is_behind)
    return Caseload(
        staff=member,
        total=counts["total"],
        active=counts["active"],
        at_gateway=counts["at_gateway"],
        reviews_overdue=counts["reviews_overdue"],
        otj_behind=behind,
        evidence_awaiting_assessment=counts["evidence_awaiting_assessment"],
        members=list(summaries) if with_members else [],
    )


def list_caseloads(*, active_only: bool = True) -> list[Caseload]:
    """Every tutor's caseload, for the admin staff screen."""
    caseloads = []
    for member in list_all(active_only=active_only):
        caseload = build_caseload(member.staff_id)
        if caseload is not None:
            caseloads.append(caseload)
    caseloads.sort(key=lambda c: c.active, reverse=True)
    return caseloads
