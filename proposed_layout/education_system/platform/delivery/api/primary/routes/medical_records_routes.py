"""REST API for Primary Medical Records."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

medical_records_bp = Blueprint("pri_medical_records", __name__, url_prefix="/api/medical-records")


def _token_required(view):
    try:
        from education_system.platform.delivery.api.auth import token_required
        return token_required(view)
    except Exception:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            expected = os.environ.get("PRIMARY_API_TOKEN")
            got = request.headers.get("X-Primary-Token")
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


def _bool_arg(name: str) -> bool:
    return request.args.get(name, "").strip().lower() in ("1", "true", "yes", "on")


@medical_records_bp.route("", methods=["GET"])
@medical_records_bp.route("/", methods=["GET"])
@_token_required
def list_records():
    from education_system.systems.primary.domain.pastoral.health.medical_records import (
        medical_records as data,
    )
    try:
        pairs = data.list_records(
            record_type=request.args.get("record_type") or None,
            severity=request.args.get("severity") or None,
            pupil_id=request.args.get("pupil_id") or None,
            year_group=request.args.get("year_group") or None,
            active_only=_bool_arg("active_only"),
            critical_only=_bool_arg("critical_only"),
            search=request.args.get("search") or None,
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    items = [
        {"record": _dump(rec), "pupil": _dump(pupil)}
        for rec, pupil in pairs
    ]
    return jsonify({"items": items, "count": len(items)})


@medical_records_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    from education_system.systems.primary.domain.pastoral.health.medical_records import (
        medical_records as data,
    )
    return jsonify(data.summary())


@medical_records_bp.route("/pupil/<pupil_id>", methods=["GET"])
@_token_required
def list_for_pupil(pupil_id):
    from education_system.systems.primary.domain.pastoral.health.medical_records import (
        medical_records as data,
    )
    try:
        rows = data.list_for_pupil(pupil_id, active_only=_bool_arg("active_only"))
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@medical_records_bp.route("/<int:record_id>", methods=["GET"])
@_token_required
def get_record(record_id):
    from education_system.systems.primary.domain.pastoral.health.medical_records import (
        medical_records as data,
    )
    rec = data.get(record_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@medical_records_bp.route("", methods=["POST"])
@medical_records_bp.route("/", methods=["POST"])
@_token_required
def create_record():
    from education_system.systems.primary.domain.pastoral.health.medical_records import (
        medical_records as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@medical_records_bp.route("/<int:record_id>", methods=["PUT"])
@_token_required
def update_record(record_id):
    from education_system.systems.primary.domain.pastoral.health.medical_records import (
        medical_records as data,
    )
    if data.get(record_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update(record_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@medical_records_bp.route("/<int:record_id>/toggle-active", methods=["POST"])
@_token_required
def toggle_active(record_id):
    from education_system.systems.primary.domain.pastoral.health.medical_records import (
        medical_records as data,
    )
    try:
        rec = data.toggle_active(record_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(_dump(rec))


@medical_records_bp.route("/<int:record_id>", methods=["DELETE"])
@_token_required
def delete_record(record_id):
    from education_system.systems.primary.domain.pastoral.health.medical_records import (
        medical_records as data,
    )
    if not data.delete(record_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "record_id": record_id})
