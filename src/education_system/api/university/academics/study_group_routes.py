"""Study group routes: groups and memberships."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.platform.delivery.api.university.auth import token_required
from education_system.platform.delivery.api.university.pagination import get_pagination_params, paginated_response
from education_system.platform.delivery.api.university.validators import validate_study_group_create
from education_system.systems.university.infrastructure.exceptions import ValidationError
from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity

logger = logging.getLogger(__name__)

study_group_bp = Blueprint("study_groups", __name__, url_prefix="/api/study-groups")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


@study_group_bp.route("", methods=["GET"])
@token_required
def list_groups():
    course_id = request.args.get("course_id")
    status = request.args.get("status")

    with get_connection() as conn:
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
            "SELECT * FROM study_groups" + where + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
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


@study_group_bp.route("/<int:group_id>", methods=["GET"])
@token_required
def get_group(group_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM study_groups WHERE group_id = ?", (group_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Study group {group_id} not found")
    log_activity("view", "study_group", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@study_group_bp.route("", methods=["POST"])
@token_required
def create_group():
    data = request.get_json(silent=True) or {}
    validate_study_group_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO study_groups
               (course_id, group_name, creator_id, max_members, meeting_schedule,
                location, is_virtual, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'Active')""",
            (
                data["course_id"],
                data["group_name"],
                data["creator_id"],
                data.get("max_members", 6),
                data.get("meeting_schedule", ""),
                data.get("location", ""),
                data.get("is_virtual", 1),
            ),
        )
        group_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Add creator as first member
        conn.execute(
            """INSERT INTO study_group_members
               (group_id, student_id, role)
               VALUES (?, ?, 'Leader')""",
            (group_id, data["creator_id"]),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM study_groups WHERE group_id = ?", (group_id,)
        ).fetchone()

    log_activity("create", "study_group", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@study_group_bp.route("/<int:group_id>", methods=["PUT"])
@token_required
def update_group(group_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM study_groups WHERE group_id = ?", (group_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Study group {group_id} not found")

    data = request.get_json(silent=True) or {}
    if not data:
        raise ValidationError("No fields provided for update")

    set_clauses = []
    values = []
    allowed = [
        "group_name", "max_members", "meeting_schedule",
        "location", "is_virtual", "status",
    ]
    for field in allowed:
        if field in data:
            set_clauses.append(field + " = ?")
            values.append(data[field])

    if not set_clauses:
        raise ValidationError("No valid fields to update")

    values.append(group_id)
    with transaction() as conn:
        conn.execute(
            "UPDATE study_groups SET " + ", ".join(set_clauses) + " WHERE group_id = ?",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM study_groups WHERE group_id = ?", (group_id,)
        ).fetchone()

    log_activity("update", "study_group", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Members ----

@study_group_bp.route("/<int:group_id>/members", methods=["GET"])
@token_required
def list_members(group_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM study_groups WHERE group_id = ?", (group_id,)
        ).fetchone()
        if not existing:
            raise ValidationError(f"Study group {group_id} not found")

        rows = conn.execute(
            """SELECT sgm.*, s.first_name, s.last_name
               FROM study_group_members sgm
               LEFT JOIN students s ON sgm.student_id = s.student_id
               WHERE sgm.group_id = ?
               ORDER BY sgm.joined_at""",
            (group_id,),
        ).fetchall()

    log_activity("view", "study_group_members", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@study_group_bp.route("/<int:group_id>/members", methods=["POST"])
@token_required
def add_member(group_id: int):
    with get_connection() as conn:
        group = conn.execute(
            "SELECT * FROM study_groups WHERE group_id = ?", (group_id,)
        ).fetchone()
    if not group:
        raise ValidationError(f"Study group {group_id} not found")
    if group["current_members"] >= group["max_members"]:
        raise ValidationError("Study group is full")

    data = request.get_json(silent=True) or {}
    if not data.get("student_id"):
        raise ValidationError("'student_id' is required")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO study_group_members (group_id, student_id, role)
               VALUES (?, ?, ?)""",
            (group_id, data["student_id"], data.get("role", "Member")),
        )
        conn.execute(
            "UPDATE study_groups SET current_members = current_members + 1 WHERE group_id = ?",
            (group_id,),
        )
        member_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM study_group_members WHERE membership_id = ?", (member_id,)
        ).fetchone()

    log_activity("create", "study_group_member", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
