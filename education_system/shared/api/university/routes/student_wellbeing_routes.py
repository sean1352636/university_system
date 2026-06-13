"""Student wellbeing routes: referrals, check-ins, and counselling sessions."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

student_wellbeing_bp = Blueprint("student_wellbeing", __name__, url_prefix="/api/student-wellbeing")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- referrals ----

@student_wellbeing_bp.route("/referrals", methods=["GET"])
@token_required
def list_referrals():
    student_id = request.args.get("student_id")
    status = request.args.get("status")
    concern_type = request.args.get("concern_type")
    urgency = request.args.get("urgency")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if concern_type:
            conditions.append("concern_type = ?")
            params.append(concern_type)
        if urgency:
            conditions.append("urgency = ?")
            params.append(urgency)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM wellbeing_referrals" + where + " ORDER BY id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM wellbeing_referrals" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "wellbeing_referrals", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@student_wellbeing_bp.route("/referrals/<int:referral_id>", methods=["GET"])
@token_required
def get_referral(referral_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM wellbeing_referrals WHERE id = ?", (referral_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Wellbeing referral {referral_id} not found")
    log_activity("view", "wellbeing_referral", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@student_wellbeing_bp.route("/referrals", methods=["POST"])
@token_required
def create_referral():
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "referred_by", "concern_type"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO wellbeing_referrals
               (student_id, referred_by, concern_type, description, urgency)
               VALUES (?, ?, ?, ?, ?)""",
            (data["student_id"], data["referred_by"], data["concern_type"],
             data.get("description", ""), data.get("urgency", "normal")),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM wellbeing_referrals WHERE id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "wellbeing_referral", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@student_wellbeing_bp.route("/referrals/<int:referral_id>", methods=["PUT"])
@token_required
def update_referral(referral_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM wellbeing_referrals WHERE id = ?", (referral_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Wellbeing referral {referral_id} not found")

    data = request.get_json(silent=True) or {}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    allowed = ["concern_type", "description", "urgency", "status"]
    sets = ["updated_at = ?"]
    params: list = [now]
    for key in allowed:
        if key in data:
            sets.append(f"{key} = ?")
            params.append(data[key])
    params.append(referral_id)

    with transaction() as conn:
        conn.execute(
            f"UPDATE wellbeing_referrals SET {', '.join(sets)} WHERE id = ?", params
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM wellbeing_referrals WHERE id = ?", (referral_id,)
        ).fetchone()

    log_activity("update", "wellbeing_referral", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- check-ins ----

@student_wellbeing_bp.route("/checkins", methods=["GET"])
@token_required
def list_checkins():
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
            "SELECT * FROM wellbeing_checkins" + where + " ORDER BY id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM wellbeing_checkins" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "wellbeing_checkins", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@student_wellbeing_bp.route("/checkins/<int:checkin_id>", methods=["GET"])
@token_required
def get_checkin(checkin_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM wellbeing_checkins WHERE id = ?", (checkin_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Wellbeing check-in {checkin_id} not found")
    log_activity("view", "wellbeing_checkin", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@student_wellbeing_bp.route("/checkins", methods=["POST"])
@token_required
def create_checkin():
    data = request.get_json(silent=True) or {}
    if "student_id" not in data:
        raise ValidationError("Missing required field: student_id")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO wellbeing_checkins
               (student_id, mood_rating, notes)
               VALUES (?, ?, ?)""",
            (data["student_id"], data.get("mood_rating"), data.get("notes", "")),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM wellbeing_checkins WHERE id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "wellbeing_checkin", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- counselling sessions ----

@student_wellbeing_bp.route("/counselling", methods=["GET"])
@token_required
def list_counselling():
    student_id = request.args.get("student_id")
    counsellor = request.args.get("counsellor")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if counsellor:
            conditions.append("counsellor = ?")
            params.append(counsellor)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM counselling_sessions" + where + " ORDER BY id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM counselling_sessions" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "counselling_sessions", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@student_wellbeing_bp.route("/counselling/<int:session_id>", methods=["GET"])
@token_required
def get_counselling(session_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM counselling_sessions WHERE id = ?", (session_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Counselling session {session_id} not found")
    log_activity("view", "counselling_session", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@student_wellbeing_bp.route("/counselling", methods=["POST"])
@token_required
def create_counselling():
    data = request.get_json(silent=True) or {}
    if "student_id" not in data:
        raise ValidationError("Missing required field: student_id")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO counselling_sessions
               (student_id, counsellor, session_date, notes, outcome)
               VALUES (?, ?, ?, ?, ?)""",
            (data["student_id"], data.get("counsellor", ""),
             data.get("session_date", ""), data.get("notes", ""),
             data.get("outcome", "")),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM counselling_sessions WHERE id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "counselling_session", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@student_wellbeing_bp.route("/referrals/<int:referral_id>", methods=["DELETE"])
@token_required
def delete_referral(referral_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM wellbeing_referrals WHERE id = ?", (referral_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Wellbeing referral {referral_id} not found")

    with transaction() as conn:
        conn.execute("DELETE FROM wellbeing_referrals WHERE id = ?", (referral_id,))

    log_activity("delete", "wellbeing_referral", user=g.current_user.get("sub"))
    return jsonify({"message": "Referral deleted"})
