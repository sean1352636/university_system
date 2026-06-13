"""REST API for Nursery Policy Register.

Exposes CRUD over the policy register plus revision log, views and summary.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

policies_bp = Blueprint("nsy_policies", __name__, url_prefix="/api/policies")


def _token_required(view):
    try:
        from education_system.shared.api.auth import token_required
        return token_required(view)
    except Exception:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            expected = os.environ.get("NURSERY_API_TOKEN")
            got = request.headers.get("X-Nursery-Token")
            if expected and got and got == expected:
                g.current_user = {"sub": "service", "role": "service"}
                return view(*args, **kwargs)
            return jsonify({"error": "Unauthorized"}), 401
        return wrapper


def _dump(obj):
    """Serialize a domain dataclass (or list of them) to JSON-safe data."""
    if isinstance(obj, list):
        return [_dump(o) for o in obj]
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj


# ── Policies ───────────────────────────────────────────────────────

@policies_bp.route("", methods=["GET"])
@policies_bp.route("/", methods=["GET"])
@_token_required
def list_policies():
    from education_system.nursery_system.modules.domain.policies import policies as data
    args = request.args
    kwargs = {}
    if args.get("category"):
        kwargs["category"] = args.get("category")
    if args.get("status"):
        kwargs["status"] = args.get("status")
    if args.get("owner"):
        kwargs["owner"] = args.get("owner")
    if args.get("query"):
        kwargs["query"] = args.get("query")
    if args.get("overdue_only", "").lower() in ("1", "true", "yes"):
        kwargs["overdue_only"] = True
    try:
        rows = data.list_policies(**kwargs)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@policies_bp.route("/<int:policy_id>", methods=["GET"])
@_token_required
def get_policy(policy_id: int):
    from education_system.nursery_system.modules.domain.policies import policies as data
    row = data.get_policy(policy_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@policies_bp.route("", methods=["POST"])
@policies_bp.route("/", methods=["POST"])
@_token_required
def create_policy():
    from education_system.nursery_system.modules.domain.policies import policies as data
    try:
        row = data.create_policy(request.get_json(force=True, silent=True) or {})
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@policies_bp.route("/<int:policy_id>", methods=["PUT"])
@_token_required
def update_policy(policy_id: int):
    from education_system.nursery_system.modules.domain.policies import policies as data
    if data.get_policy(policy_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        row = data.update_policy(policy_id, request.get_json(force=True, silent=True) or {})
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@policies_bp.route("/<int:policy_id>", methods=["DELETE"])
@_token_required
def delete_policy(policy_id: int):
    from education_system.nursery_system.modules.domain.policies import policies as data
    if not data.delete_policy(policy_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": policy_id})


# ── Revisions ──────────────────────────────────────────────────────

@policies_bp.route("/<int:policy_id>/revisions", methods=["GET"])
@_token_required
def list_revisions(policy_id: int):
    from education_system.nursery_system.modules.domain.policies import policies as data
    if data.get_policy(policy_id) is None:
        return jsonify({"error": "Not found"}), 404
    rows = data.list_revisions(policy_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@policies_bp.route("/<int:policy_id>/revisions", methods=["POST"])
@_token_required
def add_revision(policy_id: int):
    from education_system.nursery_system.modules.domain.policies import policies as data
    try:
        row = data.add_revision(policy_id, request.get_json(force=True, silent=True) or {})
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@policies_bp.route("/revisions/<int:revision_id>", methods=["DELETE"])
@_token_required
def delete_revision(revision_id: int):
    from education_system.nursery_system.modules.domain.policies import policies as data
    if not data.delete_revision(revision_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": revision_id})


# ── Summary ────────────────────────────────────────────────────────

@policies_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    from education_system.nursery_system.modules.domain.policies import policies as data
    return jsonify(_dump(data.summary()))
