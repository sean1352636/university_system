"""Wellness routes: check-ins, mood, sleep, exercise, goals, and crisis resources."""

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

wellness_bp = Blueprint("wellness", __name__, url_prefix="/api/wellness")

_STAFF_ROLES = {"admin", "staff", "superadmin", "counselor", "wellness_officer"}


def _is_staff() -> bool:
    return (g.current_user or {}).get("role") in _STAFF_ROLES


def _caller_student_id() -> str:
    return str((g.current_user or {}).get("sub") or "")


def _effective_student_filter(requested: str | None) -> str | None:
    """Enforce that non-staff callers may only query their own ``student_id``.

    Returns the ``student_id`` to filter by, or raises ``ValidationError``
    if a non-staff caller asks for someone else's records.
    """
    if _is_staff():
        return requested
    own = _caller_student_id()
    if requested and str(requested) != own:
        raise ValidationError("Forbidden: cannot query another student's records")
    return own


def _authorize_record(row, owner_field: str = "student_id"):
    """Return a (response, status) if the caller may not see ``row``."""
    if _is_staff():
        return None
    try:
        owner = row[owner_field]
    except (IndexError, KeyError):
        owner = None
    if str(owner) == _caller_student_id() and owner is not None:
        return None
    return jsonify({"error": "Forbidden", "status": 403}), 403


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- checkins ----

@wellness_bp.route("/checkins", methods=["GET"])
@token_required
def list_checkins():
    student_id = _effective_student_filter(request.args.get("student_id"))

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
            "SELECT * FROM wellness_checkins" + where + " ORDER BY checkin_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM wellness_checkins" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "wellness_checkins", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@wellness_bp.route("/checkins/<int:checkin_id>", methods=["GET"])
