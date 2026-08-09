"""Apprentice records, their status history, breaks and withdrawals."""

from __future__ import annotations

from typing import Any

from education_system.systems.apprenticeships.domain.apprentices.models import (
    Apprentice,
    ApprenticeSummary,
)
from education_system.systems.apprenticeships.domain.apprentices.status import StatusChange
from education_system.systems.apprenticeships.infrastructure.persistence.repositories.base import (
    QueryBuilder,
    col,
    connect,
    init_db,
    to_float,
    to_int,
)

# Selected by every summary query. Kept as one string so the column list
# and the mapper below cannot drift apart.
_SUMMARY_SELECT = """
    SELECT a.*,
           p.title       AS programme_title,
           p.reference   AS programme_reference,
           p.level       AS programme_level,
           e.name        AS employer_name,
           w.name        AS workplace_name,
           s.full_name   AS tutor_name,
           g.status      AS gateway_status,
           (SELECT COALESCE(SUM(o.hours), 0) FROM otj_entries o
             WHERE o.apprentice_id = a.apprentice_id AND o.status = 'Approved')
                         AS otj_approved,
           (SELECT COUNT(*) FROM programme_ksbs k
             WHERE k.programme_id = a.programme_id)
                         AS ksbs_total,
           (SELECT COUNT(DISTINCT m.ksb_id)
              FROM evidence_ksb_map m
              JOIN portfolio_evidence pe ON pe.evidence_id = m.evidence_id
             WHERE pe.apprentice_id = a.apprentice_id
               AND pe.status = 'Accepted'
               AND m.coverage = 'Competent')
                         AS ksbs_competent,
           (SELECT COUNT(*) FROM reviews r
             WHERE r.apprentice_id = a.apprentice_id
               AND r.status NOT IN ('Complete', 'Missed'))
                         AS open_reviews
      FROM apprentices a
      LEFT JOIN programmes          p ON p.programme_id = a.programme_id
      LEFT JOIN employers           e ON e.employer_id  = a.employer_id
      LEFT JOIN employer_workplaces w ON w.workplace_id = a.workplace_id
      LEFT JOIN staff               s ON s.staff_id     = a.tutor_id
      LEFT JOIN gateway_records     g ON g.apprentice_id = a.apprentice_id
"""

_FIELDS = (
    "uln", "given_name", "family_name", "date_of_birth", "email", "phone",
    "username", "programme_id", "employer_id", "workplace_id", "tutor_id",
    "status", "start_date", "planned_end_date", "actual_end_date",
    "weekly_hours", "funding_model", "prior_learning", "support_needs", "notes",
)


def _map(row: Any) -> Apprentice:
    return Apprentice(
        apprentice_id=row["apprentice_id"],
        uln=col(row, "uln"),
        given_name=row["given_name"],
        family_name=row["family_name"],
        date_of_birth=col(row, "date_of_birth"),
        email=col(row, "email"),
        phone=col(row, "phone"),
        username=col(row, "username"),
        programme_id=col(row, "programme_id"),
        employer_id=col(row, "employer_id"),
        workplace_id=col(row, "workplace_id"),
        tutor_id=col(row, "tutor_id"),
        status=col(row, "status", "Applicant"),
        start_date=col(row, "start_date"),
        planned_end_date=col(row, "planned_end_date"),
        actual_end_date=col(row, "actual_end_date"),
        weekly_hours=to_float(col(row, "weekly_hours"), 30.0),
        funding_model=col(row, "funding_model"),
        prior_learning=col(row, "prior_learning"),
        support_needs=col(row, "support_needs"),
        notes=col(row, "notes"),
        created_at=col(row, "created_at", ""),
        updated_at=col(row, "updated_at", ""),
    )


def _map_summary(row: Any) -> ApprenticeSummary:
    apprentice = _map(row)
    target = 0.0
    # Import here: the OTJ target depends on programme dates that are
    # already on the row, and a module-level import would make the
    # persistence layer depend on training at import time.
    from education_system.systems.apprenticeships.domain.training.off_the_job_hours import (
        target_hours,
    )

    target = target_hours(
        apprentice.start_date, apprentice.planned_end_date, apprentice.weekly_hours
    )
    return ApprenticeSummary(
        apprentice=apprentice,
        programme_title=col(row, "programme_title"),
        programme_reference=col(row, "programme_reference"),
        programme_level=col(row, "programme_level"),
        employer_name=col(row, "employer_name"),
        workplace_name=col(row, "workplace_name"),
        tutor_name=col(row, "tutor_name"),
        otj_hours_logged=to_float(col(row, "otj_approved")),
        otj_hours_target=target,
        ksbs_total=to_int(col(row, "ksbs_total")),
        ksbs_competent=to_int(col(row, "ksbs_competent")),
        open_reviews=to_int(col(row, "open_reviews")),
        gateway_status=col(row, "gateway_status") or "Not Ready",
    )


# ── Reads ───────────────────────────────────────────────────────────

