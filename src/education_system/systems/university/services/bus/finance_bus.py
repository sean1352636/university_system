"""Cross-domain finance services + bus integration.

A small, dependency-free service layer that any GUI (Library, Research
portal, Course/Module enrolment, Exam scheduler) can call without
knowing Finance's schema. Mirrors the academics ``_cross_services``
pattern but for money flow.

Public surface:

- ``has_active_hold(student_id)``  → bool
- ``place_hold(...)``              → hold_id  + publishes EVENT_HOLD_CHANGED
- ``release_hold(...)``            → bool     + publishes EVENT_HOLD_CHANGED
- ``check_registration_holds(conn, ...)`` → refuses registration on an active
  hold unless a ``finance.hold_override`` holder overrides it with a reason
- ``raise_charge(...)``            → tx_id    + publishes EVENT_CHARGE_RAISED
- ``student_balance(student_id)``  → float
- ``grant_balance(grant_ref)``     → float

Schema lives in this module — ``finance_holds`` is created on first
call so callers don't need to coordinate migrations.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection

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
        from education_system.systems.university.infrastructure.event_bus import publish
        publish(event, **payload)
    except Exception as exc:
        logger.debug("finance bus publish failed for %s: %s", event, exc)


def _is_student(conn: sqlite3.Connection, student_id: str) -> bool:
    """Return True iff ``student_id`` exists in the ``students`` table.

    ``student_finance_transactions`` has a FK to ``students(student_id)``,
    so posting a ledger row for a non-student buyer (e.g. a staff/admin
    account buying a gym membership at the till) raises a FOREIGN KEY
    constraint error and leaves an orphan ``student_finance_accounts`` row.
    Callers use this to skip ledger writes for non-students cleanly.
    """
    try:
        return conn.execute(
            "SELECT 1 FROM students WHERE student_id = ? LIMIT 1",
            (student_id,),
        ).fetchone() is not None
    except Exception:
        # No students table / query error — be permissive and let the
        # caller's own try/except handle any downstream failure.
        return True


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
# Registration gate: active holds block annual and module registration unless
# someone holding the ``finance.hold_override`` capability overrides them
# with a reason. Works on the caller's connection so it can run inside the
# registration transaction (no executescript: that would commit it).
# ---------------------------------------------------------------------------

class FinanceHoldBlock(ValueError):
    """Registration refused because of active finance holds. ``holds`` lists
    them; the message gives every reason so staff and the student see why."""

    def __init__(self, holds: list[dict[str, Any]], *, can_override: bool = False):
        self.holds = holds
        self.can_override = can_override
        reasons = "; ".join(
            f"{h['reason']} (£{float(h.get('amount') or 0):,.2f}, placed "
            f"{str(h.get('placed_at') or '')[:10]})" for h in holds)
        super().__init__(
            "Registration is blocked by a finance hold: " + reasons
            + ". Please contact Student Finance to clear it"
            + (" (you can override it with a reason)" if can_override else "") + ".")


def _gate_schema(conn: sqlite3.Connection) -> None:
    conn.execute(_HOLDS_SCHEMA_SQL)
    for sql in _HOLDS_INDEX_SQL:
        conn.execute(sql)
    from education_system.systems.university.infrastructure.database.schemas import (
        student_fees_schema,
    )
    student_fees_schema.apply_to_connection(conn)


def holds_on(conn: sqlite3.Connection, student_id: str | int) -> list[dict[str, Any]]:
    """Active holds for the student, read on ``conn``."""
    _gate_schema(conn)
    cur = conn.execute(
        "SELECT hold_id, amount, reason, source, reference_id, placed_at, placed_by "
        "FROM finance_holds WHERE student_id = ? AND is_active = 1 ORDER BY placed_at DESC",
        (str(student_id),))
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def can_override_holds(conn: sqlite3.Connection, username: str | None,
                       role: str | None) -> bool:
    """Whether this person holds the ``finance.hold_override`` capability."""
    from education_system.systems.university.domains.finance.domain.tuition import access
    if not username:
        return False
    return access.holds(conn, access.Actor(str(username), str(role or "").lower()),
                        access.HOLD_OVERRIDE)


def _covering_override(conn, student_id: str, year: str, hold_ids: set[int]):
    for override_id, ids in conn.execute(
            "SELECT override_id, hold_ids FROM finance_hold_overrides WHERE student_id = ? "
            "AND academic_year = ? ORDER BY override_id DESC", (student_id, year)).fetchall():
        try:
            covered = {int(i) for i in json.loads(ids or "[]")}
        except (TypeError, ValueError):
            continue
        if hold_ids <= covered:
            return int(override_id)
    return None


def check_registration_holds(conn: sqlite3.Connection, student_id: str | int, *,
                             academic_year: str, context: str,
                             override_by: str | None = None, override_role: str | None = None,
                             override_reason: str | None = None) -> int | None:
    """Refuse registration while the student has active holds.

    Passes when there are none, or when an earlier override for this
    academic year already covers every active hold. Otherwise an override
    needs ``override_by`` holding ``finance.hold_override`` and a reason;
    it is recorded (and audited) and its id returned. Raises
    :class:`FinanceHoldBlock` when refused. Does not commit.
    """
    sid = str(student_id)
    holds = holds_on(conn, sid)
    if not holds:
        return None
    year = str(academic_year)
    hold_ids = {int(h["hold_id"]) for h in holds}
    existing = _covering_override(conn, sid, year, hold_ids)
    if existing is not None:
        return existing
    allowed = can_override_holds(conn, override_by, override_role)
    reason = (override_reason or "").strip()
    if not (allowed and reason):
        raise FinanceHoldBlock(holds, can_override=allowed)
    override_id = int(conn.execute(
        "INSERT INTO finance_hold_overrides (student_id, academic_year, context, hold_ids, "
        "reason, authorised_by, authorised_role) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (sid, year, context, json.dumps(sorted(hold_ids)), reason, override_by,
         override_role)).lastrowid)
    from education_system.systems.university.domains.finance.domain.tuition import access
    access.audit(conn, override_by, "hold.overridden", "finance_hold_override", override_id,
                 student_id=sid, detail={"context": context, "academic_year": year,
                                         "reason": reason, "holds": holds})
    return override_id


def hold_overrides(conn: sqlite3.Connection, student_id: str | int | None = None
                   ) -> list[dict[str, Any]]:
    """Recorded hold overrides, newest first."""
    _gate_schema(conn)
    sql = "SELECT * FROM finance_hold_overrides"
    params: tuple = ()
    if student_id is not None:
        sql += " WHERE student_id = ?"
        params = (str(student_id),)
    cur = conn.execute(sql + " ORDER BY override_id DESC", params)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


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
            # Only genuine students have a finance ledger (FK to
            # students.student_id); skip non-student buyers cleanly.
            if not _is_student(conn, sid):
                logger.debug(
                    "raise_charge: %s is not a student; "
                    "skipping ledger write", sid)
                return None

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
            # The student ledger only holds rows for genuine students
            # (FK to students.student_id). A paid-at-till sale to a
            # staff/admin buyer has nothing to record here — skip cleanly
            # rather than failing the FK and orphaning an account row.
            if not _is_student(conn, sid):
                logger.debug(
                    "record_paid_sale: %s is not a student; "
                    "skipping ledger write", sid)
                return None

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


# ---------------------------------------------------------------------------
# Posting port — the one door through which a domain service posts money
# it has just taken (or refunded) to Finance. Thin pass-throughs to
# ``finance.infrastructure.finance_integration`` and the GL hook, imported
# lazily so this module stays import-light and a domain can call it without
# reaching into the Finance slice directly.
# ---------------------------------------------------------------------------


_STUDENT_ACCOUNT_LABELS = frozenset({
    "finance_account", "student_account", "student account", "student finance",
    "student_finance", "student finance account", "student_finance_account",
})


def is_student_account_method(method: str | None) -> bool:
    """True when a payment/refund method label means "settle from the
    student's finance account" — GUIs and CLIs spell it several ways."""
    if not method:
        return False
    label = str(method).strip().lower()
    return label in _STUDENT_ACCOUNT_LABELS or label.startswith("student account (")


