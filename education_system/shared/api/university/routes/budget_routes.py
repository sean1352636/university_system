"""Budget routes: student budgets, categories, expenses, income, and savings goals."""

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

budget_bp = Blueprint("budget", __name__, url_prefix="/api/budget")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- budgets ----

@budget_bp.route("/budgets", methods=["GET"])
@token_required
def list_budgets():
    student_id = request.args.get("student_id")
    semester = request.args.get("semester")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if semester:
            conditions.append("semester = ?")
            params.append(semester)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM student_budgets" + where + " ORDER BY budget_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM student_budgets" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "student_budgets", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@budget_bp.route("/budgets/<int:budget_id>", methods=["GET"])
@token_required
def get_budget(budget_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_budgets WHERE budget_id = ?", (budget_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"budgets {budget_id} not found")
    log_activity("view", "student_budgets", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@budget_bp.route("/budgets", methods=["POST"])
@token_required
def create_budget():
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "semester", "total_budget"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO student_budgets
               (student_id, semester, total_budget, created_at)
               VALUES (?, ?, ?, ?)""",
            (data["student_id"], data["semester"], data["total_budget"], now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_budgets WHERE budget_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "student_budgets", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- expenses ----

@budget_bp.route("/expenses", methods=["GET"])
@token_required
def list_expenses():
    search = request.args.get("search")
    budget_id = request.args.get("budget_id")
    category_id = request.args.get("category_id")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM budget_expenses WHERE expense_name LIKE ?",
                (pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if budget_id:
            conditions.append("budget_id = ?")
            params.append(budget_id)
        if category_id:
            conditions.append("category_id = ?")
            params.append(category_id)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM budget_expenses" + where + " ORDER BY expense_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM budget_expenses" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "budget_expenses", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@budget_bp.route("/expenses/<int:expense_id>", methods=["GET"])
@token_required
def get_expense(expense_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM budget_expenses WHERE expense_id = ?", (expense_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"expenses {expense_id} not found")
    log_activity("view", "budget_expenses", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@budget_bp.route("/expenses", methods=["POST"])
@token_required
def create_expense():
    data = request.get_json(silent=True) or {}
    for field in ["budget_id", "expense_name", "amount"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO budget_expenses
               (budget_id, expense_name, amount, category_id, date, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (data["budget_id"], data["expense_name"], data["amount"], data.get("category_id", ""), data.get("date", ""), data.get("notes", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM budget_expenses WHERE expense_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "budget_expenses", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- savings-goals ----

@budget_bp.route("/savings-goals", methods=["GET"])
@token_required
def list_savings_goals():
    search = request.args.get("search")
    student_id = request.args.get("student_id")
    status = request.args.get("status")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM savings_goals WHERE goal_name LIKE ?",
                (pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM savings_goals" + where + " ORDER BY goal_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM savings_goals" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "savings_goals", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@budget_bp.route("/savings-goals/<int:goal_id>", methods=["GET"])
@token_required
def get_savings_goal(goal_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM savings_goals WHERE goal_id = ?", (goal_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"savings-goals {goal_id} not found")
    log_activity("view", "savings_goals", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@budget_bp.route("/savings-goals", methods=["POST"])
@token_required
def create_savings_goal():
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "goal_name", "target_amount"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO savings_goals
               (student_id, goal_name, target_amount, current_amount, deadline, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (data["student_id"], data["goal_name"], data["target_amount"], data.get("current_amount", 0), data.get("deadline", ""), data.get("status", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM savings_goals WHERE goal_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "savings_goals", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- update / delete expense ----

@budget_bp.route("/expenses/<int:expense_id>", methods=["PUT"])
@token_required
def update_expense(expense_id: int):
    data = request.get_json(silent=True) or {}
    # Iterate over a literal column tuple so user-supplied keys never flow
    # into the SQL identifier positions (py/sql-injection).
    set_parts: list[str] = []
    values: list = []
    for col in ("amount", "expense_name", "category_id", "date", "notes"):
        if col in data:
            set_parts.append(f"{col} = ?")
            values.append(data[col])
    if not set_parts:
        raise ValidationError("No valid fields to update")

    set_clause = ", ".join(set_parts)
    values.append(expense_id)

    with transaction() as conn:
        conn.execute(
            f"UPDATE budget_expenses SET {set_clause} WHERE expense_id = ?",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM budget_expenses WHERE expense_id = ?", (expense_id,)
        ).fetchone()

    if not row:
        raise ValidationError(f"expense {expense_id} not found")

    log_activity("update", "budget_expenses", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@budget_bp.route("/expenses/<int:expense_id>", methods=["DELETE"])
@token_required
def delete_expense(expense_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM budget_expenses WHERE expense_id = ?", (expense_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"expense {expense_id} not found")

    with transaction() as conn:
        conn.execute("DELETE FROM budget_expenses WHERE expense_id = ?", (expense_id,))

    log_activity("delete", "budget_expenses", user=g.current_user.get("sub"))
    return jsonify({"message": f"Expense {expense_id} deleted"})


# ---- spending by category ----

@budget_bp.route("/spending-by-category", methods=["GET"])
@token_required
def get_spending_by_category():
    student_id = request.args.get("student_id")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    if not student_id or not start_date or not end_date:
        raise ValidationError("student_id, start_date, and end_date are required")

    with get_connection() as conn:
        rows = conn.execute(
            """SELECT
                   COALESCE(c.category_name, e.expense_name, 'Uncategorized') AS category_name,
                   COUNT(*) AS transaction_count,
                   SUM(e.amount) AS total_amount,
                   AVG(e.amount) AS average_amount,
                   MIN(e.amount) AS min_amount,
                   MAX(e.amount) AS max_amount
               FROM budget_expenses e
               LEFT JOIN student_budget_categories c ON e.category_id = c.category_id
               WHERE e.budget_id IN (SELECT budget_id FROM student_budgets WHERE student_id = ?)
                 AND e.date BETWEEN ? AND ?
               GROUP BY COALESCE(c.category_id, e.expense_name)
               ORDER BY total_amount DESC""",
            (student_id, start_date, end_date),
        ).fetchall()

    log_activity("view", "spending_by_category", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- spending trends ----

@budget_bp.route("/spending-trends", methods=["GET"])
@token_required
def get_spending_trends():
    student_id = request.args.get("student_id")
    days = request.args.get("days", 30, type=int)

    if not student_id:
        raise ValidationError("student_id is required")

    from datetime import timedelta

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    with get_connection() as conn:
        daily_rows = conn.execute(
            """SELECT date AS expense_date, SUM(amount) AS daily_total
               FROM budget_expenses
               WHERE budget_id IN (SELECT budget_id FROM student_budgets WHERE student_id = ?)
                 AND date BETWEEN ? AND ?
               GROUP BY date
               ORDER BY date""",
            (student_id, start_date, end_date),
        ).fetchall()

        stats_row = conn.execute(
            """SELECT COUNT(*) AS total_transactions,
                      COALESCE(SUM(amount), 0) AS total_spent,
                      AVG(amount) AS average_transaction,
                      MIN(amount) AS min_transaction,
                      MAX(amount) AS max_transaction
               FROM budget_expenses
               WHERE budget_id IN (SELECT budget_id FROM student_budgets WHERE student_id = ?)
                 AND date BETWEEN ? AND ?""",
            (student_id, start_date, end_date),
        ).fetchone()

    stats = _row_to_dict(stats_row) if stats_row else {}
    stats["average_daily_spending"] = round(
        (stats.get("total_spent") or 0) / days, 2
    ) if days > 0 else 0

    log_activity("view", "spending_trends", user=g.current_user.get("sub"))
    return jsonify({
        "daily_spending": [_row_to_dict(r) for r in daily_rows],
        "statistics": stats,
        "period_days": days,
        "start_date": start_date,
        "end_date": end_date,
    })


# ---- update goal progress ----

@budget_bp.route("/savings-goals/<int:goal_id>/progress", methods=["PUT"])
@token_required
def update_goal_progress(goal_id: int):
    data = request.get_json(silent=True) or {}
    amount = data.get("amount")
    if amount is None:
        raise ValidationError("amount is required")

    with get_connection() as conn:
        row = conn.execute(
            "SELECT current_amount, target_amount FROM savings_goals WHERE goal_id = ?",
            (goal_id,),
        ).fetchone()

    if not row:
        raise ValidationError(f"savings goal {goal_id} not found")

    new_amount = (row["current_amount"] or 0) + float(amount)
    status = "completed" if new_amount >= row["target_amount"] else "active"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            "UPDATE savings_goals SET current_amount = ?, status = ?, created_at = created_at WHERE goal_id = ?",
            (new_amount, status, goal_id),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM savings_goals WHERE goal_id = ?", (goal_id,)
        ).fetchone()

    log_activity("update", "savings_goal_progress", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- meal plan tracking ----

@budget_bp.route("/meal-plans", methods=["GET"])
@token_required
def list_meal_plans():
    student_id = request.args.get("student_id")
    active_only = request.args.get("active_only", "true").lower() == "true"

    conditions = []
    params: list = []
    if student_id:
        conditions.append("student_id = ?")
        params.append(student_id)
    if active_only:
        conditions.append("is_active = 1")

    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM meal_plan_tracking" + where + " ORDER BY start_date DESC",
            params,
        ).fetchall()

    log_activity("view", "meal_plan_tracking", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@budget_bp.route("/meal-plans", methods=["POST"])
@token_required
def create_meal_plan():
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "plan_name", "plan_type", "academic_term", "start_date", "end_date"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO meal_plan_tracking
               (student_id, academic_term, plan_name, plan_type, total_meals, total_dollars, start_date, end_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["student_id"], data["academic_term"], data["plan_name"],
             data["plan_type"], data.get("total_meals", 0),
             data.get("total_dollars", 0.0), data["start_date"], data["end_date"]),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM meal_plan_tracking WHERE tracking_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "meal_plan_tracking", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@budget_bp.route("/meal-plans/<int:tracking_id>/status", methods=["GET"])
@token_required
def get_meal_plan_status(tracking_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM meal_plan_tracking WHERE tracking_id = ?", (tracking_id,)
        ).fetchone()

    if not row:
        raise ValidationError(f"meal plan {tracking_id} not found")

    plan = _row_to_dict(row)
    plan["remaining_meals"] = (plan.get("total_meals") or 0) - (plan.get("used_meals") or 0)
    plan["remaining_dollars"] = (plan.get("total_dollars") or 0) - (plan.get("used_dollars") or 0)
    plan["meals_used_pct"] = round(
        ((plan.get("used_meals") or 0) / plan["total_meals"] * 100), 2
    ) if plan.get("total_meals") else 0
    plan["dollars_used_pct"] = round(
        ((plan.get("used_dollars") or 0) / plan["total_dollars"] * 100), 2
    ) if plan.get("total_dollars") else 0

    log_activity("view", "meal_plan_status", user=g.current_user.get("sub"))
    return jsonify(plan)


@budget_bp.route("/meal-plans/<int:tracking_id>/transactions", methods=["POST"])
@token_required
def log_meal_transaction(tracking_id: int):
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "transaction_date", "location", "meal_type"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    meals_used = data.get("meals_used", 0)
    dollars_used = data.get("dollars_used", 0.0)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO transactions
               (source_type, reference_id, student_id, created_at, transaction_time, location, transaction_type, quantity_change, amount, description)
               VALUES ('meal_plan', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (tracking_id, data["student_id"], data["transaction_date"],
             data.get("transaction_time", ""), data["location"], data["meal_type"],
             meals_used, dollars_used, data.get("description", "")),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.execute(
            """UPDATE meal_plan_tracking
               SET used_meals = used_meals + ?, used_dollars = used_dollars + ?, updated_at = CURRENT_TIMESTAMP
               WHERE tracking_id = ?""",
            (meals_used, dollars_used, tracking_id),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM transactions WHERE id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "meal_transaction", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row) if row else {"id": new_id}), 201
