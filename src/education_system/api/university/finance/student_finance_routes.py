"""Student finance routes: accounts and transactions."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.platform.delivery.api.university.auth import (
    authorize_object,
    current_subject_id,
    require_staff,
    token_required,
)
from education_system.platform.delivery.api.university.pagination import get_pagination_params, paginated_response
from education_system.systems.university.infrastructure.exceptions import ValidationError
from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity

logger = logging.getLogger(__name__)

student_finance_bp = Blueprint("student_finance", __name__, url_prefix="/api/student-finance")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


#: Reading finance records belonging to somebody else. Held by ``admin`` and
#: ``staff``.
FINANCE_OVERSIGHT = "manage_students_finance"

#: Changing money: opening or closing accounts, moving balances, posting
#: transactions, raising or writing off fees. Held by ``admin`` only, so a
#: read-only finance role cannot alter a balance.
FINANCE_MUTATE = "manage_finances"


def _forbidden(detail: str = "Forbidden"):
    return jsonify({"error": detail, "status": 403}), 403


def _may_read_any_finance() -> bool:
    return require_staff(permission=FINANCE_OVERSIGHT) is None


def _require_finance_mutation():
    """Gate every money-moving endpoint. Returns a response, or None to allow.

    These endpoints carried only ``@token_required``, which meant any account
    on the system — including every student — could open an account with an
    arbitrary opening balance, rewrite another account's balance, post
    positive or negative transactions, and stamp them with a forged
    ``processed_by``. Money movement now needs an explicit finance capability.
    """
    denial = require_staff(permission=FINANCE_MUTATE)
    if denial is not None:
        logger.warning(
            "Refused finance mutation by %r (role %r): %s capability required",
            (g.current_user or {}).get("sub"), (g.current_user or {}).get("role"),
            FINANCE_MUTATE,
        )
    return denial


def _scope_student(requested):
    """Restrict a listing to the caller's own records unless they hold
    oversight. Returns ``(student_id, denial)``.

    ``student_id`` is TEXT on all three finance tables (e.g. "S12345"), which
    is the student's username, so ``sub`` is the right key.
    """
    if _may_read_any_finance():
        return requested, None
    me = current_subject_id()
    if not me:
        return None, _forbidden()
    return me, None


def _guard_row(row, field: str = "student_id"):
    """Owner-or-finance-staff check for a single fetched record."""
    return authorize_object(row[field], permission=FINANCE_OVERSIGHT)


# ---- accounts ----

@student_finance_bp.route("/accounts", methods=["GET"])
@token_required
def list_accounts():
    account_status = request.args.get("account_status")
    student_id = request.args.get("student_id")

    student_id, denial = _scope_student(student_id)
    if denial is not None:
        return denial

    with get_connection() as conn:
        conditions = []
        params: list = []
        if account_status:
            conditions.append("account_status = ?")
            params.append(account_status)
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM student_finance_accounts" + where + " ORDER BY account_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM student_finance_accounts" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "student_finance_accounts", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@student_finance_bp.route("/accounts/<int:account_id>", methods=["GET"])
@token_required
def get_account(account_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_finance_accounts WHERE account_id = ?", (account_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Finance account {account_id} not found")

    denial = _guard_row(row)
    if denial is not None:
        return denial

    log_activity("view", "student_finance_account", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@student_finance_bp.route("/accounts", methods=["POST"])
@token_required
def create_account():
    denial = _require_finance_mutation()
    if denial is not None:
        return denial

    data = request.get_json(silent=True) or {}
    if "student_id" not in data:
        raise ValidationError("Missing required field: student_id")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO student_finance_accounts
               (student_id, balance, currency, account_status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data["student_id"], data.get("balance", 0.00),
             data.get("currency", "GBP"), data.get("account_status", "active"),
             now, now),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_finance_accounts WHERE account_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "student_finance_account", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@student_finance_bp.route("/accounts/<int:account_id>", methods=["PUT"])
@token_required
def update_account(account_id: int):
    denial = _require_finance_mutation()
    if denial is not None:
        return denial

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM student_finance_accounts WHERE account_id = ?", (account_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Finance account {account_id} not found")

    data = request.get_json(silent=True) or {}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    allowed = ["balance", "currency", "account_status"]
    sets = ["updated_at = ?"]
    params: list = [now]
    for key in allowed:
        if key in data:
            sets.append(f"{key} = ?")
            params.append(data[key])
    params.append(account_id)

    with transaction() as conn:
        # db-audit: ignore[DBW001] - join over a code-controlled list
        conn.execute(
            f"UPDATE student_finance_accounts SET {', '.join(sets)} WHERE account_id = ?",
            params,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_finance_accounts WHERE account_id = ?", (account_id,)
        ).fetchone()

    log_activity("update", "student_finance_account", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- transactions ----

@student_finance_bp.route("/transactions", methods=["GET"])
@token_required
def list_transactions():
    account_id = request.args.get("account_id")
    student_id = request.args.get("student_id")
    transaction_type = request.args.get("transaction_type")

    student_id, denial = _scope_student(student_id)
    if denial is not None:
        return denial

    with get_connection() as conn:
        conditions = []
        params: list = []
        if account_id:
            conditions.append("account_id = ?")
            params.append(account_id)
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if transaction_type:
            conditions.append("transaction_type = ?")
            params.append(transaction_type)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM student_finance_transactions" + where + " ORDER BY transaction_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM student_finance_transactions" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "student_finance_transactions", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@student_finance_bp.route("/transactions/<int:transaction_id>", methods=["GET"])
@token_required
def get_transaction(transaction_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_finance_transactions WHERE transaction_id = ?", (transaction_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Transaction {transaction_id} not found")

    denial = _guard_row(row)
    if denial is not None:
        return denial

    log_activity("view", "student_finance_transaction", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@student_finance_bp.route("/transactions", methods=["POST"])
@token_required
def create_transaction():
    denial = _require_finance_mutation()
    if denial is not None:
        return denial

    data = request.get_json(silent=True) or {}
    for field in ["account_id", "student_id", "transaction_type", "amount"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        account = conn.execute(
            "SELECT student_id FROM student_finance_accounts WHERE account_id = ?",
            (data["account_id"],),
        ).fetchone()
        if not account:
            raise ValidationError(f"Finance account {data['account_id']} not found")
        account_student_id = str(account["student_id"])
        if str(data["student_id"]) != account_student_id:
            raise ValidationError("student_id does not own the finance account")

        conn.execute(
            """INSERT INTO student_finance_transactions
               (account_id, student_id, transaction_type, amount,
                description, reference_id, processed_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["account_id"], account_student_id, data["transaction_type"],
             data["amount"], data.get("description", ""),
             data.get("reference_id", ""),
             # Attribution is the authenticated operator, never a body field:
             # a forged processed_by makes the audit trail worthless.
             g.current_user.get("sub", ""), now),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_finance_transactions WHERE transaction_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "student_finance_transaction", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@student_finance_bp.route("/accounts/<int:account_id>", methods=["DELETE"])
