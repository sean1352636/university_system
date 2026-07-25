"""External examiner routes: examiners, visits, findings, and action items."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.platform.delivery.api.university.auth import token_required
from education_system.platform.delivery.api.university.pagination import get_pagination_params, paginated_response
from education_system.systems.university.infrastructure.exceptions import ValidationError
from education_system.systems.university.infrastructure.sql_safety import escape_like
from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity

logger = logging.getLogger(__name__)

external_examiner_bp = Blueprint("external_examiner", __name__, url_prefix="/api/external-examiners")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- examiners ----

@external_examiner_bp.route("/examiners", methods=["GET"])
@token_required
def list_examiners():
    status = request.args.get("status")
    search = request.args.get("search")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM external_examiners WHERE name LIKE ? OR institution LIKE ? OR specialisation LIKE ?",
                (pattern, pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM external_examiners" + where + " ORDER BY id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM external_examiners" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "external_examiners", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@external_examiner_bp.route("/examiners/<int:examiner_id>", methods=["GET"])
@token_required
def get_examiner(examiner_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM external_examiners WHERE id = ?", (examiner_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"External examiner {examiner_id} not found")
    log_activity("view", "external_examiner", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@external_examiner_bp.route("/examiners", methods=["POST"])
@token_required
def create_examiner():
    data = request.get_json(silent=True) or {}
    if "name" not in data:
        raise ValidationError("Missing required field: name")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO external_examiners
               (name, email, institution, specialisation, appointment_start, appointment_end)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data["name"], data.get("email", ""), data.get("institution", ""),
             data.get("specialisation", ""), data.get("appointment_start", ""),
             data.get("appointment_end", "")),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM external_examiners WHERE id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "external_examiner", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@external_examiner_bp.route("/examiners/<int:examiner_id>", methods=["PUT"])
@token_required
def update_examiner(examiner_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM external_examiners WHERE id = ?", (examiner_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"External examiner {examiner_id} not found")

    data = request.get_json(silent=True) or {}
    allowed = ["name", "email", "institution", "specialisation",
               "appointment_start", "appointment_end", "status"]
    sets = []
    params: list = []
    for key in allowed:
        if key in data:
            sets.append(f"{key} = ?")
            params.append(data[key])
    if not sets:
        raise ValidationError("No valid fields to update")
    params.append(examiner_id)

    with transaction() as conn:
        conn.execute(
            f"UPDATE external_examiners SET {', '.join(sets)} WHERE id = ?", params
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM external_examiners WHERE id = ?", (examiner_id,)
        ).fetchone()

    log_activity("update", "external_examiner", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@external_examiner_bp.route("/examiners/<int:examiner_id>/history", methods=["GET"])
@token_required
def get_examiner_history(examiner_id: int):
    with get_connection() as conn:
        examiner = conn.execute(
            "SELECT * FROM external_examiners WHERE id = ?", (examiner_id,)
        ).fetchone()
        if not examiner:
            raise ValidationError(f"External examiner {examiner_id} not found")
        visits = conn.execute(
            "SELECT * FROM examiner_visits WHERE examiner_id = ? ORDER BY visit_date DESC",
            (examiner_id,),
        ).fetchall()

    log_activity("view", "examiner_history", user=g.current_user.get("sub"))
    return jsonify({
        "examiner": _row_to_dict(examiner),
        "visits": [_row_to_dict(v) for v in visits],
        "total_visits": len(visits),
    })


# ---- visits ----

@external_examiner_bp.route("/visits", methods=["GET"])
@token_required
def list_visits():
    examiner_id = request.args.get("examiner_id")
    department = request.args.get("department")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if examiner_id:
            conditions.append("examiner_id = ?")
            params.append(examiner_id)
        if department:
            conditions.append("department = ?")
            params.append(department)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM examiner_visits" + where + " ORDER BY visit_date DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM examiner_visits" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "examiner_visits", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@external_examiner_bp.route("/visits/<int:visit_id>", methods=["GET"])
@token_required
def get_visit(visit_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM examiner_visits WHERE id = ?", (visit_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Examiner visit {visit_id} not found")
    log_activity("view", "examiner_visit", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@external_examiner_bp.route("/visits", methods=["POST"])
@token_required
def schedule_visit():
    data = request.get_json(silent=True) or {}
    for field in ["examiner_id", "visit_date"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO examiner_visits
               (examiner_id, visit_date, department, purpose, created_by)
               VALUES (?, ?, ?, ?, ?)""",
            (data["examiner_id"], data["visit_date"], data.get("department", ""),
             data.get("purpose", ""), data.get("created_by", g.current_user.get("sub", ""))),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM examiner_visits WHERE id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "examiner_visit", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@external_examiner_bp.route("/visits/<int:visit_id>/findings", methods=["PUT"])
