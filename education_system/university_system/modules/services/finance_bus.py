"""Cross-domain finance services + bus integration.

A small, dependency-free service layer that any GUI (Library, Research
portal, Course/Module enrolment, Exam scheduler) can call without
knowing Finance's schema. Mirrors the academics ``_cross_services``
pattern but for money flow.

Public surface:

- ``has_active_hold(student_id)``  → bool
- ``place_hold(...)``              → hold_id  + publishes EVENT_HOLD_CHANGED
- ``release_hold(...)``            → bool     + publishes EVENT_HOLD_CHANGED
- ``raise_charge(...)``            → tx_id    + publishes EVENT_CHARGE_RAISED
- ``student_balance(student_id)``  → float
- ``grant_balance(grant_ref)``     → float

Schema lives in this module — ``finance_holds`` is created on first
call so callers don't need to coordinate migrations.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from education_system.university_system.infrastructure.database.db import sqlite3, get_connection

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_HOLDS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS finance_holds (
    hold_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL,
    amount       REAL NOT NULL DEFAULT 0,
    reason       TEXT NOT NULL,
    source       TEXT NOT NULL,
    reference_id TEXT,
    is_active    INTEGER NOT NULL DEFAULT 1,
    placed_at    TEXT NOT NULL,
    released_at  TEXT,
    placed_by    TEXT,
    released_by  TEXT
)
"""

_HOLDS_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_finance_holds_student "
    "ON finance_holds(student_id, is_active)",
)


def _ensure_holds_table(conn: sqlite3.Connection) -> None:
    conn.executescript(_HOLDS_SCHEMA_SQL)
    for sql in _HOLDS_INDEX_SQL:
        conn.execute(sql)


# ---------------------------------------------------------------------------
# Bus helper
# ---------------------------------------------------------------------------

def _publish(event: str, **payload: Any) -> None:
    """Best-effort publish — never raise out of a finance call."""
    try:
        from education_system.university_system.modules.domain.academics.gui._event_bus import publish
        publish(event, **payload)
    except Exception as exc:
        logger.debug("finance bus publish failed for %s: %s", event, exc)


# ---------------------------------------------------------------------------
# Holds
# ---------------------------------------------------------------------------

def has_active_hold(student_id: str | int) -> bool:
    """Return True if the student has any active enrolment-blocking hold."""
    if not student_id:
        return False
    sid = str(student_id)
    try:
        with get_connection() as conn:
            _ensure_holds_table(conn)
            row = conn.execute(
                "SELECT 1 FROM finance_holds "
                "WHERE student_id = ? AND is_active = 1 LIMIT 1",
                (sid,),
            ).fetchone()
            return row is not None
    except Exception as exc:
        logger.warning("has_active_hold(%s) failed: %s — treating as no hold",
                       student_id, exc)
        return False


def list_active_holds(student_id: str | int) -> list[dict[str, Any]]:
    """Return all active holds for the student. Empty list on any failure."""
    if not student_id:
        return []
    sid = str(student_id)
    try:
        with get_connection() as conn:
            _ensure_holds_table(conn)
            rows = conn.execute(
                "SELECT hold_id, amount, reason, source, reference_id, "
                "       placed_at, placed_by "
                "FROM finance_holds "
                "WHERE student_id = ? AND is_active = 1 "
                "ORDER BY placed_at DESC",
                (sid,),
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception as exc:
        logger.warning("list_active_holds(%s) failed: %s", student_id, exc)
        return []


def place_hold(
    student_id: str | int,
    *,
    reason: str,
    source: str,
    amount: float = 0.0,
    reference_id: str | None = None,
    placed_by: str | None = None,
) -> int | None:
    """Place a hold on the student. Returns the new hold_id."""
    sid = str(student_id)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with get_connection() as conn:
            _ensure_holds_table(conn)
            cur = conn.execute(
                "INSERT INTO finance_holds "
                "(student_id, amount, reason, source, reference_id, "
                " is_active, placed_at, placed_by) "
                "VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                (sid, float(amount), reason, source,
                 reference_id, now, placed_by),
            )
            conn.commit()
            hold_id = cur.lastrowid
    except Exception as exc:
        logger.warning("place_hold failed: %s", exc)
        return None

    _publish(
        "finance.hold.changed",
        hold_id=hold_id, student_id=sid, action="placed",
        source=source, reason=reason, amount=float(amount),
    )
    return hold_id


