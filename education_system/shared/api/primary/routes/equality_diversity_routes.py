"""REST API for Primary Equality & Diversity."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

equality_diversity_bp = Blueprint("pri_equality_diversity", __name__, url_prefix="/api/equality-diversity")


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
    from education_system.primarysch_system.modules.domain.equality_diversity import (
        equality_diversity as data,
    )
    return data


@equality_diversity_bp.route("", methods=["GET"])
@equality_diversity_bp.route("/", methods=["GET"])
@_token_required
def list_incidents():
    data = _data()
    args = request.args
    kwargs = {}
    for key in ("incident_type", "characteristic", "status",
                "reporter_like", "subject_like", "date_from", "date_to"):
        val = args.get(key)
        if val:
            kwargs[key] = val
    for key in ("severity", "severity_min"):
        val = args.get(key, type=int)
        if val is not None:
            kwargs[key] = val
    for key in ("open_only", "substantiated_only", "escalated_only"):
        if args.get(key, "").lower() in ("1", "true", "yes"):
            kwargs[key] = True
    rows = data.list_incidents(**kwargs)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@equality_diversity_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    data = _data()
    return jsonify(_dump(data.summary()))


@equality_diversity_bp.route("/<int:incident_id>", methods=["GET"])
@_token_required
def get_incident(incident_id: int):
    data = _data()
    row = data.get_incident(incident_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@equality_diversity_bp.route("", methods=["POST"])
@equality_diversity_bp.route("/", methods=["POST"])
@_token_required
def create_incident():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_incident(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@equality_diversity_bp.route("/<int:incident_id>", methods=["PUT"])
@_token_required
def update_incident(incident_id: int):
    data = _data()
    if data.get_incident(incident_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_incident(incident_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@equality_diversity_bp.route("/<int:incident_id>", methods=["DELETE"])
@_token_required
def delete_incident(incident_id: int):
    data = _data()
    if not data.delete_incident(incident_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "incident_id": incident_id})