@token_required
def delete_account(account_id: int):
    denial = _require_finance_mutation()
    if denial is not None:
        return denial

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM student_finance_accounts WHERE account_id = ?", (account_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Finance account {account_id} not found")

    with transaction() as conn:
        conn.execute("DELETE FROM student_finance_accounts WHERE account_id = ?", (account_id,))

    log_activity("delete", "student_finance_account", user=g.current_user.get("sub"))
    return jsonify({"message": "Account deleted"})


# ---- fees (service-layer table: student_fees) ----

@student_finance_bp.route("/fees", methods=["GET"])
@token_required
def list_fees():
    student_id = request.args.get("student_id")

    student_id, denial = _scope_student(student_id)
    if denial is not None:
        return denial

    with get_connection() as conn:
        conditions = []
        params: list = []
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM student_fees" + where + " ORDER BY student_fee_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM student_fees" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "student_fees", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@student_finance_bp.route("/fees/<int:fee_id>", methods=["GET"])
@token_required
def get_fee(fee_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_fees WHERE student_fee_id = ?", (fee_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Fee record {fee_id} not found")

    denial = _guard_row(row)
    if denial is not None:
        return denial

    log_activity("view", "student_fee", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@student_finance_bp.route("/fees", methods=["POST"])
@token_required
def create_fee():
    denial = _require_finance_mutation()
    if denial is not None:
        return denial

    data = request.get_json(silent=True) or {}
    if "student_id" not in data:
        raise ValidationError("Missing required field: student_id")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Whitelist of valid student_fees columns; 'description' and 'academic_year'
    # are not on the table and were dropped (the previous list silently broke
    # callers that posted them). 'fee_type' was renamed to 'fee_type_id' to
    # match the actual FK column.
    allowed = ["student_id", "fee_type_id", "amount", "currency", "due_date", "status"]
    cols = []
    vals = []
    for key in allowed:
        if key in data:
            cols.append(key)
            vals.append(data[key])

    with transaction() as conn:
        placeholders = ", ".join("?" for _ in cols)
        # db-audit: ignore[DBW001] - join over a code-controlled list; literal collection
        conn.execute(
            f"INSERT INTO student_fees ({', '.join(cols)}) VALUES ({placeholders})",
            vals,
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Auto-post AR + revenue to GL (never raises; no-op if SQL above didn't actually
    # produce a usable row, e.g. when the caller posts a 'fee_type' key that the
    # current schema doesn't have).
    try:
        from education_system.systems.university.domains.finance.domain.ledger import notify_ledger
        notify_ledger("fee_assignment", new_id, posted_by=g.current_user.get("sub") or "api")
    except Exception as _e:
        import logging
        logging.getLogger(__name__).warning("ledger hook failed: %s", _e)

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_fees WHERE student_fee_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "student_fee", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@student_finance_bp.route("/fees/<int:fee_id>", methods=["PUT"])
@token_required
def update_fee(fee_id: int):
    denial = _require_finance_mutation()
    if denial is not None:
        return denial

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM student_fees WHERE student_fee_id = ?", (fee_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Fee record {fee_id} not found")

    data = request.get_json(silent=True) or {}
    allowed = ["fee_type_id", "amount", "currency", "due_date", "status"]
    sets = []
    params: list = []
    for key in allowed:
        if key in data:
            sets.append(f"{key} = ?")
            params.append(data[key])
    if not sets:
        raise ValidationError("No valid fields to update")
    params.append(fee_id)

    with transaction() as conn:
        # db-audit: ignore[DBW001] - join over a code-controlled list
        conn.execute(
            f"UPDATE student_fees SET {', '.join(sets)} WHERE student_fee_id = ?", params
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_fees WHERE student_fee_id = ?", (fee_id,)
        ).fetchone()

    log_activity("update", "student_fee", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@student_finance_bp.route("/fees/<int:fee_id>", methods=["DELETE"])
@token_required
def delete_fee(fee_id: int):
    denial = _require_finance_mutation()
    if denial is not None:
        return denial

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM student_fees WHERE student_fee_id = ?", (fee_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Fee record {fee_id} not found")

    with transaction() as conn:
        conn.execute("DELETE FROM student_fees WHERE student_fee_id = ?", (fee_id,))

    log_activity("delete", "student_fee", user=g.current_user.get("sub"))
    return jsonify({"message": "Fee record deleted"})