def get(apprentice_id: int) -> Apprentice | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM apprentices WHERE apprentice_id = ?", (apprentice_id,)
        ).fetchone()
    return _map(row) if row else None


def get_summary(apprentice_id: int) -> ApprenticeSummary | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            f"{_SUMMARY_SELECT} WHERE a.apprentice_id = ?", (apprentice_id,)
        ).fetchone()
    return _map_summary(row) if row else None


def get_by_username(username: str) -> Apprentice | None:
    """Find the apprentice a login belongs to.

    Case-insensitive because usernames arrive from the shared auth
    layer, which does not normalise them.
    """
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM apprentices WHERE LOWER(username) = LOWER(?)", (username,)
        ).fetchone()
    return _map(row) if row else None


def get_by_uln(uln: str) -> Apprentice | None:
    init_db()
    with connect() as conn:
        row = conn.execute("SELECT * FROM apprentices WHERE uln = ?", (uln,)).fetchone()
    return _map(row) if row else None


def list_summaries(
    *,
    apprentice_id: int | None = None,
    status: str | None = None,
    statuses: list[str] | None = None,
    employer_id: int | None = None,
    programme_id: int | None = None,
    tutor_id: int | None = None,
    gateway_status: str | None = None,
    search: str | None = None,
    active_only: bool = False,
    limit: int | None = None,
) -> list[ApprenticeSummary]:
    """Cohort list with every label and derived figure the screens need.

    ``apprentice_id`` narrows to a single row. It exists so that
    ``access.apprentice_filters()`` — which yields that key for an
    apprentice actor — can be splatted into this call like any other
    scope, rather than every caller special-casing the one role whose
    cohort is themselves.
    """
    init_db()
    qb = QueryBuilder()
    qb.add_if(apprentice_id, "a.apprentice_id = ?", apprentice_id)
    qb.add_if(status, "a.status = ?", status)
    qb.add_in("a.status", statuses)
    qb.add_if(employer_id, "a.employer_id = ?", employer_id)
    qb.add_if(programme_id, "a.programme_id = ?", programme_id)
    qb.add_if(tutor_id, "a.tutor_id = ?", tutor_id)
    qb.add_if(gateway_status, "COALESCE(g.status, 'Not Ready') = ?", gateway_status)
    if active_only:
        qb.add("a.status IN ('On Programme', 'Gateway', 'EPA')")
    if search and search.strip():
        term = f"%{search.strip()}%"
        qb.add(
            "(a.given_name LIKE ? OR a.family_name LIKE ? OR a.uln LIKE ? "
            "OR a.email LIKE ? OR (a.given_name || ' ' || a.family_name) LIKE ?)",
            term, term, term, term, term,
        )
    sql = f"{_SUMMARY_SELECT} {qb.where} ORDER BY a.family_name, a.given_name"
    args = qb.args
    if limit:
        sql += " LIMIT ?"
        args = [*args, int(limit)]
    with connect() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [_map_summary(r) for r in rows]


def count_by_status() -> dict[str, int]:
    """How many apprentices sit in each status, for the dashboards."""
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM apprentices GROUP BY status"
        ).fetchall()
    return {r["status"]: r["n"] for r in rows}


def count_by_programme() -> list[tuple[str, int]]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """SELECT COALESCE(p.title, 'Unassigned') AS title, COUNT(*) AS n
                 FROM apprentices a
                 LEFT JOIN programmes p ON p.programme_id = a.programme_id
                GROUP BY p.title
                ORDER BY n DESC"""
        ).fetchall()
    return [(r["title"], r["n"]) for r in rows]


def count_by_employer(limit: int = 10) -> list[tuple[str, int]]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """SELECT COALESCE(e.name, 'Unassigned') AS name, COUNT(*) AS n
                 FROM apprentices a
                 LEFT JOIN employers e ON e.employer_id = a.employer_id
                GROUP BY e.name
                ORDER BY n DESC
                LIMIT ?""",
            (limit,),
        ).fetchall()
    return [(r["name"], r["n"]) for r in rows]


# ── Writes ──────────────────────────────────────────────────────────

def create(payload: dict[str, Any]) -> int:
    """Insert an apprentice and return the new id."""
    init_db()
    columns = [f for f in _FIELDS if f in payload]
    placeholders = ", ".join("?" for _ in columns)
    values = [payload[c] for c in columns]
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO apprentices ({', '.join(columns)}) VALUES ({placeholders})",
            values,
        )
        return int(cur.lastrowid)


def update(apprentice_id: int, payload: dict[str, Any]) -> None:
    """Update the supplied fields only; anything absent is untouched."""
    init_db()
    columns = [f for f in _FIELDS if f in payload]
    if not columns:
        return
    assignments = ", ".join(f"{c} = ?" for c in columns)
    values = [payload[c] for c in columns]
    with connect() as conn:
        conn.execute(
            f"UPDATE apprentices SET {assignments}, updated_at = datetime('now') "
            "WHERE apprentice_id = ?",
            [*values, apprentice_id],
        )