@token_required
def get_checkin(checkin_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM wellness_checkins WHERE checkin_id = ?", (checkin_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"checkins {checkin_id} not found")
    denied = _authorize_record(row)
    if denied is not None:
        return denied
    log_activity("view", "wellness_checkins", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@wellness_bp.route("/checkins", methods=["POST"])
@token_required
def create_checkin():
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "overall_mood", "stress_level"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")
    if not _is_staff() and str(data["student_id"]) != _caller_student_id():
        return jsonify({"error": "Forbidden", "status": 403}), 403

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO wellness_checkins
               (student_id, overall_mood, stress_level, sleep_quality, energy_level, anxiety_level, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["student_id"], data["overall_mood"], data["stress_level"], data.get("sleep_quality", ""), data.get("energy_level", ""), data.get("anxiety_level", ""), data.get("notes", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM wellness_checkins WHERE checkin_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "wellness_checkins", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- mood ----

@wellness_bp.route("/mood", methods=["GET"])
@token_required
def list_mood():
    student_id = _effective_student_filter(request.args.get("student_id"))
    mood_type = request.args.get("mood_type")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if mood_type:
            conditions.append("mood_type = ?")
            params.append(mood_type)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM mood_tracking" + where + " ORDER BY mood_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM mood_tracking" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "mood_tracking", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@wellness_bp.route("/mood/<int:mood_id>", methods=["GET"])
@token_required
def get_mood(mood_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM mood_tracking WHERE mood_id = ?", (mood_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"mood {mood_id} not found")
    denied = _authorize_record(row)
    if denied is not None:
        return denied
    log_activity("view", "mood_tracking", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@wellness_bp.route("/mood", methods=["POST"])
@token_required
def create_mood():
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "mood_type", "intensity"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")
    if not _is_staff() and str(data["student_id"]) != _caller_student_id():
        return jsonify({"error": "Forbidden", "status": 403}), 403

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO mood_tracking
               (student_id, mood_type, intensity, mood_date, triggers, activities, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["student_id"], data["mood_type"], data["intensity"], data.get("mood_date", ""), data.get("triggers", ""), data.get("activities", ""), data.get("notes", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM mood_tracking WHERE mood_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "mood_tracking", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- sleep ----

@wellness_bp.route("/sleep", methods=["GET"])
@token_required
def list_sleep():
    student_id = _effective_student_filter(request.args.get("student_id"))

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
            "SELECT * FROM sleep_tracking" + where + " ORDER BY sleep_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM sleep_tracking" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "sleep_tracking", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@wellness_bp.route("/sleep/<int:sleep_id>", methods=["GET"])
@token_required
def get_sleep(sleep_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sleep_tracking WHERE sleep_id = ?", (sleep_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"sleep {sleep_id} not found")
    denied = _authorize_record(row)
    if denied is not None:
        return denied
    log_activity("view", "sleep_tracking", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@wellness_bp.route("/sleep", methods=["POST"])
@token_required
def create_sleep():
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "sleep_date", "hours_slept"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")
    if not _is_staff() and str(data["student_id"]) != _caller_student_id():
        return jsonify({"error": "Forbidden", "status": 403}), 403

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO sleep_tracking
               (student_id, sleep_date, hours_slept, bedtime, wake_time, sleep_quality, interruptions, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["student_id"], data["sleep_date"], data["hours_slept"], data.get("bedtime", ""), data.get("wake_time", ""), data.get("sleep_quality", ""), data.get("interruptions", ""), data.get("notes", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sleep_tracking WHERE sleep_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "sleep_tracking", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- goals ----

@wellness_bp.route("/goals", methods=["GET"])
@token_required
def list_goals():
    search = request.args.get("search")
    student_id = _effective_student_filter(request.args.get("student_id"))
    goal_type = request.args.get("goal_type")
    status = request.args.get("status")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            if _is_staff():
                rows = conn.execute(
                    "SELECT * FROM wellness_goals WHERE goal_description LIKE ?",
                    (pattern,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM wellness_goals WHERE goal_description LIKE ? AND student_id = ?",
                    (pattern, _caller_student_id()),
                ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if goal_type:
            conditions.append("goal_type = ?")
            params.append(goal_type)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM wellness_goals" + where + " ORDER BY goal_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM wellness_goals" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "wellness_goals", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@wellness_bp.route("/goals/<int:goal_id>", methods=["GET"])
@token_required
def get_goal(goal_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM wellness_goals WHERE goal_id = ?", (goal_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"goals {goal_id} not found")
    denied = _authorize_record(row)
    if denied is not None:
        return denied
    log_activity("view", "wellness_goals", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@wellness_bp.route("/goals", methods=["POST"])
@token_required
def create_goal():
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "goal_type", "goal_description", "target_value"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")
    if not _is_staff() and str(data["student_id"]) != _caller_student_id():
        return jsonify({"error": "Forbidden", "status": 403}), 403

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO wellness_goals
               (student_id, goal_type, goal_description, target_value, current_value, start_date, end_date, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["student_id"], data["goal_type"], data["goal_description"], data["target_value"], data.get("current_value", 0), data.get("start_date", ""), data.get("end_date", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM wellness_goals WHERE goal_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "wellness_goals", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- crisis-resources ----

@wellness_bp.route("/crisis-resources", methods=["GET"])
@token_required
def list_crisis_resources():
    search = request.args.get("search")
    resource_type = request.args.get("resource_type")
    is_active = request.args.get("is_active")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM crisis_resources WHERE resource_name LIKE ? OR description LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if resource_type:
            conditions.append("resource_type = ?")
            params.append(resource_type)
        if is_active:
            conditions.append("is_active = ?")
            params.append(is_active)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM crisis_resources" + where + " ORDER BY resource_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM crisis_resources" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "crisis_resources", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@wellness_bp.route("/crisis-resources/<int:resource_id>", methods=["GET"])
@token_required
def get_crisis_resource(resource_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM crisis_resources WHERE resource_id = ?", (resource_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"crisis-resources {resource_id} not found")
    log_activity("view", "crisis_resources", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@wellness_bp.route("/crisis-resources", methods=["POST"])
@token_required
def create_crisis_resource():
    data = request.get_json(silent=True) or {}
    for field in ["resource_name", "resource_type", "contact_info"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO crisis_resources
               (resource_name, resource_type, contact_info, description, availability, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data["resource_name"], data["resource_type"], data["contact_info"], data.get("description", ""), data.get("availability", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM crisis_resources WHERE resource_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "crisis_resources", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
