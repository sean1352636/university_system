"""Campus mail routes: packages, PO boxes, forwarding, and transactions."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.post_18.university_system.core.exceptions import ValidationError
from education_system.post_18.university_system.core.sql_safety import escape_like
from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

mail_bp = Blueprint("mail", __name__, url_prefix="/api/mail")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- packages ----

@mail_bp.route("/packages", methods=["GET"])
@token_required
def list_packages():
    search = request.args.get("search")
    recipient_id = request.args.get("recipient_id")
    status = request.args.get("status")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM mail_packages WHERE tracking_number LIKE ? OR recipient_name LIKE ? OR sender_name LIKE ?",
                (pattern, pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if recipient_id:
            conditions.append("recipient_id = ?")
            params.append(recipient_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM mail_packages" + where + " ORDER BY package_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM mail_packages" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "mail_packages", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@mail_bp.route("/packages/<int:package_id>", methods=["GET"])
@token_required
def get_package(package_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM mail_packages WHERE package_id = ?", (package_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"packages {package_id} not found")
    log_activity("view", "mail_packages", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@mail_bp.route("/packages", methods=["POST"])
@token_required
def create_package():
    data = request.get_json(silent=True) or {}
    for field in ["tracking_number", "recipient_id", "recipient_name", "sender_name"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO mail_packages
               (tracking_number, recipient_id, recipient_name, sender_name, recipient_email, sender_address, package_type, description, weight_kg, storage_location, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["tracking_number"], data["recipient_id"], data["recipient_name"], data["sender_name"], data.get("recipient_email", ""), data.get("sender_address", ""), data.get("package_type", ""), data.get("description", ""), data.get("weight_kg", ""), data.get("storage_location", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM mail_packages WHERE package_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "mail_packages", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- po-boxes ----

@mail_bp.route("/po-boxes", methods=["GET"])
@token_required
def list_po_boxes():
    search = request.args.get("search")
    holder_id = request.args.get("holder_id")
    status = request.args.get("status")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM mail_po_boxes WHERE holder_name LIKE ? OR box_number LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if holder_id:
            conditions.append("holder_id = ?")
            params.append(holder_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM mail_po_boxes" + where + " ORDER BY box_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM mail_po_boxes" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "mail_po_boxes", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@mail_bp.route("/po-boxes/<int:box_id>", methods=["GET"])
@token_required
def get_po_boxe(box_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM mail_po_boxes WHERE box_id = ?", (box_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"po-boxes {box_id} not found")
    log_activity("view", "mail_po_boxes", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@mail_bp.route("/po-boxes", methods=["POST"])
@token_required
def create_po_boxe():
    data = request.get_json(silent=True) or {}
    for field in ["box_number", "holder_id", "holder_name", "size", "monthly_fee"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO mail_po_boxes
               (box_number, holder_id, holder_name, size, monthly_fee, holder_email, rental_start, rental_end, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["box_number"], data["holder_id"], data["holder_name"], data["size"], data["monthly_fee"], data.get("holder_email", ""), data.get("rental_start", ""), data.get("rental_end", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM mail_po_boxes WHERE box_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "mail_po_boxes", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
