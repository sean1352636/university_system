"""REST API for Nursery Nappy / Toileting Log.

Exposes CRUD over toileting/nappy-change records for children in the setting.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

toileting_log_bp = Blueprint("nsy_toileting_log", __name__, url_prefix="/api/toileting-log")


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


@toileting_log_bp.route("", methods=["GET"])
@toileting_log_bp.route("/", methods=["GET"])
@_token_required
def list_records():
    from education_system.nursery_system.modules.domain.toileting_log import (
        toileting_log as data,
    )
    rows = data.list_records(
        log_date=request.args.get("log_date"),
        pupil_id=request.args.get("pupil_id"),
        type=request.args.get("type"),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@toileting_log_bp.route("/<record_id>", methods=["GET"])
@_token_required
def get_record(record_id):
    from education_system.nursery_system.modules.domain.toileting_log import (
        toileting_log as data,
    )
    rec = data.get_record(record_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@toileting_log_bp.route("", methods=["POST"])
@toileting_log_bp.route("/", methods=["POST"])
@_token_required
def create_record():
    from education_system.nursery_system.modules.domain.toileting_log import (
        toileting_log as data,
    )
    try:
        rec = data.create_record(request.get_json(force=True, silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec)), 201


@toileting_log_bp.route("/<record_id>", methods=["PUT"])
@_token_required
def update_record(record_id):
    from education_system.nursery_system.modules.domain.toileting_log import (
        toileting_log as data,
    )
    if data.get_record(record_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        rec = data.update_record(record_id, request.get_json(force=True, silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec))


@toileting_log_bp.route("/<record_id>", methods=["DELETE"])
@_token_required
def delete_record(record_id):
    from education_system.nursery_system.modules.domain.toileting_log import (
        toileting_log as data,
    )
    if not data.delete_record(record_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "record_id": record_id})


@toileting_log_bp.route("/choices/pupils", methods=["GET"])
@_token_required
def list_pupil_choices():
    from education_system.nursery_system.modules.domain.toileting_log import (
        toileting_log as data,
    )
    rows = data.list_pupil_choices()
    return jsonify({"items": [{"id": i, "label": lbl} for i, lbl in rows], "count": len(rows)})


@toileting_log_bp.route("/choices/staff", methods=["GET"])
@_token_required
def list_staff_choices():
    from education_system.nursery_system.modules.domain.toileting_log import (
        toileting_log as data,
    )
    rows = data.list_staff_choices()
    return jsonify({"items": [{"id": i, "label": lbl} for i, lbl in rows], "count": len(rows)})
