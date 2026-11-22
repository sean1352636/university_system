"""Student wellbeing routes: referrals, check-ins, and counselling sessions.

Who may do what (see ``_health_access``):

* **referrals** - any member of staff (or the student themselves) may raise
  one; the wellbeing team reads, updates and deletes them, and the person
  who raised a referral can read it back;
* **check-ins** - the student's own, plus the wellbeing team;
* **counselling sessions** - the counselling team (counsellors and the
  health team, not wellness officers); a student sees their own sessions
  without the counsellor's notes and outcome.

``referred_by`` / ``logged_by`` / ``counsellor`` default to the signed-in
caller and are never taken on trust from a non-team caller.
"""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.api.university.pastoral._health_access import (
    audit_health_view,
    deny_unless_health_team,
    deny_unless_may_view_health,
    health_caller,
    health_scope,
    is_health_team,
    own_student_id,
    seal,
    unseal,
)
from education_system.platform.delivery.api.university.auth import is_staff, token_required
from education_system.platform.delivery.api.university.pagination import get_pagination_params, paginated_response
from education_system.systems.university.infrastructure.exceptions import ValidationError
from education_system.systems.university.infrastructure.sql_safety import escape_like
from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity

logger = logging.getLogger(__name__)

student_wellbeing_bp = Blueprint("student_wellbeing", __name__, url_prefix="/api/student-wellbeing")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


_FORBIDDEN = {"error": "Forbidden", "status": 403}


def _caller_name() -> str:
    who = health_caller()
    return who.username if who is not None else ""


def _confine(requested, scope):
    """The student filter for a scoped caller, or a 403 if they asked for someone else."""
    if scope is None:
        return requested, None
    if requested and str(requested) != scope:
        return None, (jsonify({**_FORBIDDEN, "message": "You can only see your own records"}), 403)
    return scope, None


#: Counsellor-only columns hidden from the student's own view.
_COUNSELLOR_ONLY = ("notes", "outcome")


# ---- referrals ----

