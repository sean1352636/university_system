"""Funding records and the payment schedule."""

from __future__ import annotations

from typing import Any

from education_system.systems.apprenticeships.domain.funding.funding_rules import (
    FundingRecord,
    FundingSummary,
    Payment,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories.base import (
    QueryBuilder,
    col,
    connect,
    init_db,
    to_float,
)

_RECORD_FIELDS = (
    "apprentice_id", "funding_model", "band", "negotiated_price",
    "employer_contribution", "government_contribution", "additional_payments", "notes",
)

_PAYMENT_FIELDS = (
    "apprentice_id", "due_date", "amount", "payment_type", "status",
    "claimed_at", "paid_at", "notes",
)


def _map_record(row: Any) -> FundingRecord:
    return FundingRecord(
        funding_id=row["funding_id"],
        apprentice_id=row["apprentice_id"],
        funding_model=row["funding_model"],
        band=row["band"],
        negotiated_price=to_float(row["negotiated_price"]),
        employer_contribution=to_float(col(row, "employer_contribution")),
        government_contribution=to_float(col(row, "government_contribution")),
        additional_payments=to_float(col(row, "additional_payments")),
        notes=col(row, "notes"),
        created_at=col(row, "created_at", ""),
        updated_at=col(row, "updated_at", ""),
    )


def _map_payment(row: Any) -> Payment:
    return Payment(
        payment_id=row["payment_id"],
        apprentice_id=row["apprentice_id"],
        due_date=row["due_date"],
        amount=to_float(row["amount"]),
        payment_type=col(row, "payment_type", "Monthly"),
        status=col(row, "status", "Scheduled"),
        claimed_at=col(row, "claimed_at"),
        paid_at=col(row, "paid_at"),
        notes=col(row, "notes"),
        created_at=col(row, "created_at", ""),
    )


# ── Funding records ─────────────────────────────────────────────────

def get_record(apprentice_id: int) -> FundingRecord | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM funding_records WHERE apprentice_id = ?", (apprentice_id,)
        ).fetchone()
    return _map_record(row) if row else None


def upsert_record(apprentice_id: int, payload: dict[str, Any]) -> int:
    """Create or replace the funding record for one apprentice.

    There is exactly one per apprentice (a UNIQUE constraint enforces
    it), so a re-negotiation updates in place rather than adding a
    second row that reporting would double-count.
    """
    init_db()
    data = {**payload, "apprentice_id": apprentice_id}
    columns = [f for f in _RECORD_FIELDS if f in data]
    placeholders = ", ".join("?" for _ in columns)
    updates = ", ".join(f"{c} = excluded.{c}" for c in columns if c != "apprentice_id")
    with connect() as conn:
        cur = conn.execute(
            f"""INSERT INTO funding_records ({', '.join(columns)})
                VALUES ({placeholders})
                ON CONFLICT(apprentice_id) DO UPDATE SET
                    {updates}, updated_at = datetime('now')""",
            [data[c] for c in columns],
        )
        if cur.lastrowid:
            return int(cur.lastrowid)
        row = conn.execute(
            "SELECT funding_id FROM funding_records WHERE apprentice_id = ?",
            (apprentice_id,),
        ).fetchone()
        return int(row["funding_id"])


def delete_record(apprentice_id: int) -> None:
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM funding_records WHERE apprentice_id = ?", (apprentice_id,))


def list_records(
    *, funding_model: str | None = None, employer_id: int | None = None,
    programme_id: int | None = None,
) -> list[dict[str, Any]]:
    """Funding records with the labels the admin funding screen shows."""
    init_db()
    qb = QueryBuilder()
    qb.add_if(funding_model, "f.funding_model = ?", funding_model)
    qb.add_if(employer_id, "a.employer_id = ?", employer_id)
    qb.add_if(programme_id, "a.programme_id = ?", programme_id)
    with connect() as conn:
        rows = conn.execute(
            f"""SELECT f.*,
                       (a.given_name || ' ' || a.family_name) AS apprentice_name,
                       a.status AS apprentice_status,
                       e.name   AS employer_name,
                       p.title  AS programme_title,
                       (SELECT COALESCE(SUM(amount), 0) FROM funding_payments pay
                         WHERE pay.apprentice_id = f.apprentice_id AND pay.status = 'Paid')
                              AS paid_to_date
                  FROM funding_records f
                  JOIN apprentices a ON a.apprentice_id = f.apprentice_id
                  LEFT JOIN employers  e ON e.employer_id  = a.employer_id
                  LEFT JOIN programmes p ON p.programme_id = a.programme_id
                  {qb.where}
                 ORDER BY a.family_name, a.given_name""",
            qb.args,
        ).fetchall()
    return [dict(r) for r in rows]


# ── Payments ────────────────────────────────────────────────────────

def get_payment(payment_id: int) -> Payment | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM funding_payments WHERE payment_id = ?", (payment_id,)
        ).fetchone()
    return _map_payment(row) if row else None


