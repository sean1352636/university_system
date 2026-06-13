"""Accessibility routes: accommodation requests, accommodations, and faculty notifications."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

accessibility_bp = Blueprint("accessibility", __name__, url_prefix="/api/accessibility")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- requests ----

@accessibility_bp.route("/requests", methods=["GET"])
@token_required
def list_requests():
    search = request.args.get("search")
    student_id = request.args.get("student_id")
    status = request.args.get("status")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM accommodation_requests WHERE student_name LIKE ? OR description LIKE ?",
                (pattern, pattern),
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
            "SELECT * FROM accommodation_requests" + where + " ORDER BY request_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM accommodation_requests" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "accommodation_requests", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@accessibility_bp.route("/requests/<int:request_id>", methods=["GET"])
@token_required
def get_request(request_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM accommodation_requests WHERE request_id = ?", (request_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"requests {request_id} not found")
    log_activity("view", "accommodation_requests", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@accessibility_bp.route("/requests", methods=["POST"])
@token_required
def create_request():
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "student_name", "accommodation_type", "description"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO accommodation_requests
               (student_id, student_name, accommodation_type, description, student_email, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data["student_id"], data["student_name"], data["accommodation_type"], data["description"], data.get("student_email", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM accommodation_requests WHERE request_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "accommodation_requests", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- accommodations ----

@accessibility_bp.route("/accommodations", methods=["GET"])
@token_required
def list_accommodations():
    search = request.args.get("search")
    student_id = request.args.get("student_id")
    is_active = request.args.get("is_active")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM accommodations WHERE description LIKE ?",
                (pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if is_active:
            conditions.append("is_active = ?")
            params.append(is_active)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM accommodations" + where + " ORDER BY accommodation_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM accommodations" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "accommodations", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@accessibility_bp.route("/accommodations/<int:accommodation_id>", methods=["GET"])
@token_required
def get_accommodation(accommodation_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM accommodations WHERE accommodation_id = ?", (accommodation_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"accommodations {accommodation_id} not found")
    log_activity("view", "accommodations", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@accessibility_bp.route("/accommodations", methods=["POST"])
@token_required
def create_accommodation():
    data = request.get_json(silent=True) or {}
    for field in ["request_id", "student_id", "accommodation_type"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO accommodations
               (request_id, student_id, accommodation_type, description, start_date, expiration_date, approved_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["request_id"], data["student_id"], data["accommodation_type"], data.get("description", ""), data.get("start_date", ""), data.get("expiration_date", ""), data.get("approved_by", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM accommodations WHERE accommodation_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "accommodations", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- request status and approval ----

@accessibility_bp.route("/requests/<int:request_id>/status", methods=["PUT"])
@token_required
def update_request_status(request_id: int):
    data = request.get_json(silent=True) or {}
    if "status" not in data:
        raise ValidationError("Missing required field: status")

    valid_statuses = ["Submitted", "Under Review", "Approved", "Denied", "Active"]
    if data["status"] not in valid_statuses:
        raise ValidationError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM accommodation_requests WHERE request_id = ?", (request_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Request {request_id} not found")

    reviewer_id = data.get("reviewer_id", g.current_user.get("sub"))
    reviewer_notes = data.get("reviewer_notes")

    with transaction() as conn:
        conn.execute(
            """UPDATE accommodation_requests
               SET status = ?, reviewed_by = ?, review_notes = ?, review_date = ?
               WHERE request_id = ?""",
            (data["status"], reviewer_id, reviewer_notes,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"), request_id),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM accommodation_requests WHERE request_id = ?", (request_id,)
        ).fetchone()

    log_activity("update", "accommodation_request_status", user=g.current_user.get("sub"),
                 details={"request_id": request_id, "status": data["status"]})
    return jsonify(_row_to_dict(row))


@accessibility_bp.route("/requests/<int:request_id>/approve", methods=["POST"])
@token_required
def approve_request(request_id: int):
    data = request.get_json(silent=True) or {}

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM accommodation_requests WHERE request_id = ?", (request_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Request {request_id} not found")
    req = _row_to_dict(row)

    approved_by = data.get("approved_by", g.current_user.get("sub"))
    start_date = data.get("start_date", datetime.now().strftime("%Y-%m-%d"))
    duration_months = int(data.get("duration_months", 12))
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_date = (start_dt + timedelta(days=duration_months * 30)).strftime("%Y-%m-%d")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with transaction() as conn:
        conn.execute(
            """UPDATE accommodation_requests
               SET status = 'Approved', reviewed_by = ?, review_date = ?
               WHERE request_id = ?""",
            (approved_by, now, request_id),
        )
        conn.execute(
            """INSERT INTO accommodations
               (student_id, accommodation_type, description,
                start_date, end_date, status, approved_by, approval_date,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)""",
            (req["student_id"], req["accommodation_type"], req.get("description", ""),
             start_date, end_date, approved_by, now, now, now),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        acc_row = conn.execute(
            "SELECT * FROM accommodations WHERE id = ?", (new_id,)
        ).fetchone()

    log_activity("approve", "accommodation_request", user=g.current_user.get("sub"),
                 details={"request_id": request_id, "accommodation_id": new_id})
    return jsonify(_row_to_dict(acc_row)), 201


# ---- expiring accommodations ----

@accessibility_bp.route("/accommodations/expiring", methods=["GET"])
@token_required
def list_expiring_accommodations():
    days = int(request.args.get("days", 30))
    student_id = request.args.get("student_id")
    threshold_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")

    with get_connection() as conn:
        conditions = ["status = 'active'", "end_date <= ?"]
        params: list = [threshold_date]
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)

        where = " WHERE " + " AND ".join(conditions)
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM accommodations" + where + " ORDER BY end_date ASC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM accommodations" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "expiring_accommodations", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


# ---- documentation ----

@accessibility_bp.route("/requests/<int:request_id>/documentation", methods=["POST"])
@token_required
def upload_documentation(request_id: int):
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "filename"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM accommodation_requests WHERE request_id = ?", (request_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Request {request_id} not found")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO accommodation_documentation
               (request_id, student_id, filename, file_path, upload_date, document_type)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (request_id, data["student_id"], data["filename"],
             data.get("file_path", ""), now, data.get("document_type", "Medical Documentation")),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM accommodation_documentation WHERE doc_id = ?", (new_id,)
        ).fetchone()

    log_activity("upload", "accommodation_documentation", user=g.current_user.get("sub"),
                 details={"request_id": request_id, "doc_id": new_id})
    return jsonify(_row_to_dict(row)), 201


@accessibility_bp.route("/requests/<int:request_id>/documentation", methods=["GET"])
@token_required
def get_documentation(request_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM accommodation_requests WHERE request_id = ?", (request_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Request {request_id} not found")

    with get_connection() as conn:
        page, per_page, offset = get_pagination_params()
        rows = conn.execute(
            "SELECT * FROM accommodation_documentation WHERE request_id = ? ORDER BY upload_date DESC LIMIT ? OFFSET ?",
            (request_id, per_page, offset),
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM accommodation_documentation WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "accommodation_documentation", user=g.current_user.get("sub"),
                 details={"request_id": request_id})
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


# ---- deactivate accommodation ----

@accessibility_bp.route("/accommodations/<int:accommodation_id>", methods=["DELETE"])
@token_required
def deactivate_accommodation(accommodation_id: int):
    data = request.get_json(silent=True) or {}

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM accommodations WHERE id = ?", (accommodation_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Accommodation {accommodation_id} not found")

    reason = data.get("reason", "")
    with transaction() as conn:
        conn.execute(
            "UPDATE accommodations SET status = 'inactive', updated_at = ? WHERE id = ?",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), accommodation_id),
        )

    log_activity("deactivate", "accommodation", user=g.current_user.get("sub"),
                 details={"accommodation_id": accommodation_id, "reason": reason})
    return jsonify({"message": f"Accommodation {accommodation_id} deactivated"}), 200


# ---- pending requests ----

@accessibility_bp.route("/requests/pending", methods=["GET"])
@token_required
def list_pending_requests():
    with get_connection() as conn:
        page, per_page, offset = get_pagination_params()
        rows = conn.execute(
            """SELECT * FROM accommodation_requests
               WHERE status IN ('pending', 'Submitted', 'Under Review')
               ORDER BY requested_date ASC LIMIT ? OFFSET ?""",
            (per_page, offset),
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM accommodation_requests WHERE status IN ('pending', 'Submitted', 'Under Review')"
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "pending_accommodation_requests", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


# ---- statistics ----

@accessibility_bp.route("/statistics", methods=["GET"])
@token_required
def get_statistics():
    with get_connection() as conn:
        total_requests = conn.execute(
            "SELECT COUNT(*) FROM accommodation_requests"
        ).fetchone()[0]

        pending_requests = conn.execute(
            "SELECT COUNT(*) FROM accommodation_requests WHERE status IN ('pending', 'Submitted', 'Under Review')"
        ).fetchone()[0]

        active_accommodations = conn.execute(
            "SELECT COUNT(*) FROM accommodations WHERE status = 'active'"
        ).fetchone()[0]

        by_type_rows = conn.execute(
            "SELECT accommodation_type, COUNT(*) as count FROM accommodations WHERE status = 'active' GROUP BY accommodation_type"
        ).fetchall()
        by_type = {row[0]: row[1] for row in by_type_rows}

        threshold_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        expiring_soon = conn.execute(
            "SELECT COUNT(*) FROM accommodations WHERE status = 'active' AND end_date <= ?",
            (threshold_date,),
        ).fetchone()[0]

    log_activity("view", "accessibility_statistics", user=g.current_user.get("sub"))
    return jsonify({
        "total_requests": total_requests,
        "pending_requests": pending_requests,
        "active_accommodations": active_accommodations,
        "by_type": by_type,
        "expiring_soon": expiring_soon,
    })


# ---- renewals ----

@accessibility_bp.route("/requests/<int:request_id>/renew", methods=["POST"])
@token_required
def request_renewal(request_id: int):
    data = request.get_json(silent=True) or {}

    # Look up the accommodation linked to this request to find accommodation_id and student_id
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM accommodation_requests WHERE request_id = ?", (request_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Request {request_id} not found")
    req = _row_to_dict(row)

    # Find the active accommodation for this request's student and type
    with get_connection() as conn:
        acc_row = conn.execute(
            """SELECT * FROM accommodations
               WHERE student_id = ? AND accommodation_type = ? AND status = 'active'
               ORDER BY end_date DESC LIMIT 1""",
            (req["student_id"], req["accommodation_type"]),
        ).fetchone()
    if not acc_row:
        raise ValidationError(f"No active accommodation found for request {request_id}")
    acc = _row_to_dict(acc_row)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    notes = data.get("notes")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO accommodation_renewals
               (accommodation_id, student_id, renewal_request_date, status, notes)
               VALUES (?, ?, ?, 'Pending', ?)""",
            (acc["id"], req["student_id"], now, notes),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM accommodation_renewals WHERE renewal_id = ?", (new_id,)
        ).fetchone()

    log_activity("request", "accommodation_renewal", user=g.current_user.get("sub"),
                 details={"request_id": request_id, "renewal_id": new_id})
    return jsonify(_row_to_dict(row)), 201


