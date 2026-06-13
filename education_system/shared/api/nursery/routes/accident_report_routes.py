"""REST API for Nursery Accident / Incident Report.

Exposes CRUD plus summary, status setter and CSV export over the statutory
accident / incident / near-miss register.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

accident_report_bp = Blueprint("nsy_accident_report", __name__, url_prefix="/api/accident-report")


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


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in ("1", "y", "yes", "true", "on")


@accident_report_bp.route("", methods=["GET"])
@accident_report_bp.route("/", methods=["GET"])
@_token_required
def list_records_view():
    from education_system.nursery_system.modules.domain.accident_report import (
        accident_report as data,
    )
    rows = data.list_records(
        record_type=request.args.get("record_type") or None,
        status=request.args.get("status") or None,
        riddor_only=_truthy(request.args.get("riddor_only")),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@accident_report_bp.route("/summary", methods=["GET"])
@_token_required
def summary_view():
    from education_system.nursery_system.modules.domain.accident_report import (
        accident_report as data,
    )
    return jsonify(data.summary())


@accident_report_bp.route("/<record_id>", methods=["GET"])
@_token_required
def get_record_view(record_id):
    from education_system.nursery_system.modules.domain.accident_report import (
        accident_report as data,
    )
    rec = data.get_record(record_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@accident_report_bp.route("", methods=["POST"])
@accident_report_bp.route("/", methods=["POST"])
@_token_required
def create_record_view():
    from education_system.nursery_system.modules.domain.accident_report import (
        accident_report as data,
    )
    try:
        rec = data.create_record(request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec)), 201


@accident_report_bp.route("/<record_id>", methods=["PUT"])
@_token_required
def update_record_view(record_id):
    from education_system.nursery_system.modules.domain.accident_report import (
        accident_report as data,
    )
    if data.get_record(record_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        rec = data.update_record(record_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec))


@accident_report_bp.route("/<record_id>/status", methods=["PUT"])
@_token_required
def set_status_view(record_id):
    from education_system.nursery_system.modules.domain.accident_report import (
        accident_report as data,
    )
    body = request.get_json(silent=True) or {}
    try:
        rec = data.set_status(record_id, body.get("status", ""))
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec))


@accident_report_bp.route("/<record_id>", methods=["DELETE"])
@_token_required
def delete_record_view(record_id):
    from education_system.nursery_system.modules.domain.accident_report import (
        accident_report as data,
    )
    if not data.delete_record(record_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "record_id": record_id})
