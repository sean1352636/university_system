"""Employers, their workplaces, and the managers who sign for them."""

from __future__ import annotations

from typing import Any

from education_system.systems.apprenticeships.domain.employers.models import (
    Employer,
    EmployerManager,
    EmployerSummary,
    Workplace,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories.base import (
    QueryBuilder,
    col,
    connect,
    init_db,
    to_bool,
    to_float,
    to_int,
)

# Selected by every summary query. Kept as one string so the column list
# and the mapper below cannot drift apart. The status literals restate
# config.ACTIVE_STATUSES — SQL cannot read the tuple.
_SUMMARY_SELECT = """
    SELECT e.*,
           (SELECT COUNT(*) FROM apprentices a
             WHERE a.employer_id = e.employer_id)
                         AS apprentice_count,
           (SELECT COUNT(*) FROM apprentices a
             WHERE a.employer_id = e.employer_id
               AND a.status IN ('On Programme', 'Gateway', 'EPA'))
                         AS active_apprentices,
           (SELECT COUNT(*) FROM employer_workplaces w
             WHERE w.employer_id = e.employer_id)
                         AS workplace_count,
           (SELECT COUNT(*) FROM apprentices a
             WHERE a.employer_id = e.employer_id AND a.status = 'Completed')
                         AS completed_apprentices,
           (SELECT COUNT(*) FROM apprentices a
             WHERE a.employer_id = e.employer_id AND a.status = 'Withdrawn')
                         AS withdrawn_apprentices,
           (SELECT COUNT(*)
              FROM otj_entries o
              JOIN apprentices a ON a.apprentice_id = o.apprentice_id
             WHERE a.employer_id = e.employer_id AND o.status = 'Submitted')
                         AS pending_otj_approvals,
           (SELECT COUNT(*)
              FROM reviews r
              JOIN apprentices a ON a.apprentice_id = r.apprentice_id
             WHERE a.employer_id = e.employer_id AND r.status = 'Awaiting Signatures')
                         AS reviews_awaiting_signature
      FROM employers e
"""

_FIELDS = (
    "name", "company_number", "sector", "size", "headcount", "paybill",
    "address", "postcode", "status", "contract_start", "contract_end", "notes",
)

_WORKPLACE_FIELDS = (
    "employer_id", "name", "address", "postcode",
    "hs_checked_date", "hs_expiry_date", "active",
)

_MANAGER_FIELDS = (
    "employer_id", "full_name", "job_title", "email", "phone",
    "is_primary", "username", "active",
)


def _map(row: Any) -> Employer:
    headcount = col(row, "headcount")
    paybill = col(row, "paybill")
    return Employer(
        employer_id=row["employer_id"],
        name=row["name"],
        company_number=col(row, "company_number"),
        sector=col(row, "sector"),
        size=col(row, "size"),
        # NULL has to survive the round trip: the levy and small-employer
        # rules treat "never told us" differently from a genuine zero, so
        # the usual to_int/to_float defaults would change the answer.
        headcount=to_int(headcount) if headcount is not None else None,
        paybill=to_float(paybill) if paybill is not None else None,
        address=col(row, "address"),
        postcode=col(row, "postcode"),
        status=col(row, "status", "Prospect"),
        contract_start=col(row, "contract_start"),
        contract_end=col(row, "contract_end"),
        notes=col(row, "notes"),
        created_at=col(row, "created_at", ""),
        updated_at=col(row, "updated_at", ""),
    )


def _map_summary(row: Any) -> EmployerSummary:
    return EmployerSummary(
        employer=_map(row),
        apprentice_count=to_int(col(row, "apprentice_count")),
        active_apprentices=to_int(col(row, "active_apprentices")),
        workplace_count=to_int(col(row, "workplace_count")),
        completed_apprentices=to_int(col(row, "completed_apprentices")),
        withdrawn_apprentices=to_int(col(row, "withdrawn_apprentices")),
        pending_otj_approvals=to_int(col(row, "pending_otj_approvals")),
        reviews_awaiting_signature=to_int(col(row, "reviews_awaiting_signature")),
    )


def _map_workplace(row: Any) -> Workplace:
    return Workplace(
        workplace_id=row["workplace_id"],
        employer_id=row["employer_id"],
        name=row["name"],
        address=col(row, "address"),
        postcode=col(row, "postcode"),
        hs_checked_date=col(row, "hs_checked_date"),
        hs_expiry_date=col(row, "hs_expiry_date"),
        active=to_bool(col(row, "active"), True),
        created_at=col(row, "created_at", ""),
    )


def _map_manager(row: Any) -> EmployerManager:
    return EmployerManager(
        manager_id=row["manager_id"],
        employer_id=row["employer_id"],
        full_name=row["full_name"],
        job_title=col(row, "job_title"),
        email=col(row, "email"),
        phone=col(row, "phone"),
        is_primary=to_bool(col(row, "is_primary")),
        username=col(row, "username"),
        active=to_bool(col(row, "active"), True),
        created_at=col(row, "created_at", ""),
    )


# ── Reads ───────────────────────────────────────────────────────────

def get(employer_id: int) -> Employer | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM employers WHERE employer_id = ?", (employer_id,)
        ).fetchone()
    return _map(row) if row else None