def delete(apprentice_id: int) -> None:
    """Remove an apprentice and everything hanging off them.

    Cascades handle the children. Reserved for correcting a mistaken
    enrolment — a real departure is a withdrawal, which keeps the record.
    """
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM apprentices WHERE apprentice_id = ?", (apprentice_id,))


def set_status(
    apprentice_id: int,
    new_status: str,
    *,
    from_status: str | None,
    reason: str | None,
    effective_date: str,
    actor: str | None,
    actual_end_date: str | None = None,
) -> None:
    """Move an apprentice's status and record the move in one transaction.

    The history row and the status column must agree, so they are
    written together — a crash between them would leave a record whose
    status nobody can account for.
    """
    init_db()
    with connect() as conn:
        if actual_end_date is not None:
            conn.execute(
                "UPDATE apprentices SET status = ?, actual_end_date = ?, "
                "updated_at = datetime('now') WHERE apprentice_id = ?",
                (new_status, actual_end_date, apprentice_id),
            )
        else:
            conn.execute(
                "UPDATE apprentices SET status = ?, updated_at = datetime('now') "
                "WHERE apprentice_id = ?",
                (new_status, apprentice_id),
            )
        conn.execute(
            """INSERT INTO apprentice_status_history
                   (apprentice_id, from_status, to_status, reason, effective_date, actor)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (apprentice_id, from_status, new_status, reason, effective_date, actor),
        )


def list_status_history(apprentice_id: int) -> list[StatusChange]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """SELECT * FROM apprentice_status_history
                WHERE apprentice_id = ?
                ORDER BY effective_date DESC, history_id DESC""",
            (apprentice_id,),
        ).fetchall()
    return [
        StatusChange(
            history_id=r["history_id"],
            apprentice_id=r["apprentice_id"],
            from_status=r["from_status"],
            to_status=r["to_status"],
            reason=r["reason"],
            effective_date=r["effective_date"],
            actor=r["actor"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


# ── Breaks in learning ──────────────────────────────────────────────

def add_break(
    apprentice_id: int,
    *,
    start_date: str,
    expected_return: str | None,
    reason: str,
    notes: str | None = None,
) -> int:
    init_db()
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO breaks_in_learning
                   (apprentice_id, start_date, expected_return, reason, notes)
               VALUES (?, ?, ?, ?, ?)""",
            (apprentice_id, start_date, expected_return, reason, notes),
        )
        return int(cur.lastrowid)


def end_break(apprentice_id: int, return_date: str) -> None:
    """Close the open break, if there is one."""
    init_db()
    with connect() as conn:
        conn.execute(
            """UPDATE breaks_in_learning SET actual_return = ?
                WHERE break_id = (
                    SELECT break_id FROM breaks_in_learning
                     WHERE apprentice_id = ? AND actual_return IS NULL
                     ORDER BY start_date DESC LIMIT 1)""",
            (return_date, apprentice_id),
        )


def list_breaks(apprentice_id: int) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM breaks_in_learning WHERE apprentice_id = ? "
            "ORDER BY start_date DESC",
            (apprentice_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def total_break_days(apprentice_id: int, as_of: str) -> int:
    """Days spent on breaks, so a planned end date can be pushed out."""
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT start_date, actual_return FROM breaks_in_learning "
            "WHERE apprentice_id = ?",
            (apprentice_id,),
        ).fetchall()
    from datetime import date

    total = 0
    for row in rows:
        try:
            start = date.fromisoformat(row["start_date"])
            end = date.fromisoformat(row["actual_return"] or as_of)
        except (TypeError, ValueError):
            continue
        total += max(0, (end - start).days)
    return total


# ── Withdrawals ─────────────────────────────────────────────────────

def add_withdrawal(
    apprentice_id: int,
    *,
    withdrawal_date: str,
    reason: str,
    last_activity_date: str | None = None,
    notes: str | None = None,
    recorded_by: str | None = None,
) -> int:
    init_db()
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO withdrawals
                   (apprentice_id, withdrawal_date, last_activity_date,
                    reason, notes, recorded_by)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (apprentice_id, withdrawal_date, last_activity_date, reason, notes, recorded_by),
        )
        return int(cur.lastrowid)


def list_withdrawals(
    *, apprentice_id: int | None = None, since: str | None = None
) -> list[dict[str, Any]]:
    init_db()
    qb = QueryBuilder()
    qb.add_if(apprentice_id, "w.apprentice_id = ?", apprentice_id)
    qb.add_if(since, "w.withdrawal_date >= ?", since)
    with connect() as conn:
        rows = conn.execute(
            f"""SELECT w.*, a.given_name, a.family_name
                  FROM withdrawals w
                  JOIN apprentices a ON a.apprentice_id = w.apprentice_id
                  {qb.where}
                 ORDER BY w.withdrawal_date DESC""",
            qb.args,
        ).fetchall()
    return [dict(r) for r in rows]
