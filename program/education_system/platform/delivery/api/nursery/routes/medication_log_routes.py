"""REST API for Nursery Medication Log.

Exposes CRUD over medication records administered to children, plus a status
setter and a summary of status counts.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

medication_log_bp = Blueprint("nsy_medication_log", __name__, url_prefix="/api/medication-log")


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


@medication_log_bp.route("", methods=["GET"])
@medication_log_bp.route("/", methods=["GET"])
@_token_required
def list_records():
    from education_system.systems.nursery.domain.pastoral.health.medication_log import medication_log as data
    rows = data.list_records(
        administered_date=request.args.get("administered_date"),
        pupil_id=request.args.get("pupil_id"),
        status=request.args.get("status"),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@medication_log_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    from education_system.systems.nursery.domain.pastoral.health.medication_log import medication_log as data
    return jsonify(data.summary())


@medication_log_bp.route("/<record_id>", methods=["GET"])
@_token_required
def get_record(record_id):
    from education_system.systems.nursery.domain.pastoral.health.medication_log import medication_log as data
    rec = data.get_record(record_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@medication_log_bp.route("", methods=["POST"])
@medication_log_bp.route("/", methods=["POST"])
@_token_required
def create_record():
    from education_system.systems.nursery.domain.pastoral.health.medication_log import medication_log as data
    try:
        rec = data.create_record(request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec)), 201


@medication_log_bp.route("/<record_id>", methods=["PUT"])
@_token_required
def update_record(record_id):
    from education_system.systems.nursery.domain.pastoral.health.medication_log import medication_log as data
    if data.get_record(record_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        rec = data.update_record(record_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec))


@medication_log_bp.route("/<record_id>", methods=["DELETE"])
@_token_required
def delete_record(record_id):
    from education_system.systems.nursery.domain.pastoral.health.medication_log import medication_log as data
    if not data.delete_record(record_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "record_id": record_id})


@medication_log_bp.route("/<record_id>/status", methods=["PUT"])
@_token_required
def set_status(record_id):
    from education_system.systems.nursery.domain.pastoral.health.medication_log import medication_log as data
    body = request.get_json(silent=True) or {}
    try:
        rec = data.set_status(record_id, body.get("status", ""))
    except data.ValidationError as e:
        msg = str(e)
        code = 404 if "No medication-log record" in msg else 400
        return jsonify({"error": msg}), code
    return jsonify(_dump(rec))
