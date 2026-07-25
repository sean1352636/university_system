"""REST API for Secondary School governance."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

governance_bp = Blueprint("sec_governance", __name__, url_prefix="/api/governance")


def _token_required(view):
    try:
        from education_system.platform.delivery.api.auth import token_required
        return token_required(view)
    except Exception:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            expected = os.environ.get("SCHOOL_API_TOKEN")
            got = request.headers.get("X-School-Token")
            if expected and got and got == expected:
                g.current_user = {"sub": "service", "role": "service"}
                return view(*args, **kwargs)
            return jsonify({"error": "Unauthorized"}), 401
        return wrapper


def _dump(obj):
    if isinstance(obj, list):
        return [_dump(o) for o in obj]
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj


def _body() -> dict:
    return request.get_json(silent=True) or {}


# ── Policies ───────────────────────────────────────────────────────

@governance_bp.route("/policies", methods=["GET"])
@_token_required
def list_policies():
    from education_system.systems.secondary.domain.governance.policies import (
        policies as data,
    )
    rows = data.list_policies(
        category=request.args.get("category"),
        status=request.args.get("status"),
        owner=request.args.get("owner"),
        overdue_only=request.args.get("overdue_only", "").lower() in ("1", "true", "yes"),
        query=request.args.get("query"),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@governance_bp.route("/policies/<int:policy_id>", methods=["GET"])
@_token_required
def get_policy(policy_id: int):
    from education_system.systems.secondary.domain.governance.policies import (
        policies as data,
    )
    row = data.get_policy(policy_id)
    if row is None:
        return jsonify({"error": f"No policy #{policy_id}"}), 404
    return jsonify(_dump(row))


@governance_bp.route("/policies", methods=["POST"])
@_token_required
def create_policy():
    from education_system.systems.secondary.domain.governance.policies import (
        policies as data,
    )
    try:
        row = data.create_policy(_body())
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@governance_bp.route("/policies/<int:policy_id>", methods=["PUT"])
@_token_required
def update_policy(policy_id: int):
    from education_system.systems.secondary.domain.governance.policies import (
        policies as data,
    )
    if data.get_policy(policy_id) is None:
        return jsonify({"error": f"No policy #{policy_id}"}), 404
    try:
        row = data.update_policy(policy_id, _body())
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@governance_bp.route("/policies/<int:policy_id>", methods=["DELETE"])
@_token_required
def delete_policy(policy_id: int):
    from education_system.systems.secondary.domain.governance.policies import (
        policies as data,
    )
    if not data.delete_policy(policy_id):
        return jsonify({"error": f"No policy #{policy_id}"}), 404
    return jsonify({"deleted": policy_id})


# ── Risk management ────────────────────────────────────────────────

@governance_bp.route("/risks", methods=["GET"])
@_token_required
def list_risks():
    from education_system.systems.secondary.domain.governance.risk_management import (
        risk_management as data,
    )
    min_score = request.args.get("min_score")
    try:
        rows = data.list_risks(
            status=request.args.get("status"),
            category=request.args.get("category"),
            owner=request.args.get("owner"),
            open_only=request.args.get("open_only", "").lower() in ("1", "true", "yes"),
            review_due_only=request.args.get("review_due_only", "").lower() in ("1", "true", "yes"),
            min_score=int(min_score) if min_score else None,
            search=request.args.get("search"),
        )
    except (ValueError, data.ValidationError) as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@governance_bp.route("/risks/<int:risk_id>", methods=["GET"])
@_token_required
def get_risk(risk_id: int):
    from education_system.systems.secondary.domain.governance.risk_management import (
        risk_management as data,
    )
    row = data.get_risk(risk_id)
    if row is None:
        return jsonify({"error": f"No risk #{risk_id}"}), 404
    return jsonify(_dump(row))


@governance_bp.route("/risks", methods=["POST"])
@_token_required
def create_risk():
    from education_system.systems.secondary.domain.governance.risk_management import (
        risk_management as data,
    )
    try:
        row = data.create_risk(_body())
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@governance_bp.route("/risks/<int:risk_id>", methods=["PUT"])
@_token_required
def update_risk(risk_id: int):
    from education_system.systems.secondary.domain.governance.risk_management import (
        risk_management as data,
    )
    if data.get_risk(risk_id) is None:
        return jsonify({"error": f"No risk #{risk_id}"}), 404
    try:
        row = data.update_risk(risk_id, _body())
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@governance_bp.route("/risks/<int:risk_id>", methods=["DELETE"])
@_token_required
def delete_risk(risk_id: int):
    from education_system.systems.secondary.domain.governance.risk_management import (
        risk_management as data,
    )
    if not data.delete_risk(risk_id):
        return jsonify({"error": f"No risk #{risk_id}"}), 404
    return jsonify({"deleted": risk_id})


@governance_bp.route("/risks/overview", methods=["GET"])
@_token_required
def risks_overview():
    from education_system.systems.secondary.domain.governance.risk_management import (
        risk_management as data,
    )
    return jsonify(_dump(data.overview()))


# ── Compliance ─────────────────────────────────────────────────────

@governance_bp.route("/compliance", methods=["GET"])
@_token_required
def list_compliance():
    from education_system.systems.secondary.domain.governance.compliance import (
        compliance as data,
    )
    try:
        rows = data.list_items(
            category=request.args.get("category"),
            status=request.args.get("status"),
            owner=request.args.get("owner"),
            overdue_only=request.args.get("overdue_only", "").lower() in ("1", "true", "yes"),
            query=request.args.get("query"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@governance_bp.route("/compliance/<int:item_id>", methods=["GET"])
@_token_required
def get_compliance(item_id: int):
    from education_system.systems.secondary.domain.governance.compliance import (
        compliance as data,
    )
    row = data.get_item(item_id)
    if row is None:
        return jsonify({"error": f"No compliance item #{item_id}"}), 404
    return jsonify(_dump(row))


@governance_bp.route("/compliance", methods=["POST"])
@_token_required
def create_compliance():
    from education_system.systems.secondary.domain.governance.compliance import (
        compliance as data,
    )
    try:
        row = data.create_item(_body())
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@governance_bp.route("/compliance/<int:item_id>", methods=["PUT"])
@_token_required
def update_compliance(item_id: int):
    from education_system.systems.secondary.domain.governance.compliance import (
        compliance as data,
    )
    if data.get_item(item_id) is None:
        return jsonify({"error": f"No compliance item #{item_id}"}), 404
    try:
        row = data.update_item(item_id, _body())
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@governance_bp.route("/compliance/<int:item_id>", methods=["DELETE"])
@_token_required
def delete_compliance(item_id: int):
    from education_system.systems.secondary.domain.governance.compliance import (
        compliance as data,
    )
    if not data.delete_item(item_id):
        return jsonify({"error": f"No compliance item #{item_id}"}), 404
    return jsonify({"deleted": item_id})
