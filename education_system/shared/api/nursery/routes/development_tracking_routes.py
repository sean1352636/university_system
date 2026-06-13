"""REST API for Nursery Development Tracking.

Exposes CRUD over EYFS development assessment records (DevRecord), keyed by a
string record_id (e.g. ``NDT001``), with optional filtering by pupil_id.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

development_tracking_bp = Blueprint(
    "nsy_development_tracking", __name__, url_prefix="/api/development-tracking"
)


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


@development_tracking_bp.route("", methods=["GET"])
@development_tracking_bp.route("/", methods=["GET"])
@_token_required
def list_development_records():
    from education_system.nursery_system.modules.domain.development_tracking import (
        development_tracking as data,
    )
    pupil_id = request.args.get("pupil_id") or None
    rows = data.list_records(pupil_id=pupil_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@development_tracking_bp.route("/<record_id>", methods=["GET"])
@_token_required
def get_development_record(record_id):
    from education_system.nursery_system.modules.domain.development_tracking import (
        development_tracking as data,
    )
    rec = data.get_record(record_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@development_tracking_bp.route("", methods=["POST"])
@development_tracking_bp.route("/", methods=["POST"])
@_token_required
def create_development_record():
    from education_system.nursery_system.modules.domain.development_tracking import (
        development_tracking as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create_record(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@development_tracking_bp.route("/<record_id>", methods=["PUT"])
@_token_required
def update_development_record(record_id):
    from education_system.nursery_system.modules.domain.development_tracking import (
        development_tracking as data,
    )
    if data.get_record(record_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update_record(record_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@development_tracking_bp.route("/<record_id>", methods=["DELETE"])
@_token_required
def delete_development_record(record_id):
    from education_system.nursery_system.modules.domain.development_tracking import (
        development_tracking as data,
    )
    if not data.delete_record(record_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "record_id": record_id})