def release_hold(hold_id: int, *, released_by: str | None = None) -> bool:
    """Release an active hold. Idempotent — returns False if already released."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    student_id: str | None = None
    try:
        with get_connection() as conn:
            _ensure_holds_table(conn)
            row = conn.execute(
                "SELECT student_id, is_active FROM finance_holds WHERE hold_id = ?",
                (hold_id,),
            ).fetchone()
            if not row or not row["is_active"]:
                return False
            student_id = row["student_id"]
            conn.execute(
                "UPDATE finance_holds SET is_active = 0, "
                "       released_at = ?, released_by = ? "
                "WHERE hold_id = ?",
                (now, released_by, hold_id),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("release_hold(%s) failed: %s", hold_id, exc)
        return False

    _publish(
        "finance.hold.changed",
        hold_id=hold_id, student_id=student_id, action="released",
    )
    return True


# ---------------------------------------------------------------------------
# Charges
# ---------------------------------------------------------------------------

def raise_charge(
    student_id: str | int,
    amount: float,
    *,
    source: str,
    description: str,
    reference_id: str | None = None,
    processed_by: str | None = None,
) -> int | None:
    """Post a charge to the student's finance account.

    Writes a debit row to ``student_finance_transactions`` and updates
    the running balance on ``student_finance_accounts``. Best-effort —
    the bus event still fires even if the row insert can't update the
    balance (so subscribers always learn about the charge).
    """
    if not student_id or amount is None:
        return None
    sid = str(student_id)
    amt = float(amount)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tx_id: int | None = None

    try:
        with get_connection() as conn:
            # Ensure the student has an account row.
            acc = conn.execute(
                "SELECT account_id, balance FROM student_finance_accounts "
                "WHERE student_id = ? LIMIT 1",
                (sid,),
            ).fetchone()
            if acc is None:
                conn.execute(
                    "INSERT INTO student_finance_accounts "
                    "(student_id, balance, currency, account_status, "
                    " created_at, updated_at) "
                    "VALUES (?, 0, 'GBP', 'active', ?, ?)",
                    (sid, now, now),
                )
                acc = conn.execute(
                    "SELECT account_id, balance FROM student_finance_accounts "
                    "WHERE student_id = ? LIMIT 1",
                    (sid,),
                ).fetchone()

            account_id = acc["account_id"]
            balance_before = float(acc["balance"] or 0)
            balance_after = balance_before - amt  # debit lowers balance

            cur = conn.execute(
                "INSERT INTO student_finance_transactions "
                "(account_id, student_id, transaction_type, amount, "
                " balance_before, balance_after, description, "
                " reference_id, processed_by, created_at) "
                "VALUES (?, ?, 'charge', ?, ?, ?, ?, ?, ?, ?)",
                (account_id, sid, amt, balance_before, balance_after,
                 description, reference_id, processed_by, now),
            )
            tx_id = cur.lastrowid
            conn.execute(
                "UPDATE student_finance_accounts "
                "SET balance = ?, updated_at = ? WHERE account_id = ?",
                (balance_after, now, account_id),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("raise_charge(%s, %s) failed: %s", student_id, amount, exc)

    _publish(
        "finance.charge.raised",
        tx_id=tx_id, student_id=sid, amount=amt,
        source=source, description=description,
        reference_id=reference_id,
    )
    return tx_id


# ---------------------------------------------------------------------------
# Paid-in-full sales (informational; do NOT mutate the running balance)
# ---------------------------------------------------------------------------

def record_paid_sale(
    student_id: str | int,
    amount: float,
    *,
    source: str,
    description: str,
    reference_id: str | None = None,
    processed_by: str | None = None,
) -> int | None:
    """Record a sale that has already been paid at the till.

    Unlike :func:`raise_charge`, this writes a ``transaction_type='sale'``
    row whose ``balance_before == balance_after`` so it appears in the
    student's transaction history but does not create phantom debt.

    Used by Cinema / Gym / Restaurant / Shop after a successful POS
    payment. Use :func:`raise_charge` only for genuinely deferred
    obligations (e.g. monthly rent, an apprenticeship levy invoice).

    Still publishes ``finance.charge.raised`` so the Finance GUI's
    bus subscriber refreshes — the event payload includes
    ``kind='sale'`` so subscribers can distinguish it from a charge.
    """
    if not student_id or amount is None:
        return None
    sid = str(student_id)
    amt = float(amount)
    if amt <= 0:
        return None
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tx_id: int | None = None

    try:
        with get_connection() as conn:
            acc = conn.execute(
                "SELECT account_id, balance FROM student_finance_accounts "
                "WHERE student_id = ? LIMIT 1",
                (sid,),
            ).fetchone()
            if acc is None:
                conn.execute(
                    "INSERT INTO student_finance_accounts "
                    "(student_id, balance, currency, account_status, "
                    " created_at, updated_at) "
                    "VALUES (?, 0, 'GBP', 'active', ?, ?)",
                    (sid, now, now),
                )
                acc = conn.execute(
                    "SELECT account_id, balance FROM student_finance_accounts "
                    "WHERE student_id = ? LIMIT 1",
                    (sid,),
                ).fetchone()

            account_id = acc["account_id"]
            balance = float(acc["balance"] or 0)

            cur = conn.execute(
                "INSERT INTO student_finance_transactions "
                "(account_id, student_id, transaction_type, amount, "
                " balance_before, balance_after, description, "
                " reference_id, processed_by, created_at) "
                "VALUES (?, ?, 'sale', ?, ?, ?, ?, ?, ?, ?)",
                (account_id, sid, amt, balance, balance, description,
                 reference_id, processed_by, now),
            )
            tx_id = cur.lastrowid
            conn.commit()
    except Exception as exc:
        logger.warning("record_paid_sale(%s, %s) failed: %s",
                       student_id, amount, exc)
        return None

    _publish(
        "finance.charge.raised",
        tx_id=tx_id, student_id=sid, amount=amt,
        source=source, description=description,
        reference_id=reference_id, kind="sale",
    )
    return tx_id


# ---------------------------------------------------------------------------
# Balances
# ---------------------------------------------------------------------------

def student_balance(student_id: str | int) -> float:
    """Return the student's finance balance. ``0.0`` if no row exists."""
    if not student_id:
        return 0.0
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COALESCE(balance, 0) FROM student_finance_accounts "
                "WHERE student_id = ? LIMIT 1",
                (str(student_id),),
            ).fetchone()
            return float(row[0]) if row else 0.0
    except Exception as exc:
        logger.warning("student_balance(%s) failed: %s", student_id, exc)
        return 0.0


