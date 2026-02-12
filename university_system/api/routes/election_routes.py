"""Election routes: polls, candidates, votes, union representatives."""

from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify, request

from university_system.api.auth import admin_required, token_required
from university_system.api.pagination import get_pagination_params, paginated_response
from university_system.api.validators import (
    validate_election_candidate_create,
    validate_poll_create,
)
from university_system.core.exceptions import ValidationError
from university_system.infrastructure.database.db import get_connection, transaction
from university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

election_bp = Blueprint("elections", __name__, url_prefix="/api/elections")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- Polls ----

@election_bp.route("/polls", methods=["GET"])
@token_required
def list_polls():
    status = request.args.get("status")

    with get_connection() as conn:
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
            "SELECT * FROM polls" + where + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM polls" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "polls", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@election_bp.route("/polls/<int:poll_id>", methods=["GET"])
@token_required
def get_poll(poll_id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM polls WHERE id = ?", (poll_id,)).fetchone()
        if not row:
            raise ValidationError(f"Poll {poll_id} not found")

        options = conn.execute(
            "SELECT * FROM poll_options WHERE poll_id = ? ORDER BY id",
            (poll_id,),
        ).fetchall()

    result = _row_to_dict(row)
    result["options"] = [_row_to_dict(o) for o in options]

    log_activity("view", "poll", user=g.current_user.get("sub"))
    return jsonify(result)


@election_bp.route("/polls", methods=["POST"])
@token_required
@admin_required
def create_poll():
    data = request.get_json(silent=True) or {}
    validate_poll_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO polls
               (title, description, poll_type, start_date, end_date, max_votes_per_user, status)
               VALUES (?, ?, ?, ?, ?, ?, 'active')""",
            (
                data["title"],
                data.get("description", ""),
                data.get("poll_type", "general"),
                data["start_date"],
                data["end_date"],
                data.get("max_votes_per_user", 1),
            ),
        )
        pid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        for opt in data.get("options", []):
            conn.execute(
                "INSERT INTO poll_options (poll_id, option_text) VALUES (?, ?)",
                (pid, opt),
            )

    with get_connection() as conn:
        row = conn.execute("SELECT * FROM polls WHERE id = ?", (pid,)).fetchone()

    log_activity("create", "poll", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- Poll Votes ----

@election_bp.route("/polls/<int:poll_id>/vote", methods=["POST"])
@token_required
def cast_poll_vote(poll_id: int):
    data = request.get_json(silent=True) or {}
    option_id = data.get("option_id")
    if not option_id:
        raise ValidationError("option_id is required")

    with get_connection() as conn:
        poll = conn.execute("SELECT * FROM polls WHERE id = ?", (poll_id,)).fetchone()
        if not poll:
            raise ValidationError(f"Poll {poll_id} not found")
        if poll["status"] != "active":
            raise ValidationError("Poll is not active")

    with transaction() as conn:
        conn.execute(
            "INSERT INTO poll_votes (poll_id, option_id, member_id) VALUES (?, ?, ?)",
            (poll_id, option_id, g.current_user.get("user_id")),
        )
        conn.execute(
            "UPDATE poll_options SET votes = votes + 1 WHERE id = ?",
            (option_id,),
        )

    log_activity("create", "poll_vote", user=g.current_user.get("sub"))
    return jsonify({"message": "Vote recorded"}), 201


# ---- Election Candidates ----

@election_bp.route("/candidates", methods=["GET"])
@token_required
def list_candidates():
    election_id = request.args.get("election_id")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if election_id:
            conditions.append("election_id = ?")
            params.append(election_id)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        rows = conn.execute(
            "SELECT * FROM election_candidates" + where + " ORDER BY votes DESC",
            params,
        ).fetchall()

    log_activity("view", "election_candidates", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@election_bp.route("/candidates", methods=["POST"])
@token_required
def create_candidate():
    data = request.get_json(silent=True) or {}
    validate_election_candidate_create(data)

    with transaction() as conn:
        conn.execute(
            "INSERT INTO election_candidates (election_id, student_id, manifesto) VALUES (?, ?, ?)",
            (data["election_id"], data["student_id"], data.get("manifesto", "")),
        )
        cid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM election_candidates WHERE id = ?", (cid,)
        ).fetchone()

    log_activity("create", "election_candidate", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- Election Votes ----

@election_bp.route("/vote", methods=["POST"])
@token_required
def cast_election_vote():
    data = request.get_json(silent=True) or {}
    election_id = data.get("election_id")
    candidate_id = data.get("candidate_id")
    if not election_id or not candidate_id:
        raise ValidationError("election_id and candidate_id are required")

    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with transaction() as conn:
        conn.execute(
            "INSERT INTO election_votes (election_id, voter_id, candidate_id, vote_time) VALUES (?, ?, ?, ?)",
            (election_id, g.current_user.get("sub"), candidate_id, now),
        )
        conn.execute(
            "UPDATE election_candidates SET votes = votes + 1 WHERE id = ?",
            (candidate_id,),
        )

    log_activity("create", "election_vote", user=g.current_user.get("sub"))
    return jsonify({"message": "Vote recorded"}), 201


# ---- Union Representatives ----

@election_bp.route("/representatives", methods=["GET"])
@token_required
def list_representatives():
    status = request.args.get("status")
    department = request.args.get("department")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if department:
            conditions.append("department = ?")
            params.append(department)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        rows = conn.execute(
            "SELECT * FROM union_representatives" + where + " ORDER BY position",
            params,
        ).fetchall()

    log_activity("view", "union_representatives", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})
