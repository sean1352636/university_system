"""REST API for Primary First Aid."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

first_aid_bp = Blueprint("pri_first_aid", __name__, url_prefix="/api/first-aid")


def _token_required(view):
    try:
        from education_system.shared.api.auth import token_required
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


def _data():
    from education_system.primarysch_system.modules.domain.first_aid import (
        first_aid as data,
    )
    return data


@first_aid_bp.route("", methods=["GET"])
@first_aid_bp.route("/", methods=["GET"])
@_token_required
def list_incidents():
    data = _data()
    args = request.args
    try:
        rows = data.list_incidents(
            pupil_id=args.get("pupil_id"),
            from_date=args.get("from_date"),
            to_date=args.get("to_date"),
            severity=args.get("severity"),
            injury_type=args.get("injury_type"),
            riddor_only=args.get("riddor_only", "").lower() in ("1", "true", "yes"),
            hospital_only=args.get("hospital_only", "").lower() in ("1", "true", "yes"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@first_aid_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    data = _data()
    args = request.args
    try:
        result = data.cohort_summary(
            from_date=args.get("from_date"),
            to_date=args.get("to_date"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)


@first_aid_bp.route("/<int:incident_id>", methods=["GET"])
@_token_required
def get_incident(incident_id):
    data = _data()
    rec = data.get(incident_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@first_aid_bp.route("", methods=["POST"])
@first_aid_bp.route("/", methods=["POST"])
@_token_required
def create_incident():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@first_aid_bp.route("/<int:incident_id>", methods=["PUT"])
@_token_required
def update_incident(incident_id):
    data = _data()
    if data.get(incident_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update(incident_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@first_aid_bp.route("/<int:incident_id>", methods=["DELETE"])
@_token_required
def delete_incident(incident_id):
    data = _data()
    if not data.delete(incident_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})