def record_payment(**kwargs: Any) -> int | None:
    """Post a completed cash/card payment to Finance's ``payments`` table.

    Same keyword surface as ``finance_integration.record_payment_to_finance``
    (student_id, amount, payment_method, transaction_source, transaction_ref,
    notes, created_by, ...). Returns the payment id, or ``None`` on failure;
    never raises, so a posting failure cannot roll back the caller's write.
    """
    try:
        from education_system.systems.university.domains.finance.infrastructure import (
            finance_integration,
        )
        return finance_integration.record_payment_to_finance(**kwargs)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Finance posting failed for %s/%s: %s",
                     kwargs.get("transaction_source"), kwargs.get("transaction_ref"), exc)
        return None


def pay_from_student_account(**kwargs: Any) -> dict[str, Any]:
    """Settle a charge from the student's finance account balance.

    Pass-through to ``finance_integration.process_student_finance_account_payment``
    (student_id, amount, description, transaction_source, transaction_ref,
    processed_by). It debits the balance and writes the ``payments`` row
    itself, so callers must not also ``record_payment`` for the same money.
    Returns the integration's result dict (``success``, ``message``,
    ``new_balance``, ``transaction_id``); never raises.
    """
    try:
        from education_system.systems.university.domains.finance.infrastructure import (
            finance_integration,
        )
        return finance_integration.process_student_finance_account_payment(**kwargs)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Student-account payment failed for %s: %s", kwargs.get("student_id"), exc)
        return {"success": False, "message": str(exc), "new_balance": None,
                "transaction_id": None}


