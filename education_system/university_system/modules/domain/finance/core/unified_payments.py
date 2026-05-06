"""Unified payments writer / reader.

Single entry point for recording any payment in the system, regardless
of which domain (library, bursary, nailbar, general fees, …) it came
from. Writes to the central ``payments`` table only, tagged with
``source_type`` so cross-domain reports can SELECT one place instead
of UNION-ing per-domain tables.

Historically each domain had its own payment ledger
(``library_payments``, ``bursary_payments``, ``nailbar_payments``,
``library_fine_payments``, plus the now-dropped ``student_payments``).
The schema's polymorphic columns (``source_type``,
``source_payment_id``, ``payment_type``, ``reference_type``,
``reference_id``, ``department``) were always there for unification but
nothing wrote to them. 8.117.103 introduces this module and migrates
each domain to use it; subsequent revisions will retire the per-domain
tables.

Idempotency: ``(source_type, source_payment_id)`` is uniquely indexed
where ``source_payment_id`` is non-NULL, so re-mirroring the same
domain row is safe — the second call does an INSERT OR IGNORE and
leaves the original row untouched.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from education_system.university_system.infrastructure.database.db import (
    get_connection,
    transaction,
)


# ----------------------------------------------------------------------
# Schema bootstrap
# ----------------------------------------------------------------------

def ensure_unified_payments_index():
    """Create the ``(source_type, source_payment_id)`` unique index if
    it doesn't exist. Partial index (only rows where source_payment_id
    is non-NULL) so 'general' payments without a domain origin remain
    insertable without a UNIQUE collision."""
    with transaction() as conn:
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS "
            "idx_payments_source_unique "
            "ON payments(source_type, source_payment_id) "
            "WHERE source_payment_id IS NOT NULL"
        )


# ----------------------------------------------------------------------
# Writer
# ----------------------------------------------------------------------

def record_payment(
    *,
    student_id: str,
    amount: float,
    payment_method: str = "card",
    source_type: str = "general",
    source_payment_id: Optional[str] = None,
    payment_type: Optional[str] = None,
    reference_type: Optional[str] = None,
    reference_id: Optional[str] = None,
    department: Optional[str] = None,
    description: Optional[str] = None,
    notes: Optional[str] = None,
    payment_date: Optional[str] = None,
    status: str = "completed",
    currency: str = "GBP",
    created_by: Optional[str] = None,
) -> int:
    """Record a payment and return its ``payment_id``.

    Parameters
    ----------
    student_id, amount, payment_method
        Required for every payment.
    source_type
        Domain that owns this payment: ``'library'``, ``'library_fine'``,
        ``'bursary'``, ``'nailbar'``, ``'general'``, …
    source_payment_id
        Stable identifier in the source domain (e.g. the bursary
        award_id, the nailbar appointment_id, the library receipt_id).
        Combined with ``source_type`` for idempotency.
    payment_type, reference_type, reference_id, department
        Optional polymorphic tagging used by reports.
    description, notes
        Free-text fields surfaced by the receipt/log views.
    payment_date
        ``YYYY-MM-DD HH:MM:SS`` string. Defaults to "now".
    status
        Defaults to ``'completed'``. Use ``'pending'`` for scheduled
        payments that haven't settled yet.
    currency
        Defaults to ``'GBP'``.
    created_by
        Username of the person/service recording the payment.

    Returns
    -------
    int
        The new ``payments.payment_id``. If a row with the same
        ``(source_type, source_payment_id)`` already exists, returns
        the existing id rather than creating a duplicate.
    """
    if amount is None:
        raise ValueError("amount is required")
    if not student_id:
        raise ValueError("student_id is required")

    payment_date = payment_date or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    src_id_str = str(source_payment_id) if source_payment_id is not None else None

    with transaction() as conn:
        # Idempotency check — if the same (source_type, source_id)
        # was already recorded, return the existing payment_id.
        if src_id_str is not None:
            row = conn.execute(
                "SELECT payment_id FROM payments "
                "WHERE source_type = ? AND source_payment_id = ?",
                (source_type, src_id_str),
            ).fetchone()
            if row:
                return int(row[0])

        cursor = conn.execute(
            """
            INSERT INTO payments (
                student_id, amount, currency, payment_method,
                payment_date, status, notes,
                source_type, source_payment_id,
                payment_type, reference_type, reference_id,
                department, description,
                created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                student_id, amount, currency, payment_method,
                payment_date, status, notes,
                source_type, src_id_str,
                payment_type, reference_type, reference_id,
                department, description,
                created_by, now,
            ),
        )
        return int(cursor.lastrowid)


# ----------------------------------------------------------------------
# Reader
# ----------------------------------------------------------------------

def read_payments(
    *,
    source_type: Optional[str] = None,
    student_id: Optional[str] = None,
    reference_type: Optional[str] = None,
    reference_id: Optional[str] = None,
    source_payment_id: Optional[str] = None,
    limit: Optional[int] = None,
    order_desc: bool = True,
) -> List[Dict[str, Any]]:
    """Return rows from the unified ``payments`` table as dicts.

    All filters are optional and ANDed together. Pass nothing to get
    every payment.
    """
    sql = "SELECT * FROM payments WHERE 1=1"
    params: List[Any] = []
    if source_type is not None:
        sql += " AND source_type = ?"
        params.append(source_type)
    if student_id is not None:
        sql += " AND student_id = ?"
        params.append(student_id)
    if reference_type is not None:
        sql += " AND reference_type = ?"
        params.append(reference_type)
    if reference_id is not None:
        sql += " AND reference_id = ?"
        params.append(str(reference_id))
    if source_payment_id is not None:
        sql += " AND source_payment_id = ?"
        params.append(str(source_payment_id))
    sql += " ORDER BY payment_date " + ("DESC" if order_desc else "ASC")
    if limit:
        sql += " LIMIT ?"
        params.append(int(limit))

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
        cols = [d[0] for d in conn.execute("PRAGMA table_info(payments)").fetchall()]
        # Some Connection objects ship a Row factory; some return tuples.
        # Convert defensively.
        try:
            return [dict(r) for r in rows]
        except (TypeError, ValueError):
            return [dict(zip(cols, tuple(r))) for r in rows]


def sum_payments(
    *,
    source_type: Optional[str] = None,
    student_id: Optional[str] = None,
    reference_type: Optional[str] = None,
    reference_id: Optional[str] = None,
) -> float:
    """Sum of ``amount`` across the matching payments. Same filter
    shape as :func:`read_payments`."""
    sql = "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE 1=1"
    params: List[Any] = []
    if source_type is not None:
        sql += " AND source_type = ?"
        params.append(source_type)
    if student_id is not None:
        sql += " AND student_id = ?"
        params.append(student_id)
    if reference_type is not None:
        sql += " AND reference_type = ?"
        params.append(reference_type)
    if reference_id is not None:
        sql += " AND reference_id = ?"
        params.append(str(reference_id))

    with get_connection() as conn:
        row = conn.execute(sql, params).fetchone()
        return float(row[0]) if row else 0.0


__all__ = [
    "ensure_unified_payments_index",
    "record_payment",
    "read_payments",
    "sum_payments",
]