@accessibility_bp.route("/renewals", methods=["GET"])
@token_required
def list_renewals():
    student_id = request.args.get("student_id")
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if student_id:
            conditions.append("ar.student_id = ?")
            params.append(student_id)
        if status:
            conditions.append("ar.status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            """SELECT ar.*, a.accommodation_type, a.end_date as accommodation_end_date
               FROM accommodation_renewals ar
               JOIN accommodations a ON ar.accommodation_id = a.id"""
            + where + " ORDER BY ar.renewal_request_date DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            """SELECT COUNT(*) FROM accommodation_renewals ar
               JOIN accommodations a ON ar.accommodation_id = a.id""" + where,
            params_count,
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "accommodation_renewals", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@accessibility_bp.route("/renewals/<int:renewal_id>", methods=["PUT"])
@token_required
def process_renewal(renewal_id: int):
    data = request.get_json(silent=True) or {}
    if "status" not in data:
        raise ValidationError("Missing required field: status")

    if data["status"] not in ("Approved", "Denied"):
        raise ValidationError("Status must be 'Approved' or 'Denied'")

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM accommodation_renewals WHERE renewal_id = ?", (renewal_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Renewal {renewal_id} not found")
    renewal = _row_to_dict(row)

    processed_by = data.get("processed_by", g.current_user.get("sub"))
    notes = data.get("notes")
    extend_months = int(data.get("extend_months", 12))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with transaction() as conn:
        conn.execute(
            """UPDATE accommodation_renewals
               SET status = ?, processed_date = ?, processed_by = ?, notes = ?
               WHERE renewal_id = ?""",
            (data["status"], now, processed_by, notes, renewal_id),
        )

        if data["status"] == "Approved":
            acc_row = conn.execute(
                "SELECT end_date FROM accommodations WHERE id = ?",
                (renewal["accommodation_id"],),
            ).fetchone()
            if acc_row:
                current_end = datetime.strptime(acc_row[0], "%Y-%m-%d")
                new_end = (current_end + timedelta(days=extend_months * 30)).strftime("%Y-%m-%d")
                conn.execute(
                    "UPDATE accommodations SET end_date = ?, updated_at = ? WHERE id = ?",
                    (new_end, now, renewal["accommodation_id"]),
                )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM accommodation_renewals WHERE renewal_id = ?", (renewal_id,)
        ).fetchone()

    log_activity("process", "accommodation_renewal", user=g.current_user.get("sub"),
                 details={"renewal_id": renewal_id, "status": data["status"]})
    return jsonify(_row_to_dict(row))