def get_summary(employer_id: int) -> EmployerSummary | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            f"{_SUMMARY_SELECT} WHERE e.employer_id = ?", (employer_id,)
        ).fetchone()
    return _map_summary(row) if row else None


def get_by_manager_username(username: str) -> Employer | None:
    """Find the organisation an employer login belongs to.

    This is what scopes the employer portal: every screen it renders is
    filtered to the one organisation this lookup returns. Matched
    case-insensitively because usernames arrive from the shared auth
    layer, which does not normalise them, and only against active
    contacts so that deactivating a manager also ends their access.
    """
    init_db()
    with connect() as conn:
        row = conn.execute(
            """SELECT e.*
                 FROM employers e
                 JOIN employer_managers m ON m.employer_id = e.employer_id
                WHERE LOWER(m.username) = LOWER(?) AND m.active = 1
                ORDER BY m.is_primary DESC, m.manager_id
                LIMIT 1""",
            (username,),
        ).fetchone()
    return _map(row) if row else None


def list_summaries(
    *,
    status: str | None = None,
    search: str | None = None,
    active_only: bool = False,
) -> list[EmployerSummary]:
    """Employer list with every count the list and dashboard screens show."""
    init_db()
    qb = QueryBuilder()
    qb.add_if(status, "e.status = ?", status)
    if active_only:
        qb.add("e.status = 'Active'")
    if search and search.strip():
        term = f"%{search.strip()}%"
        qb.add(
            "(e.name LIKE ? OR e.company_number LIKE ? OR e.sector LIKE ? "
            "OR e.postcode LIKE ?)",
            term, term, term, term,
        )
    with connect() as conn:
        rows = conn.execute(
            f"{_SUMMARY_SELECT} {qb.where} ORDER BY e.name", qb.args
        ).fetchall()
    return [_map_summary(r) for r in rows]


def list_all(*, active_only: bool = False) -> list[Employer]:
    """Every employer without the summary counts, for pickers."""
    init_db()
    qb = QueryBuilder()
    if active_only:
        qb.add("status = 'Active'")
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM employers {qb.where} ORDER BY name", qb.args
        ).fetchall()
    return [_map(r) for r in rows]


# ── Writes ──────────────────────────────────────────────────────────

def create(payload: dict[str, Any]) -> int:
    """Insert an employer and return the new id."""
    init_db()
    columns = [f for f in _FIELDS if f in payload]
    placeholders = ", ".join("?" for _ in columns)
    values = [payload[c] for c in columns]
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO employers ({', '.join(columns)}) VALUES ({placeholders})",
            values,
        )
        return int(cur.lastrowid)


def update(employer_id: int, payload: dict[str, Any]) -> None:
    """Update the supplied fields only; anything absent is untouched."""
    init_db()
    columns = [f for f in _FIELDS if f in payload]
    if not columns:
        return
    assignments = ", ".join(f"{c} = ?" for c in columns)
    values = [payload[c] for c in columns]
    with connect() as conn:
        conn.execute(
            f"UPDATE employers SET {assignments}, updated_at = datetime('now') "
            "WHERE employer_id = ?",
            [*values, employer_id],
        )


