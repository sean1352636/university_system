"""REST API for Nursery Funded Hours Claims.

Exposes CRUD plus summary and status-setter over local-authority funded-hours claims.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

funding_claims_bp = Blueprint("nsy_funding_claims", __name__, url_prefix="/api/funding-claims")


def _token_required(view):
    try:
        from education_system.platform.delivery.api.auth import token_required
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


@funding_claims_bp.route("", methods=["GET"])
@funding_claims_bp.route("/", methods=["GET"])
@_token_required
def list_funding_claims():
    from education_system.systems.nursery.domain.finance.funding_claims import (
        funding_claims as data,
    )
    status = request.args.get("status") or None
    rows = data.list_claims(status=status)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@funding_claims_bp.route("/summary", methods=["GET"])
@_token_required
def funding_claims_summary():
    from education_system.systems.nursery.domain.finance.funding_claims import (
        funding_claims as data,
    )
    return jsonify(data.summary())


@funding_claims_bp.route("/<claim_id>", methods=["GET"])
@_token_required
def get_funding_claim(claim_id):
    from education_system.systems.nursery.domain.finance.funding_claims import (
        funding_claims as data,
    )
    claim = data.get_claim(claim_id)
    if claim is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(claim))


@funding_claims_bp.route("", methods=["POST"])
@funding_claims_bp.route("/", methods=["POST"])
@_token_required
def create_funding_claim():
    from education_system.systems.nursery.domain.finance.funding_claims import (
        funding_claims as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        claim = data.create_claim(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(claim)), 201


@funding_claims_bp.route("/<claim_id>", methods=["PUT"])
@_token_required
def update_funding_claim(claim_id):
    from education_system.systems.nursery.domain.finance.funding_claims import (
        funding_claims as data,
    )
    if data.get_claim(claim_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        claim = data.update_claim(claim_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(claim))


@funding_claims_bp.route("/<claim_id>/status", methods=["PUT"])
@_token_required
def set_funding_claim_status(claim_id):
    from education_system.systems.nursery.domain.finance.funding_claims import (
        funding_claims as data,
    )
    if data.get_claim(claim_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        claim = data.set_status(claim_id, payload.get("status"))
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(claim))


@funding_claims_bp.route("/<claim_id>", methods=["DELETE"])
@_token_required
def delete_funding_claim(claim_id):
    from education_system.systems.nursery.domain.finance.funding_claims import (
        funding_claims as data,
    )
    if not data.delete_claim(claim_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "claim_id": claim_id})