def grant_balance(grant_ref: str | int) -> float:
    """Return the remaining budget for a research grant.

    Reads ``research_projects.total_budget`` and subtracts every
    transaction in ``student_finance_transactions`` whose
    ``reference_id`` matches the grant reference. Returns 0.0 on any
    error or unknown grant.
    """
    if not grant_ref:
        return 0.0
    ref = str(grant_ref)
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COALESCE(total_budget, 0) FROM research_projects "
                "WHERE project_id = ? OR funding_source = ? LIMIT 1",
                (ref, ref),
            ).fetchone()
            budget = float(row[0]) if row else 0.0
            spent = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) "
                "FROM student_finance_transactions "
                "WHERE reference_id = ? AND transaction_type = 'charge'",
                (ref,),
            ).fetchone()
            return budget - float(spent[0] or 0)
    except Exception as exc:
        logger.warning("grant_balance(%s) failed: %s", grant_ref, exc)
        return 0.0


# ---------------------------------------------------------------------------
# Unified student account summary
# ---------------------------------------------------------------------------

def student_account_summary(student_id: str | int,
                            *, days: int = 365) -> dict[str, Any]:
    """Return a single dict combining balance, holds, and recent
    transactions grouped by source. Pulls in housing and SU charges
    via their bus modules so the Finance GUI doesn't need to know
    those schemas.

    Shape::

        {
          "student_id": "S12345",
          "balance": -120.0,
          "active_holds": [...],
          "transactions_by_source": {
              "housing_rent": [...],
              "su_membership": [...],
              "library": [...],
          },
          "totals_by_source": {"housing_rent": 540.0, ...},
        }
    """
    sid = str(student_id) if student_id is not None else ""
    summary: dict[str, Any] = {
        "student_id": sid,
        "balance": student_balance(sid),
        "active_holds": list_active_holds(sid),
        "transactions_by_source": {},
        "totals_by_source": {},
    }
    if not sid:
        return summary

    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT transaction_id, transaction_type, amount, "
                "       description, reference_id, created_at "
                "FROM student_finance_transactions "
                "WHERE student_id = ? "
                "  AND created_at >= date('now', ?) "
                "ORDER BY created_at DESC",
                (sid, f"-{int(days)} days"),
            ).fetchall()
    except Exception as exc:
        logger.warning("student_account_summary(%s) failed: %s", sid, exc)
        return summary

    by_src: dict[str, list[dict[str, Any]]] = {}
    totals: dict[str, float] = {}
    for r in rows:
        d = dict(r)
        ref = d.get("reference_id") or ""
        if ref.startswith("club:"):
            src = "su_membership"
        elif ref.startswith("asg:"):
            src = "housing"
        else:
            src = (d.get("description") or "other").split()[0].lower() \
                if d.get("description") else "other"
        by_src.setdefault(src, []).append(d)
        if d.get("transaction_type") == "charge":
            totals[src] = totals.get(src, 0.0) + float(d.get("amount") or 0)

    summary["transactions_by_source"] = by_src
    summary["totals_by_source"] = totals
    return summary


__all__ = [
    "has_active_hold",
    "list_active_holds",
    "place_hold",
    "release_hold",
    "raise_charge",
    "record_paid_sale",
    "student_balance",
    "grant_balance",
    "student_account_summary",
]
