"""REST API for Nursery Risk Assessments.

Exposes CRUD plus a summary over the nursery risk_assessments domain module.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

risk_assessments_bp = Blueprint("nsy_risk_assessments", __name__, url_prefix="/api/risk-assessments")


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


@risk_assessments_bp.route("", methods=["GET"])
@risk_assessments_bp.route("/", methods=["GET"])
@_token_required
def list_risk_assessments():
    from education_system.systems.nursery.domain.governance.risk_assessments import risk_assessments as data
    status = request.args.get("status")
    rows = data.list_records(status=status)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@risk_assessments_bp.route("/summary", methods=["GET"])
@_token_required
def risk_assessments_summary():
    from education_system.systems.nursery.domain.governance.risk_assessments import risk_assessments as data
    return jsonify(data.summary())


@risk_assessments_bp.route("/<record_id>", methods=["GET"])
@_token_required
def get_risk_assessment(record_id):
    from education_system.systems.nursery.domain.governance.risk_assessments import risk_assessments as data
    rec = data.get_record(record_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@risk_assessments_bp.route("", methods=["POST"])
@risk_assessments_bp.route("/", methods=["POST"])
@_token_required
def create_risk_assessment():
    from education_system.systems.nursery.domain.governance.risk_assessments import risk_assessments as data
    try:
        rec = data.create_record(request.get_json(silent=True) or {})
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@risk_assessments_bp.route("/<record_id>", methods=["PUT"])
@_token_required
def update_risk_assessment(record_id):
    from education_system.systems.nursery.domain.governance.risk_assessments import risk_assessments as data
    if data.get_record(record_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        rec = data.update_record(record_id, request.get_json(silent=True) or {})
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@risk_assessments_bp.route("/<record_id>", methods=["DELETE"])
@_token_required
def delete_risk_assessment(record_id):
    from education_system.systems.nursery.domain.governance.risk_assessments import risk_assessments as data
    if not data.delete_record(record_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": record_id})
