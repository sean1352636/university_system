"""Study matching routes: profiles, groups, virtual rooms, Q&A, and match suggestions."""

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

study_matching_bp = Blueprint("study_matching", __name__, url_prefix="/api/study-matching")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- profiles ----

@study_matching_bp.route("/profiles", methods=["GET"])
@token_required
def list_profiles():
    student_id = request.args.get("student_id")

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
            "SELECT * FROM study_profiles" + where + " ORDER BY profile_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM study_profiles" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "study_profiles", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@study_matching_bp.route("/profiles/<int:profile_id>", methods=["GET"])
@token_required
def get_profile(profile_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM study_profiles WHERE profile_id = ?", (profile_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"profiles {profile_id} not found")
    log_activity("view", "study_profiles", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@study_matching_bp.route("/profiles", methods=["POST"])
@token_required
def create_profile():
    data = request.get_json(silent=True) or {}
    for field in ["student_id"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO study_profiles
               (student_id, study_style, preferred_time, group_size_preference, communication_style, noise_preference, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (data["student_id"], data.get("study_style", ""), data.get("preferred_time", ""), data.get("group_size_preference", ""), data.get("communication_style", ""), data.get("noise_preference", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM study_profiles WHERE profile_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "study_profiles", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- groups ----

@study_matching_bp.route("/groups", methods=["GET"])
@token_required
def list_groups():
    search = request.args.get("search")
    course_id = request.args.get("course_id")
    status = request.args.get("status")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM study_groups WHERE group_name LIKE ?",
                (pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if course_id:
            conditions.append("course_id = ?")
            params.append(course_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM study_groups" + where + " ORDER BY group_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM study_groups" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "study_groups", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@study_matching_bp.route("/groups/<int:group_id>", methods=["GET"])
@token_required
def get_group(group_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM study_groups WHERE group_id = ?", (group_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"groups {group_id} not found")
    log_activity("view", "study_groups", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@study_matching_bp.route("/groups", methods=["POST"])
@token_required
def create_group():
    data = request.get_json(silent=True) or {}
    for field in ["course_id", "group_name", "creator_id"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO study_groups
               (course_id, group_name, creator_id, max_members, meeting_schedule, location, is_virtual, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["course_id"], data["group_name"], data["creator_id"], data.get("max_members", ""), data.get("meeting_schedule", ""), data.get("location", ""), data.get("is_virtual", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM study_groups WHERE group_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "study_groups", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- virtual-rooms ----

@study_matching_bp.route("/virtual-rooms", methods=["GET"])
@token_required
def list_virtual_rooms():
    search = request.args.get("search")
    group_id = request.args.get("group_id")
    host_id = request.args.get("host_id")
    is_active = request.args.get("is_active")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM virtual_study_rooms WHERE room_name LIKE ?",
                (pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if group_id:
            conditions.append("group_id = ?")
            params.append(group_id)
        if host_id:
            conditions.append("host_id = ?")
            params.append(host_id)
        if is_active:
            conditions.append("is_active = ?")
            params.append(is_active)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM virtual_study_rooms" + where + " ORDER BY room_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM virtual_study_rooms" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "virtual_study_rooms", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@study_matching_bp.route("/virtual-rooms/<int:room_id>", methods=["GET"])
@token_required
def get_virtual_room(room_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM virtual_study_rooms WHERE room_id = ?", (room_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"virtual-rooms {room_id} not found")
    log_activity("view", "virtual_study_rooms", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@study_matching_bp.route("/virtual-rooms", methods=["POST"])
@token_required
def create_virtual_room():
    data = request.get_json(silent=True) or {}
    for field in ["group_id", "room_name", "host_id"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO virtual_study_rooms
               (group_id, room_name, host_id, room_code, course_id, max_participants, pomodoro_enabled, work_duration, break_duration, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["group_id"], data["room_name"], data["host_id"], data.get("room_code", ""), data.get("course_id", ""), data.get("max_participants", ""), data.get("pomodoro_enabled", ""), data.get("work_duration", ""), data.get("break_duration", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM virtual_study_rooms WHERE room_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "virtual_study_rooms", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- questions ----

@study_matching_bp.route("/questions", methods=["GET"])
@token_required
def list_questions():
    search = request.args.get("search")
    course_id = request.args.get("course_id")
    student_id = request.args.get("student_id")
    is_answered = request.args.get("is_answered")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM qa_board WHERE question_title LIKE ? OR question_text LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if course_id:
            conditions.append("course_id = ?")
            params.append(course_id)
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if is_answered:
            conditions.append("is_answered = ?")
            params.append(is_answered)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM qa_board" + where + " ORDER BY question_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM qa_board" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "qa_board", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@study_matching_bp.route("/questions/<int:question_id>", methods=["GET"])
@token_required
def get_question(question_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM qa_board WHERE question_id = ?", (question_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"questions {question_id} not found")
    log_activity("view", "qa_board", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@study_matching_bp.route("/questions", methods=["POST"])
@token_required
def create_question():
    data = request.get_json(silent=True) or {}
    for field in ["course_id", "student_id", "question_title", "question_text"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO qa_board
               (course_id, student_id, question_title, question_text, category, difficulty_level, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (data["course_id"], data["student_id"], data["question_title"], data["question_text"], data.get("category", ""), data.get("difficulty_level", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM qa_board WHERE question_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "qa_board", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
