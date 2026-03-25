"""Betting routes: accounts, sports bets, prediction markets, and responsible limits."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

betting_bp = Blueprint("betting", __name__, url_prefix="/api/betting")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- accounts ----

@betting_bp.route("/accounts", methods=["GET"])
@token_required
def list_accounts():
    search = request.args.get("search")
    account_status = request.args.get("account_status")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM betting_accounts WHERE username LIKE ? OR email LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if account_status:
            conditions.append("account_status = ?")
            params.append(account_status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM betting_accounts" + where + " ORDER BY account_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM betting_accounts" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "betting_accounts", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@betting_bp.route("/accounts/<int:account_id>", methods=["GET"])
@token_required
def get_account(account_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM betting_accounts WHERE account_id = ?", (account_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"accounts {account_id} not found")
    log_activity("view", "betting_accounts", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@betting_bp.route("/accounts", methods=["POST"])
@token_required
def create_account():
    data = request.get_json(silent=True) or {}
    for field in ["user_id", "username", "email"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO betting_accounts
               (user_id, username, email, created_at)
               VALUES (?, ?, ?, ?)""",
            (data["user_id"], data["username"], data["email"], now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM betting_accounts WHERE account_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "betting_accounts", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- bets ----

@betting_bp.route("/bets", methods=["GET"])
@token_required
def list_bets():
    search = request.args.get("search")
    account_id = request.args.get("account_id")
    status = request.args.get("status")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM sports_bets WHERE event_name LIKE ?",
                (pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if account_id:
            conditions.append("account_id = ?")
            params.append(account_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM sports_bets" + where + " ORDER BY bet_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM sports_bets" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "sports_bets", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@betting_bp.route("/bets/<int:bet_id>", methods=["GET"])
@token_required
def get_bet(bet_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sports_bets WHERE bet_id = ?", (bet_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"bets {bet_id} not found")
    log_activity("view", "sports_bets", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@betting_bp.route("/bets", methods=["POST"])
@token_required
def create_bet():
    data = request.get_json(silent=True) or {}
    for field in ["account_id", "event_id", "event_name", "odds_value", "bet_amount"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO sports_bets
               (account_id, event_id, event_name, odds_value, bet_amount, odds_type, potential_payout, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["account_id"], data["event_id"], data["event_name"], data["odds_value"], data["bet_amount"], data.get("odds_type", ""), data.get("potential_payout", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sports_bets WHERE bet_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "sports_bets", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- markets ----

@betting_bp.route("/markets", methods=["GET"])
@token_required
def list_markets():
    search = request.args.get("search")
    category = request.args.get("category")
    status = request.args.get("status")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM prediction_markets WHERE title LIKE ? OR description LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if category:
            conditions.append("category = ?")
            params.append(category)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM prediction_markets" + where + " ORDER BY market_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM prediction_markets" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "prediction_markets", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@betting_bp.route("/markets/<int:market_id>", methods=["GET"])
@token_required
def get_market(market_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM prediction_markets WHERE market_id = ?", (market_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"markets {market_id} not found")
    log_activity("view", "prediction_markets", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@betting_bp.route("/markets", methods=["POST"])
@token_required
def create_market():
    data = request.get_json(silent=True) or {}
    for field in ["title", "description", "category", "creator_id"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO prediction_markets
               (title, description, category, creator_id, options_json, start_date, end_date, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["title"], data["description"], data["category"], data["creator_id"], data.get("options_json", ""), data.get("start_date", ""), data.get("end_date", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM prediction_markets WHERE market_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "prediction_markets", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- deposit ----

@betting_bp.route("/accounts/<int:account_id>/deposit", methods=["POST"])
@token_required
def deposit(account_id: int):
    """Deposit funds to a betting account."""
    data = request.get_json(silent=True) or {}
    for field in ["amount", "payment_method"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    amount = float(data["amount"])
    payment_method = data["payment_method"]
    processed_by = g.current_user.get("sub")

    if amount < 10.00 or amount > 1000.00:
        raise ValidationError("Deposit amount must be between 10.00 and 1000.00")

    with get_connection() as conn:
        account = conn.execute(
            "SELECT * FROM betting_accounts WHERE account_id = ?", (account_id,)
        ).fetchone()
    if not account:
        raise ValidationError(f"Account {account_id} not found")

    acct = _row_to_dict(account)
    balance_before = acct.get("balance", 0) or 0
    balance_after = balance_before + amount
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ref = f"BET-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    with transaction() as conn:
        conn.execute(
            """UPDATE betting_accounts
               SET balance = ?, total_deposited = COALESCE(total_deposited, 0) + ?, updated_at = ?
               WHERE account_id = ?""",
            (balance_after, amount, now, account_id),
        )
        conn.execute(
            """INSERT INTO transactions
               (source_type, student_id, transaction_type, amount, balance_before, balance_after,
                reference_number, description, payment_method, processed_by)
               VALUES ('betting', ?, 'deposit', ?, ?, ?, ?, ?, ?, ?)""",
            (acct.get("user_id"), amount, balance_before, balance_after, ref,
             f"Deposit via {payment_method}", payment_method, processed_by),
        )
        txn_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    log_activity("deposit", "betting_account", user=g.current_user.get("sub"))
    return jsonify({"transaction_id": txn_id, "balance": balance_after, "reference": ref})


# ---- withdraw ----

@betting_bp.route("/accounts/<int:account_id>/withdraw", methods=["POST"])
@token_required
def withdraw(account_id: int):
    """Withdraw funds from a betting account."""
    data = request.get_json(silent=True) or {}
    for field in ["amount", "payment_method"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    amount = float(data["amount"])
    payment_method = data["payment_method"]
    processed_by = g.current_user.get("sub")

    with get_connection() as conn:
        account = conn.execute(
            "SELECT * FROM betting_accounts WHERE account_id = ?", (account_id,)
        ).fetchone()
    if not account:
        raise ValidationError(f"Account {account_id} not found")

    acct = _row_to_dict(account)
    balance_before = acct.get("balance", 0) or 0
    if balance_before < amount:
        raise ValidationError("Insufficient balance")

    balance_after = balance_before - amount
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ref = f"BET-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    with transaction() as conn:
        conn.execute(
            """UPDATE betting_accounts
               SET balance = ?, total_withdrawn = COALESCE(total_withdrawn, 0) + ?, updated_at = ?
               WHERE account_id = ?""",
            (balance_after, amount, now, account_id),
        )
        conn.execute(
            """INSERT INTO transactions
               (source_type, student_id, transaction_type, amount, balance_before, balance_after,
                reference_number, description, payment_method, processed_by)
               VALUES ('betting', ?, 'withdrawal', ?, ?, ?, ?, ?, ?, ?)""",
            (acct.get("user_id"), amount, balance_before, balance_after, ref,
             f"Withdrawal to {payment_method}", payment_method, processed_by),
        )
        txn_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    log_activity("withdraw", "betting_account", user=g.current_user.get("sub"))
    return jsonify({"transaction_id": txn_id, "balance": balance_after, "reference": ref})


# ---- get account by user_id ----

@betting_bp.route("/accounts/by-user/<user_id>", methods=["GET"])
@token_required
def get_account_by_user(user_id: str):
    """Get a betting account by user_id."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM betting_accounts WHERE user_id = ?", (user_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Account for user {user_id} not found")
    log_activity("view", "betting_account", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- transaction history ----

@betting_bp.route("/accounts/<user_id>/transactions", methods=["GET"])
@token_required
def get_transaction_history(user_id: str):
    """Get transaction history for a user's betting account."""
    limit = int(request.args.get("limit", 50))

    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM transactions
               WHERE source_type = 'betting' AND student_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()

    log_activity("view", "betting_transactions", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- upcoming events ----

@betting_bp.route("/events/upcoming", methods=["GET"])
@token_required
def get_upcoming_events():
    """Get upcoming betting events."""
    sport_type = request.args.get("sport_type")

    query = """SELECT * FROM betting_events
               WHERE status = 'upcoming' AND event_date >= date('now')"""
    params = []

    if sport_type:
        query += " AND sport_type = ?"
        params.append(sport_type)

    query += " ORDER BY event_date, event_time"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    log_activity("view", "upcoming_events", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- settle event ----

@betting_bp.route("/events/<int:event_id>/settle", methods=["POST"])
@token_required
def settle_event(event_id: int):
    """Settle an event and resolve all pending bets."""
    data = request.get_json(silent=True) or {}
    if "result" not in data:
        raise ValidationError("Missing required field: result")

    result = data["result"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with transaction() as conn:
        # Update event status
        conn.execute(
            "UPDATE betting_events SET status = 'settled', result = ? WHERE event_id = ?",
            (result, event_id),
        )

        # Get all pending bets for this event
        bets = conn.execute(
            "SELECT bet_id, user_id, selection, potential_return FROM sports_bets WHERE event_id = ? AND status = 'pending'",
            (event_id,),
        ).fetchall()

        winners = []
        losers = []
        for bet in bets:
            b = _row_to_dict(bet)
            if b["selection"] == result:
                conn.execute(
                    "UPDATE sports_bets SET status = 'won', actual_return = ?, settled_at = ? WHERE bet_id = ?",
                    (b["potential_return"], now, b["bet_id"]),
                )
                conn.execute(
                    """UPDATE betting_accounts
                       SET balance = balance + ?, total_won = COALESCE(total_won, 0) + ?, updated_at = ?
                       WHERE user_id = ?""",
                    (b["potential_return"], b["potential_return"], now, b["user_id"]),
                )
                winners.append(b["bet_id"])
            else:
                conn.execute(
                    "UPDATE sports_bets SET status = 'lost', actual_return = 0, settled_at = ? WHERE bet_id = ?",
                    (now, b["bet_id"]),
                )
                losers.append(b["bet_id"])

    log_activity("settle", "betting_event", user=g.current_user.get("sub"))
    return jsonify({"event_id": event_id, "result": result, "winners": winners, "losers": losers})


# ---- place bet ----

@betting_bp.route("/bets/place", methods=["POST"])
@token_required
def place_bet():
    """Place a sports bet with balance deduction."""
    data = request.get_json(silent=True) or {}
    for field in ["user_id", "event_id", "selection", "stake"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    user_id = data["user_id"]
    event_id = int(data["event_id"])
    selection = data["selection"]
    stake = float(data["stake"])

    if stake < 1.00 or stake > 500.00:
        raise ValidationError("Stake must be between 1.00 and 500.00")

    with get_connection() as conn:
        event = conn.execute(
            "SELECT * FROM betting_events WHERE event_id = ? AND status = 'upcoming'", (event_id,)
        ).fetchone()
    if not event:
        raise ValidationError("Event not found or not open for betting")
    ev = _row_to_dict(event)

    # Determine odds
    if selection == "team_a":
        odds = ev.get("odds_a", 2.00) or 2.00
    elif selection == "team_b":
        odds = ev.get("odds_b", 2.00) or 2.00
    elif selection == "draw":
        odds = ev.get("odds_draw", 3.50) or 3.50
    else:
        raise ValidationError("Invalid selection. Must be team_a, team_b, or draw")

    potential_return = round(stake * float(odds), 2)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with transaction() as conn:
        # Check and deduct balance
        acct = conn.execute(
            "SELECT balance FROM betting_accounts WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not acct or (acct[0] or 0) < stake:
            raise ValidationError("Insufficient balance")

        conn.execute(
            """UPDATE betting_accounts
               SET balance = balance - ?, total_wagered = COALESCE(total_wagered, 0) + ?, updated_at = ?
               WHERE user_id = ?""",
            (stake, stake, now, user_id),
        )

        conn.execute(
            """INSERT INTO sports_bets
               (user_id, event_id, bet_type, selection, odds, stake, potential_return, status, placed_at)
               VALUES (?, ?, 'single', ?, ?, ?, ?, 'pending', ?)""",
            (user_id, event_id, selection, odds, stake, potential_return, now),
        )
        bet_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    log_activity("place_bet", "sports_bet", user=g.current_user.get("sub"))
    return jsonify({"bet_id": bet_id, "odds": odds, "stake": stake, "potential_return": potential_return}), 201


# ---- cash out ----

@betting_bp.route("/bets/<int:bet_id>/cash-out", methods=["POST"])
@token_required
def cash_out_bet(bet_id: int):
    """Cash out a pending bet early at reduced value."""
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    if not user_id:
        raise ValidationError("Missing required field: user_id")

    with get_connection() as conn:
        bet = conn.execute(
            "SELECT * FROM sports_bets WHERE bet_id = ? AND user_id = ? AND status = 'pending'",
            (bet_id, user_id),
        ).fetchone()
    if not bet:
        raise ValidationError("Bet not found or not eligible for cash out")

    b = _row_to_dict(bet)
    stake = b.get("stake", 0) or 0
    potential_return = b.get("potential_return", 0) or 0
    cash_out_value = round(stake + (potential_return - stake) * 0.5, 2)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with transaction() as conn:
        conn.execute(
            "UPDATE sports_bets SET status = 'cashed_out', actual_return = ?, settled_at = ? WHERE bet_id = ?",
            (cash_out_value, now, bet_id),
        )
        conn.execute(
            """UPDATE betting_accounts
               SET balance = balance + ?, total_won = COALESCE(total_won, 0) + ?, updated_at = ?
               WHERE user_id = ?""",
            (cash_out_value, cash_out_value, now, user_id),
        )

    log_activity("cash_out", "sports_bet", user=g.current_user.get("sub"))
    return jsonify({"bet_id": bet_id, "cash_out_value": cash_out_value})


# ---- get user bets ----

@betting_bp.route("/bets/user/<user_id>", methods=["GET"])
@token_required
def get_user_bets(user_id: str):
    """Get all bets for a user with event details."""
    status = request.args.get("status")

    query = """SELECT sb.*, be.event_name, be.team_a, be.team_b, be.event_date
               FROM sports_bets sb
               JOIN betting_events be ON sb.event_id = be.event_id
               WHERE sb.user_id = ?"""
    params = [user_id]

    if status:
        query += " AND sb.status = ?"
        params.append(status)

    query += " ORDER BY sb.placed_at DESC"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    log_activity("view", "user_bets", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- open prediction markets ----

@betting_bp.route("/markets/open", methods=["GET"])
@token_required
def get_open_prediction_markets():
    """Get open prediction markets optionally filtered by category."""
    category = request.args.get("category")

    query = "SELECT * FROM prediction_markets WHERE status = 'open'"
    params = []

    if category:
        query += " AND category = ?"
        params.append(category)

    query += " ORDER BY resolution_date"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    log_activity("view", "open_prediction_markets", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- statistics ----

@betting_bp.route("/statistics", methods=["GET"])
@token_required
def get_statistics():
    """Get overall betting statistics."""
    with get_connection() as conn:
        account_stats = conn.execute(
            "SELECT COUNT(*) as total_accounts, SUM(balance) as total_balance, SUM(total_wagered) as total_wagered, SUM(total_won) as total_won FROM betting_accounts"
        ).fetchone()

        sports_stats = conn.execute(
            """SELECT COUNT(*) as total_bets, SUM(stake) as total_staked, SUM(actual_return) as total_returned
               FROM sports_bets WHERE status IN ('won', 'lost', 'cashed_out')"""
        ).fetchone()

        casino_stats = conn.execute(
            "SELECT COUNT(*) as total_games, SUM(bet_amount) as total_wagered, SUM(win_amount) as total_won FROM casino_games"
        ).fetchone()

    acct = _row_to_dict(account_stats)
    sports = _row_to_dict(sports_stats)
    casino = _row_to_dict(casino_stats)

    total_wagered = (sports.get("total_staked") or 0) + (casino.get("total_wagered") or 0)
    total_paid_out = (sports.get("total_returned") or 0) + (casino.get("total_won") or 0)

    log_activity("view", "betting_statistics", user=g.current_user.get("sub"))
    return jsonify({
        "accounts": acct,
        "sports_betting": sports,
        "casino": casino,
        "total_wagered": total_wagered,
        "total_paid_out": total_paid_out,
        "house_profit": total_wagered - total_paid_out,
    })