@student_wellbeing_bp.route("/referrals", methods=["GET"])
@token_required
def list_referrals():
    student_id = request.args.get("student_id")
    status = request.args.get("status")
    concern_type = request.args.get("concern_type")
    urgency = request.args.get("urgency")
    team = is_health_team(pastoral=True)
    if not team and not is_staff():
        return deny_unless_health_team("see wellbeing referrals", pastoral=True)

    with get_connection() as conn:
        conditions = []
        params: list = []
        if not team:
            # Staff outside the team see only the referrals they raised.
            conditions.append("referred_by = ?")
            params.append(_caller_name())
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

    denial = audit_health_view("wellbeing_referrals", student_id=student_id)
    if denial is not None:
        return denial
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
    if is_health_team(pastoral=True) or (
            is_staff() and str(row["referred_by"] or "") == _caller_name()):
        denial = audit_health_view("wellbeing_referral", student_id=row["student_id"],
                                   record_id=referral_id)
    else:
        denial = deny_unless_health_team("see wellbeing referrals", pastoral=True)
    if denial is not None:
        return denial
    log_activity("view", "wellbeing_referral", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@student_wellbeing_bp.route("/referrals", methods=["POST"])
@token_required
def create_referral():
    data = request.get_json(silent=True) or {}
    if is_health_team(pastoral=True):
        data.setdefault("referred_by", _caller_name())
    elif is_staff():
        data["referred_by"] = _caller_name()
    else:
        own = own_student_id()
        if own is None or str(data.get("student_id") or own) != own:
            return jsonify({**_FORBIDDEN,
                            "message": "Students can only refer themselves"}), 403
        data["student_id"] = own
        data["referred_by"] = _caller_name()
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
    denial = deny_unless_health_team("update wellbeing referrals", pastoral=True)
    if denial is not None:
        return denial
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
        # db-audit: ignore[DBW001] - join over a code-controlled list
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
    scope, denial = health_scope(pastoral=True)
    if denial is not None:
        return denial
    student_id, denial = _confine(request.args.get("student_id"), scope)
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
            "SELECT * FROM wellbeing_checkins" + where + " ORDER BY id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM wellbeing_checkins" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    denial = audit_health_view("wellbeing_checkins", student_id=student_id)
    if denial is not None:
        return denial
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
    denial = deny_unless_may_view_health(row["student_id"], "wellbeing_checkin",
                                         record_id=checkin_id, team_area="wellbeing")
    if denial is not None:
        return denial
    log_activity("view", "wellbeing_checkin", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@student_wellbeing_bp.route("/checkins", methods=["POST"])
@token_required
def create_checkin():
    data = request.get_json(silent=True) or {}
    if not is_health_team(pastoral=True):
        own = own_student_id()
        if own is None or str(data.get("student_id") or own) != own:
            return jsonify({**_FORBIDDEN,
                            "message": "You can only log your own check-ins"}), 403
        data["student_id"] = own
    if "student_id" not in data:
        raise ValidationError("Missing required field: student_id")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO wellbeing_checkins
               (student_id, mood_rating, notes, logged_by)
               VALUES (?, ?, ?, ?)""",
            (data["student_id"], data.get("mood_rating"), data.get("notes", ""),
             _caller_name()),
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
    scope, denial = health_scope(area="counselling")
    if denial is not None:
        return denial
    student_id, denial = _confine(request.args.get("student_id"), scope)
    if denial is not None:
        return denial
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

    denial = audit_health_view("counselling_sessions", student_id=student_id)
    if denial is not None:
        return denial
    log_activity("view", "counselling_sessions", user=g.current_user.get("sub"))
    items = unseal(rows, "counselling_sessions")
    if scope is not None:
        items = [{k: v for k, v in item.items() if k not in _COUNSELLOR_ONLY} for item in items]
    return jsonify(paginated_response(items, total, page, per_page))


@student_wellbeing_bp.route("/counselling/<int:session_id>", methods=["GET"])
@token_required
def get_counselling(session_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM counselling_sessions WHERE id = ?", (session_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Counselling session {session_id} not found")
    denial = deny_unless_may_view_health(row["student_id"], "counselling_session",
                                         record_id=session_id, team_area="counselling")
    if denial is not None:
        return denial
    log_activity("view", "counselling_session", user=g.current_user.get("sub"))
    item = unseal([row], "counselling_sessions")[0]
    if not is_health_team(area="counselling"):
        item = {k: v for k, v in item.items() if k not in _COUNSELLOR_ONLY}
    return jsonify(item)


@student_wellbeing_bp.route("/counselling", methods=["POST"])
@token_required
def create_counselling():
    denial = deny_unless_health_team("record counselling sessions", area="counselling")
    if denial is not None:
        return denial
    data = request.get_json(silent=True) or {}
    if "student_id" not in data:
        raise ValidationError("Missing required field: student_id")
    sealed = seal("counselling_sessions", {"notes": data.get("notes", ""),
                                           "outcome": data.get("outcome", "")})

    with transaction() as conn:
        conn.execute(
            """INSERT INTO counselling_sessions
               (student_id, counsellor, session_date, notes, outcome)
               VALUES (?, ?, ?, ?, ?)""",
            (data["student_id"], data.get("counsellor") or _caller_name(),
             data.get("session_date", ""), sealed["notes"], sealed["outcome"]),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM counselling_sessions WHERE id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "counselling_session", user=g.current_user.get("sub"))
    return jsonify(unseal([row], "counselling_sessions")[0]), 201


@student_wellbeing_bp.route("/referrals/<int:referral_id>", methods=["DELETE"])
@token_required
def delete_referral(referral_id: int):
    denial = deny_unless_health_team("delete wellbeing referrals", pastoral=True)
    if denial is not None:
        return denial
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