def list_payments(
    *,
    apprentice_id: int | None = None,
    status: str | None = None,
    statuses: list[str] | None = None,
    employer_id: int | None = None,
    due_before: str | None = None,
    due_after: str | None = None,
    overdue_only: bool = False,
    limit: int | None = None,
) -> list[Payment]:
    init_db()
    qb = QueryBuilder()
    qb.add_if(apprentice_id, "p.apprentice_id = ?", apprentice_id)
    qb.add_if(status, "p.status = ?", status)
    qb.add_in("p.status", statuses)
    qb.add_if(employer_id, "a.employer_id = ?", employer_id)
    qb.add_if(due_before, "p.due_date <= ?", due_before)
    qb.add_if(due_after, "p.due_date >= ?", due_after)
    qb.add_if(overdue_only, "p.status = 'Scheduled' AND p.due_date < date('now')")
    sql = (
        f"""SELECT p.* FROM funding_payments p
              JOIN apprentices a ON a.apprentice_id = p.apprentice_id
              {qb.where}
             ORDER BY p.due_date, p.payment_id"""
    )
    args = qb.args
    if limit:
        sql += " LIMIT ?"
        args = [*args, int(limit)]
    with connect() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [_map_payment(r) for r in rows]


def replace_schedule(
    apprentice_id: int, schedule: list[tuple[str, float, str]]
) -> int:
    """Install a payment schedule, discarding any unsettled rows.

    Rebuilding on a date or price change is the only way to keep the
    schedule consistent, but claimed and paid instalments are real
    financial events — those are kept, and only the still-Scheduled
    rows are replaced.
    """
    init_db()
    with connect() as conn:
        conn.execute(
            "DELETE FROM funding_payments WHERE apprentice_id = ? AND status = 'Scheduled'",
            (apprentice_id,),
        )
        conn.executemany(
            """INSERT INTO funding_payments
                   (apprentice_id, due_date, amount, payment_type)
               VALUES (?, ?, ?, ?)""",
            [(apprentice_id, due, amount, kind) for due, amount, kind in schedule],
        )
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM funding_payments WHERE apprentice_id = ?",
            (apprentice_id,),
        ).fetchone()
    return int(row["n"])


def create_payment(payload: dict[str, Any]) -> int:
    init_db()
    columns = [f for f in _PAYMENT_FIELDS if f in payload]
    placeholders = ", ".join("?" for _ in columns)
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO funding_payments ({', '.join(columns)}) VALUES ({placeholders})",
            [payload[c] for c in columns],
        )
        return int(cur.lastrowid)


def update_payment(payment_id: int, payload: dict[str, Any]) -> None:
    init_db()
    columns = [f for f in _PAYMENT_FIELDS if f in payload]
    if not columns:
        return
    assignments = ", ".join(f"{c} = ?" for c in columns)
    with connect() as conn:
        conn.execute(
            f"UPDATE funding_payments SET {assignments} WHERE payment_id = ?",
            [*[payload[c] for c in columns], payment_id],
        )


def delete_payment(payment_id: int) -> None:
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM funding_payments WHERE payment_id = ?", (payment_id,))


def build_summary(apprentice_id: int) -> FundingSummary:
    return FundingSummary(
        record=get_record(apprentice_id),
        payments=list_payments(apprentice_id=apprentice_id),
    )


def totals(*, employer_id: int | None = None) -> dict[str, float]:
    """Headline money figures for the dashboards, in one pass."""
    init_db()
    qb = QueryBuilder()
    qb.add_if(employer_id, "a.employer_id = ?", employer_id)
    with connect() as conn:
        row = conn.execute(
            f"""SELECT
                   COALESCE(SUM(p.amount), 0)                                   AS scheduled,
                   COALESCE(SUM(CASE WHEN p.status = 'Paid'    THEN p.amount END), 0) AS paid,
                   COALESCE(SUM(CASE WHEN p.status = 'Claimed' THEN p.amount END), 0) AS claimed,
                   COALESCE(SUM(CASE WHEN p.status IN ('Withheld', 'Clawed Back')
                                     THEN p.amount END), 0)                     AS withheld,
                   COALESCE(SUM(CASE WHEN p.status = 'Scheduled'
                                      AND p.due_date < date('now')
                                     THEN p.amount END), 0)                     AS overdue
                 FROM funding_payments p
                 JOIN apprentices a ON a.apprentice_id = p.apprentice_id
                 {qb.where}""",
            qb.args,
        ).fetchone()
    return {
        "scheduled": to_float(row["scheduled"]),
        "paid": to_float(row["paid"]),
        "claimed": to_float(row["claimed"]),
        "withheld": to_float(row["withheld"]),
        "overdue": to_float(row["overdue"]),
    }


def contracted_value(*, employer_id: int | None = None) -> float:
    """Total negotiated price across live apprenticeships."""
    init_db()
    qb = QueryBuilder()
    qb.add("a.status IN ('On Programme', 'Gateway', 'EPA')")
    qb.add_if(employer_id, "a.employer_id = ?", employer_id)
    with connect() as conn:
        row = conn.execute(
            f"""SELECT COALESCE(SUM(f.negotiated_price), 0) AS total
                  FROM funding_records f
                  JOIN apprentices a ON a.apprentice_id = f.apprentice_id
                  {qb.where}""",
            qb.args,
        ).fetchone()
    return to_float(row["total"])
