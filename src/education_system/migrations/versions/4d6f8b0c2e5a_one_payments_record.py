"""university: one payments record — student_payments becomes a view over payments

``payments`` is the university's payment record: every writer goes through
``domains/finance/domain/core/unified_payments`` (idempotent on
``(source_type, source_payment_id)``) and the general ledger posts from it.
``student_payments`` was a one-off copy made by migration 0a7d9c3e5f21
(``provider='legacy'``, ``provider_reference='payments:<id>'``, amounts in
pence) that nothing has written since, so the two could only drift apart.

This migration:

* keeps every row of the copy that is not an exact mirror of a payment that
  still exists (a payment deleted since, or one whose student or amount
  differs) in ``archived_payments`` with the reason, so nothing is lost and
  nothing in ``payments`` is overwritten;
* replaces the ``student_payments`` table with a read-only view over
  ``payments`` (same columns, amounts in pence), and rebuilds the
  ``legacy_payments_compat`` view on ``payments`` directly.

Nothing references ``student_payments`` by foreign key. The partial index
``idx_payments_legal_student`` (legal payments only) is not a duplicate of
``idx_payments_student_id`` and both stay.

Revision ID: 4d6f8b0c2e5a
Revises: 3c5e7a9b1d4f
Create Date: 2026-10-18 10:00:00.000000

Idempotent.
"""
from typing import Sequence, Union

from alembic import op


revision: str = '4d6f8b0c2e5a'
down_revision: Union[str, Sequence[str], None] = '3c5e7a9b1d4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ARCHIVE_DDL = """CREATE TABLE IF NOT EXISTS archived_payments (
    id INTEGER PRIMARY KEY,
    student_id TEXT,
    amount REAL,
    payment_date TEXT,
    payment_method TEXT,
    category TEXT,
    status TEXT,
    archived_date TEXT DEFAULT CURRENT_TIMESTAMP
)"""

STUDENT_PAYMENTS_VIEW = """CREATE VIEW student_payments AS
    SELECT payment_id,
           student_id,
           COALESCE(currency, 'GBP') AS currency,
           CAST(ROUND(ABS(amount) * 100) AS INTEGER) AS amount_minor,
           COALESCE(NULLIF(gateway_name, ''), NULLIF(payment_method, ''),
                    COALESCE(source_type, 'general')) AS provider,
           'payments:' || payment_id AS provider_reference,
           CASE WHEN source_payment_id IS NOT NULL
                THEN COALESCE(source_type, 'general') || ':' || source_payment_id
                ELSE 'payments:' || payment_id END AS idempotency_key,
           status,
           payment_date AS received_at,
           COALESCE(created_at, payment_date) AS created_at
      FROM payments
     WHERE student_id IS NOT NULL AND amount IS NOT NULL AND ABS(amount) > 0"""

LEGACY_VIEW = """CREATE VIEW legacy_payments_compat AS
    SELECT payment_id, student_id, ABS(amount) AS amount,
           COALESCE(currency, 'GBP') AS currency,
           'payments:' || payment_id AS provider_reference, status,
           payment_date AS payment_date
      FROM payments"""


def _kind(execute, name):
    row = execute("SELECT type FROM sqlite_master WHERE name = ?", (name,)).fetchone()
    return row[0] if row else None


def _archive_unmatched(execute) -> int:
    """Copy rows of the old table that do not mirror a current payment."""
    execute(_ARCHIVE_DDL)
    kept = 0
    for sp_id, student, minor, provider, ref, status, received in execute(
            "SELECT payment_id, student_id, amount_minor, provider, provider_reference, status, "
            "received_at FROM student_payments").fetchall():
        reason = None
        target = None
        if provider == "legacy" and str(ref or "").startswith("payments:"):
            try:
                target = int(str(ref).split(":", 1)[1])
            except ValueError:
                target = None
        if target is None:
            reason = f"student_payments {sp_id}: not a copy of a payment ({provider}:{ref})"
        else:
            row = execute("SELECT student_id, amount FROM payments WHERE payment_id = ?",
                          (target,)).fetchone()
            if row is None:
                reason = (f"student_payments {sp_id}: copy of payment {target}, which no longer "
                          "exists in payments")
            elif str(row[0]) != str(student) or round(abs(float(row[1] or 0)) * 100) != minor:
                reason = (f"student_payments {sp_id}: differs from payment {target} "
                          f"(copy {student} {minor / 100:.2f}, payment {row[0]} "
                          f"{abs(float(row[1] or 0)):.2f})")
        if reason is None:
            continue
        if execute("SELECT 1 FROM archived_payments WHERE category = ?", (reason,)).fetchone():
            continue
        execute("INSERT INTO archived_payments (student_id, amount, payment_date, payment_method, "
                "category, status) VALUES (?, ?, ?, ?, ?, ?)",
                (student, (minor or 0) / 100.0, received, provider, reason, status))
        kept += 1
    return kept


def upgrade() -> None:
    execute = op.get_bind().exec_driver_sql
    if _kind(execute, "payments") != "table":
        return
    if _kind(execute, "legacy_payments_compat") == "view":
        execute("DROP VIEW legacy_payments_compat")
    if _kind(execute, "student_payments") == "table":
        _archive_unmatched(execute)
        execute("DROP TABLE student_payments")
    if _kind(execute, "student_payments") is None:
        execute(STUDENT_PAYMENTS_VIEW)
    if _kind(execute, "legacy_payments_compat") is None:
        execute(LEGACY_VIEW)


def downgrade() -> None:
    execute = op.get_bind().exec_driver_sql
    for view in ("legacy_payments_compat", "student_payments"):
        if _kind(execute, view) == "view":
            execute(f'DROP VIEW "{view}"')
    execute("""CREATE TABLE IF NOT EXISTS student_payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            currency TEXT NOT NULL,
            amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
            provider TEXT NOT NULL,
            provider_reference TEXT NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'pending',
            received_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (provider, provider_reference)
        )""")
    execute("""INSERT OR IGNORE INTO student_payments (student_id, currency, amount_minor,
                   provider, provider_reference, idempotency_key, status, received_at)
               SELECT student_id, COALESCE(currency, 'GBP'),
                      CAST(ROUND(ABS(amount) * 100) AS INTEGER), 'legacy',
                      'payments:' || payment_id, 'legacy:payments:' || payment_id,
                      COALESCE(status, 'received'), COALESCE(payment_date, CURRENT_TIMESTAMP)
                 FROM payments
                WHERE student_id IS NOT NULL AND amount IS NOT NULL AND ABS(amount) > 0""")
    execute("""CREATE VIEW IF NOT EXISTS legacy_payments_compat AS
           SELECT payment_id, student_id, amount_minor / 100.0 AS amount,
                  currency, provider_reference, status,
                  received_at AS payment_date
             FROM student_payments""")
