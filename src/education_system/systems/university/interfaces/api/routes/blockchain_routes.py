"""Blockchain routes: credentials, verifications, digital badges, and wallets."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.platform.delivery.api.university.auth import admin_required, token_required
from education_system.platform.delivery.api.university.pagination import get_pagination_params, paginated_response
from education_system.systems.university.infrastructure.exceptions import ValidationError
from education_system.systems.university.infrastructure.sql_safety import escape_like
from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.domains.finance.domain.blockchain.services import (
    CredentialNotFoundError,
    issue_credential,
    revoke_credential,
    verify_credential,
)

logger = logging.getLogger(__name__)

blockchain_bp = Blueprint("blockchain", __name__, url_prefix="/api/blockchain")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- credentials ----

@blockchain_bp.route("/credentials", methods=["GET"])
@token_required
def list_credentials():
    search = request.args.get("search")
    student_id = request.args.get("student_id")
    status = request.args.get("status")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                """SELECT * FROM blockchain_credentials
                   WHERE credential_type LIKE ? ESCAPE '\\'
                      OR credential_name LIKE ? ESCAPE '\\'""",
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
            normalized = status.strip().lower()
            if normalized not in {"active", "revoked"}:
                raise ValidationError("status must be 'active' or 'revoked'")
            conditions.append("is_revoked = ?")
            params.append(1 if normalized == "revoked" else 0)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM blockchain_credentials" + where + " ORDER BY credential_id DESC LIMIT ? OFFSET ?",
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


@blockchain_bp.route("/credentials/<int:credential_id>", methods=["GET"])
@token_required
def get_credential(credential_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM blockchain_credentials WHERE credential_id = ?", (credential_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"credentials {credential_id} not found")
    log_activity("view", "blockchain_credentials", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@blockchain_bp.route("/credentials", methods=["POST"])
@token_required
@admin_required
def create_credential():
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "credential_type", "credential_name", "issuer"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")
    try:
        credential = issue_credential(
            student_id=str(data["student_id"]),
            credential_type=str(data["credential_type"]),
            credential_name=str(data["credential_name"]),
            issuer=str(data["issuer"]),
            issue_date=data.get("issue_date"),
            blockchain_address=data.get("blockchain_address"),
            ipfs_hash=data.get("ipfs_hash"),
            claims=data.get("claims"),
            authoritative_record=data.get("authoritative_record"),
            record_type=data.get("record_type"),
            record_id=data.get("record_id"),
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    log_activity(
        "create",
        "blockchain_credentials",
        credential_id=credential["credential_id"],
        user=g.current_user.get("sub"),
    )
    return jsonify(credential), 201


@blockchain_bp.route("/credentials/verify/<string:credential_hash>", methods=["GET"])
def verify_credential_hash(credential_hash: str):
    """Public, read-only verification endpoint for employers and institutions."""
    result = verify_credential(
        credential_hash=credential_hash,
        verifier_name=request.args.get("verifier_name"),
        verifier_email=request.args.get("verifier_email"),
        verification_method="public_api",
    )
    status = 200 if result.get("valid") else 404 if result.get("reason") == "not_found" else 409
    return jsonify(result), status


@blockchain_bp.route("/credentials/<int:credential_id>/verify", methods=["POST"])
@token_required
def verify_credential_by_id(credential_id: int):
    data = request.get_json(silent=True) or {}
    result = verify_credential(
        credential_id=credential_id,
        verifier_name=data.get("verifier_name") or g.current_user.get("sub"),
        verifier_email=data.get("verifier_email"),
        verification_method="authenticated_api",
        authoritative_record=data.get("authoritative_record"),
    )
    status = 200 if result.get("valid") else 404 if result.get("reason") == "not_found" else 409
    return jsonify(result), status


@blockchain_bp.route("/credentials/<int:credential_id>/revoke", methods=["POST"])
@token_required
@admin_required
def revoke_credential_route(credential_id: int):
    data = request.get_json(silent=True) or {}
    reason = str(data.get("reason") or "").strip()
    if not reason:
        raise ValidationError("Missing required field: reason")
    try:
        credential = revoke_credential(
            credential_id,
            reason=reason,
            revoked_by=g.current_user.get("user_id"),
        )
    except CredentialNotFoundError as exc:
        raise ValidationError(str(exc)) from exc
    log_activity(
        "revoke",
        "blockchain_credentials",
        credential_id=credential_id,
        user=g.current_user.get("sub"),
        details={"reason": reason},
    )
    return jsonify(credential)

# ---- badges ----

@blockchain_bp.route("/badges", methods=["GET"])
@token_required
def list_badges():
    search = request.args.get("search")
    student_id = request.args.get("student_id")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM digital_badges WHERE badge_name LIKE ?",
                (pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

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
            "SELECT * FROM digital_badges" + where + " ORDER BY badge_id DESC LIMIT ? OFFSET ?",
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


@blockchain_bp.route("/badges/<int:badge_id>", methods=["GET"])
@token_required
def get_badge(badge_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM digital_badges WHERE badge_id = ?", (badge_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"badges {badge_id} not found")
    log_activity("view", "digital_badges", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@blockchain_bp.route("/badges", methods=["POST"])
@token_required
def create_badge():
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "badge_name"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO digital_badges
               (student_id, badge_name, description, issuer, issue_date, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data["student_id"], data["badge_name"], data.get("description", ""), data.get("issuer", ""), data.get("issue_date", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM digital_badges WHERE badge_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "digital_badges", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
