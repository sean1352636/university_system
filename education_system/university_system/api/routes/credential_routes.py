"""Credential routes: blockchain credentials, digital badges, micro-credentials, certifications."""

from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify, request

from education_system.university_system.api.auth import admin_required, token_required
from education_system.university_system.api.pagination import get_pagination_params, paginated_response
from education_system.university_system.api.validators import (
    validate_badge_create,
    validate_certification_create,
    validate_credential_create,
)
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

credential_bp = Blueprint("credentials", __name__, url_prefix="/api/credentials")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- Blockchain Credentials ----

@credential_bp.route("/blockchain", methods=["GET"])
@token_required
def list_blockchain_credentials():
    student_id = request.args.get("student_id")
    credential_type = request.args.get("credential_type")

    with get_connection() as conn:
        conditions = ["is_revoked = 0"]
        params: list = []
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if credential_type:
            conditions.append("credential_type = ?")
            params.append(credential_type)

        where = " WHERE " + " AND ".join(conditions)
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM blockchain_credentials" + where + " ORDER BY issue_date DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM blockchain_credentials" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "blockchain_credentials", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@credential_bp.route("/blockchain/<int:credential_id>", methods=["GET"])
@token_required
def get_blockchain_credential(credential_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM blockchain_credentials WHERE credential_id = ?",
            (credential_id,),
        ).fetchone()
    if not row:
        raise ValidationError(f"Credential {credential_id} not found")
    log_activity("view", "blockchain_credential", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@credential_bp.route("/blockchain/verify/<blockchain_hash>", methods=["GET"])
def verify_credential(blockchain_hash: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM blockchain_credentials WHERE blockchain_hash = ?",
            (blockchain_hash,),
        ).fetchone()
    if not row:
        return jsonify({"verified": False, "message": "Credential not found"}), 404
    return jsonify({
        "verified": True,
        "is_revoked": bool(row["is_revoked"]),
        "credential": _row_to_dict(row),
    })


@credential_bp.route("/blockchain", methods=["POST"])
@token_required
@admin_required
def create_blockchain_credential():
    data = request.get_json(silent=True) or {}
    validate_credential_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO blockchain_credentials
               (student_id, credential_type, credential_name, issue_date,
                blockchain_hash, blockchain_address, ipfs_hash, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["student_id"],
                data["credential_type"],
                data["credential_name"],
                data["issue_date"],
                data["blockchain_hash"],
                data.get("blockchain_address"),
                data.get("ipfs_hash"),
                data.get("metadata"),
            ),
        )
        cid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM blockchain_credentials WHERE credential_id = ?", (cid,)
        ).fetchone()

    log_activity("create", "blockchain_credential", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- Digital Badges ----

@credential_bp.route("/badges", methods=["GET"])
@token_required
def list_badges():
    badge_type = request.args.get("badge_type")

    with get_connection() as conn:
        conditions = ["is_active = 1"]
        params: list = []
        if badge_type:
            conditions.append("badge_type = ?")
            params.append(badge_type)

        where = " WHERE " + " AND ".join(conditions)
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM digital_badges" + where + " ORDER BY badge_name LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM digital_badges" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "digital_badges", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@credential_bp.route("/badges", methods=["POST"])
@token_required
@admin_required
def create_badge():
    data = request.get_json(silent=True) or {}
    validate_badge_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO digital_badges
               (badge_name, description, criteria, badge_image_url, issuer_name, badge_type)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                data["badge_name"],
                data.get("description", ""),
                data["criteria"],
                data.get("badge_image_url"),
                data["issuer_name"],
                data.get("badge_type", "skill"),
            ),
        )
        bid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM digital_badges WHERE badge_id = ?", (bid,)
        ).fetchone()

    log_activity("create", "digital_badge", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- Micro-Credentials ----

@credential_bp.route("/micro", methods=["GET"])
@token_required
def list_micro_credentials():
    category = request.args.get("category")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if category:
            conditions.append("category = ?")
            params.append(category)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM micro_credentials" + where + " ORDER BY skill_name LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM micro_credentials" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "micro_credentials", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


# ---- Certifications ----

@credential_bp.route("/certifications", methods=["GET"])
@token_required
def list_certifications():
    user_id = request.args.get("user_id")
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM certifications" + where + " ORDER BY issue_date DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM certifications" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "certifications", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@credential_bp.route("/certifications", methods=["POST"])
@token_required
def create_certification():
    data = request.get_json(silent=True) or {}
    validate_certification_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO certifications
               (user_id, name, issuing_body, credential_id, issue_date,
                expiry_date, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, 'active', ?)""",
            (
                data["user_id"],
                data["name"],
                data.get("issuing_body"),
                data.get("credential_id"),
                data.get("issue_date"),
                data.get("expiry_date"),
                data.get("notes", ""),
            ),
        )
        cid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM certifications WHERE cert_id = ?", (cid,)
        ).fetchone()

    log_activity("create", "certification", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