@token_required
def record_findings(visit_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM examiner_visits WHERE id = ?", (visit_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Examiner visit {visit_id} not found")

    data = request.get_json(silent=True) or {}
    with transaction() as conn:
        conn.execute(
            "UPDATE examiner_visits SET findings = ?, recommendations = ?, overall_rating = ? WHERE id = ?",
            (data.get("findings", ""), data.get("recommendations", ""),
             data.get("overall_rating", ""), visit_id),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM examiner_visits WHERE id = ?", (visit_id,)
        ).fetchone()

    log_activity("update", "examiner_visit_findings", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- action items ----

@external_examiner_bp.route("/actions", methods=["GET"])
@token_required
def list_actions():
    visit_id = request.args.get("visit_id")
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if visit_id:
            conditions.append("visit_id = ?")
            params.append(visit_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM examiner_actions" + where + " ORDER BY deadline LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM examiner_actions" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "examiner_actions", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@external_examiner_bp.route("/actions/<int:action_id>", methods=["GET"])
@token_required
def get_action(action_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM examiner_actions WHERE id = ?", (action_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Examiner action {action_id} not found")
    log_activity("view", "examiner_action", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@external_examiner_bp.route("/actions", methods=["POST"])
@token_required
def create_action():
    data = request.get_json(silent=True) or {}
    if "action_description" not in data:
        raise ValidationError("Missing required field: action_description")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO examiner_actions
               (visit_id, action_description, responsible_person, deadline)
               VALUES (?, ?, ?, ?)""",
            (data.get("visit_id"), data["action_description"],
             data.get("responsible_person", ""), data.get("deadline", "")),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM examiner_actions WHERE id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "examiner_action", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@external_examiner_bp.route("/actions/<int:action_id>/status", methods=["PUT"])
@token_required
def update_action_status(action_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM examiner_actions WHERE id = ?", (action_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Examiner action {action_id} not found")

    data = request.get_json(silent=True) or {}
    if "status" not in data:
        raise ValidationError("Missing required field: status")

    completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if data["status"] == "completed" else None
    with transaction() as conn:
        conn.execute(
            "UPDATE examiner_actions SET status = ?, completed_at = ? WHERE id = ?",
            (data["status"], completed_at, action_id),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM examiner_actions WHERE id = ?", (action_id,)
        ).fetchone()

    log_activity("update", "examiner_action_status", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@external_examiner_bp.route("/actions/overdue", methods=["GET"])
@token_required
def get_overdue_actions():
    today = datetime.now().strftime("%Y-%m-%d")
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM examiner_actions WHERE status != 'completed' AND deadline < ? ORDER BY deadline",
            (today,),
        ).fetchall()

    log_activity("view", "examiner_overdue_actions", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- department summary ----

@external_examiner_bp.route("/department-summary", methods=["GET"])
@token_required
def get_department_summary():
    department = request.args.get("department")

    with get_connection() as conn:
        if department:
            rows = conn.execute(
                "SELECT department, COUNT(*) as visit_count, MAX(visit_date) as last_visit "
                "FROM examiner_visits WHERE department = ? GROUP BY department",
                (department,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT department, COUNT(*) as visit_count, MAX(visit_date) as last_visit "
                "FROM examiner_visits GROUP BY department ORDER BY department"
            ).fetchall()

    log_activity("view", "examiner_department_summary", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})