def account_balance(student_id: str | int) -> float | None:
    """The student's finance account balance, or ``None`` when they have no
    account (unlike :func:`student_balance`, which reads that as 0.0) or it
    can't be read. Never raises."""
    if not student_id:
        return None
    try:
        from education_system.systems.university.domains.finance.infrastructure import (
            finance_integration,
        )
        return finance_integration.get_student_finance_account_balance(str(student_id))
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Could not read finance balance for %s: %s", student_id, exc)
        return None


def record_refund(**kwargs: Any) -> int | None:
    """Record a refund in Finance's ``unified_refunds`` (and the ledger).

    Same keyword surface as ``finance_integration.record_refund_to_finance``
    (student_id, refund_amount, original_payment_id, refund_reason,
    refund_type, transaction_source, transaction_ref, refund_method,
    requested_by, notes). Returns the refund id, or ``None`` on failure;
    never raises.
    """
    try:
        from education_system.systems.university.domains.finance.infrastructure import (
            finance_integration,
        )
        return finance_integration.record_refund_to_finance(**kwargs)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Finance refund failed for %s/%s: %s",
                     kwargs.get("transaction_source"), kwargs.get("transaction_ref"), exc)
        return None


def credit_student_account(**kwargs: Any) -> dict[str, Any]:
    """Credit (top up) a student's finance account — e.g. a refund paid back
    to the balance it came from.

    Pass-through to ``finance_integration.top_up_student_finance_account``
    (student_id, amount, payment_method, processed_by, description).
    Returns its result dict (``success``, ``message``, ``new_balance``);
    never raises.
    """
    try:
        from education_system.systems.university.domains.finance.infrastructure import (
            finance_integration,
        )
        return finance_integration.top_up_student_finance_account(**kwargs)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Crediting the finance account of %s failed: %s",
                     kwargs.get("student_id"), exc)
        return {"success": False, "message": str(exc), "new_balance": None}


def warn_if_low_balance(student_id: str | int, balance: float | None) -> bool:
    """E-mail the student Finance's low-balance warning when ``balance`` is
    under Finance's threshold. Returns whether a warning was sent; never
    raises."""
    if balance is None or not student_id:
        return False
    try:
        from education_system.systems.university.domains.finance.infrastructure import (
            finance_integration,
        )
        if float(balance) >= finance_integration.LOW_BALANCE_THRESHOLD:
            return False
        return bool(finance_integration.send_low_balance_email(str(student_id), float(balance)))
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Low-balance warning for %s not sent: %s", student_id, exc)
        return False


def ensure_student_account(student_id: str | int) -> bool:
    """Create the student's finance account if it does not exist yet."""
    try:
        from education_system.systems.university.domains.finance.infrastructure import (
            finance_integration,
        )
        return bool(finance_integration.ensure_student_finance_account_exists(str(student_id)))
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Could not ensure finance account for %s: %s", student_id, exc)
        return False


def notify_ledger(kind: str, row_id: int | None, *, posted_by: str | None = None) -> None:
    """Auto-post a ``payments`` / ``unified_refunds`` row to the GL.

    ``kind`` is ``'payment'`` or ``'refund'``. No-op when ``row_id`` is
    ``None`` or the ledger is not initialised; never raises (logged instead)
    so a GL hiccup cannot undo the operational write that preceded it.
    """
    if row_id is None:
        return
    try:
        from education_system.systems.university.domains.finance.domain.ledger import (
            notify_ledger as _notify,
        )
        _notify(kind, row_id, posted_by=posted_by or "auto")
    except Exception as exc:
        logger.warning("ledger hook failed for %s %s: %s", kind, row_id, exc)


__all__ = [
    "FinanceHoldBlock",
    "can_override_holds",
    "check_registration_holds",
    "hold_overrides",
    "holds_on",
    "has_active_hold",
    "list_active_holds",
    "place_hold",
    "release_hold",
    "raise_charge",
    "record_paid_sale",
    "student_balance",
    "grant_balance",
    "student_account_summary",
    "is_student_account_method",
    "record_payment",
    "pay_from_student_account",
    "ensure_student_account",
    "notify_ledger",
]