def delete(employer_id: int) -> None:
    """Remove an employer, their workplaces and their managers.

    Apprentices survive with a null employer rather than cascading away,
    so ending a relationship properly means setting the status to
    'Ended' — this is for correcting a record that should never have
    been created.
    """
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM employers WHERE employer_id = ?", (employer_id,))


# ── Workplaces ──────────────────────────────────────────────────────

def list_workplaces(employer_id: int, *, active_only: bool = False) -> list[Workplace]:
    init_db()
    qb = QueryBuilder()
    qb.add("employer_id = ?", employer_id)
    if active_only:
        qb.add("active = 1")
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM employer_workplaces {qb.where} ORDER BY name", qb.args
        ).fetchall()
    return [_map_workplace(r) for r in rows]


def get_workplace(workplace_id: int) -> Workplace | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM employer_workplaces WHERE workplace_id = ?", (workplace_id,)
        ).fetchone()
    return _map_workplace(row) if row else None


def create_workplace(payload: dict[str, Any]) -> int:
    init_db()
    columns = [f for f in _WORKPLACE_FIELDS if f in payload]
    placeholders = ", ".join("?" for _ in columns)
    values = [payload[c] for c in columns]
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO employer_workplaces ({', '.join(columns)}) VALUES ({placeholders})",
            values,
        )
        return int(cur.lastrowid)


def update_workplace(workplace_id: int, payload: dict[str, Any]) -> None:
    init_db()
    columns = [f for f in _WORKPLACE_FIELDS if f in payload]
    if not columns:
        return
    assignments = ", ".join(f"{c} = ?" for c in columns)
    values = [payload[c] for c in columns]
    with connect() as conn:
        conn.execute(
            f"UPDATE employer_workplaces SET {assignments} WHERE workplace_id = ?",
            [*values, workplace_id],
        )


def delete_workplace(workplace_id: int) -> None:
    """Remove a site. Apprentices placed there keep a null workplace."""
    init_db()
    with connect() as conn:
        conn.execute(
            "DELETE FROM employer_workplaces WHERE workplace_id = ?", (workplace_id,)
        )


# ── Managers ────────────────────────────────────────────────────────

def list_managers(employer_id: int, *, active_only: bool = False) -> list[EmployerManager]:
    init_db()
    qb = QueryBuilder()
    qb.add("employer_id = ?", employer_id)
    if active_only:
        qb.add("active = 1")
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM employer_managers {qb.where} "
            "ORDER BY is_primary DESC, full_name",
            qb.args,
        ).fetchall()
    return [_map_manager(r) for r in rows]


def get_manager(manager_id: int) -> EmployerManager | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM employer_managers WHERE manager_id = ?", (manager_id,)
        ).fetchone()
    return _map_manager(row) if row else None


def create_manager(payload: dict[str, Any]) -> int:
    init_db()
    columns = [f for f in _MANAGER_FIELDS if f in payload]
    placeholders = ", ".join("?" for _ in columns)
    values = [payload[c] for c in columns]
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO employer_managers ({', '.join(columns)}) VALUES ({placeholders})",
            values,
        )
        return int(cur.lastrowid)


def update_manager(manager_id: int, payload: dict[str, Any]) -> None:
    init_db()
    columns = [f for f in _MANAGER_FIELDS if f in payload]
    if not columns:
        return
    assignments = ", ".join(f"{c} = ?" for c in columns)
    values = [payload[c] for c in columns]
    with connect() as conn:
        conn.execute(
            f"UPDATE employer_managers SET {assignments} WHERE manager_id = ?",
            [*values, manager_id],
        )


def delete_manager(manager_id: int) -> None:
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM employer_managers WHERE manager_id = ?", (manager_id,))


def clear_primary(employer_id: int) -> None:
    """Demote every contact at this employer.

    Only one manager may be primary — they are the signatory on the
    commitment statement and the reviews — and the table cannot express
    that, so promoting a new one means clearing the flag first.
    """
    init_db()
    with connect() as conn:
        conn.execute(
            "UPDATE employer_managers SET is_primary = 0 WHERE employer_id = ?",
            (employer_id,),
        )
