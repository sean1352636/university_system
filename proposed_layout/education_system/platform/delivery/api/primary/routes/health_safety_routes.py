"""REST API for Primary Health & Safety (incident / hazard register)."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

health_safety_bp = Blueprint("pri_health_safety", __name__, url_prefix="/api/health-safety")


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


def _data():
    from education_system.systems.primary.domain.governance.health_safety import (
        health_safety as data,
    )
    return data


def _body() -> dict:
    return request.get_json(silent=True) or {}


# ── Incidents ──────────────────────────────────────────────────────

@health_safety_bp.route("", methods=["GET"])
@health_safety_bp.route("/", methods=["GET"])
@_token_required
def list_incidents():
    data = _data()
    args = request.args
    rows = data.list_incidents(
        status=args.get("status"),
        severity=args.get("severity"),
        category=args.get("category"),
        incident_type=args.get("incident_type"),
        affected_party=args.get("affected_party"),
        riddor_only=args.get("riddor_only", "").lower() in ("1", "true", "yes"),
        open_only=args.get("open_only", "").lower() in ("1", "true", "yes"),
        date_from=args.get("date_from"),
        date_to=args.get("date_to"),
        search=args.get("search"),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@health_safety_bp.route("/<int:incident_id>", methods=["GET"])
@_token_required
def get_incident(incident_id: int):
    data = _data()
    row = data.get_incident(incident_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@health_safety_bp.route("", methods=["POST"])
@health_safety_bp.route("/", methods=["POST"])
@_token_required
def create_incident():
    data = _data()
    try:
        row = data.create_incident(_body())
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@health_safety_bp.route("/<int:incident_id>", methods=["PUT"])
@_token_required
def update_incident(incident_id: int):
    data = _data()
    if data.get_incident(incident_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        row = data.update_incident(incident_id, _body())
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@health_safety_bp.route("/<int:incident_id>/status", methods=["PUT"])
@_token_required
def set_status(incident_id: int):
    data = _data()
    if data.get_incident(incident_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        row = data.set_status(incident_id, _body().get("status"))
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@health_safety_bp.route("/<int:incident_id>", methods=["DELETE"])
@_token_required
def delete_incident(incident_id: int):
    data = _data()
    if not data.delete_incident(incident_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


# ── Actions (child of incident) ────────────────────────────────────

@health_safety_bp.route("/<int:incident_id>/actions", methods=["GET"])
@_token_required
def list_actions(incident_id: int):
    data = _data()
    if data.get_incident(incident_id) is None:
        return jsonify({"error": "Not found"}), 404
    args = request.args
    rows = data.list_actions(
        incident_id=incident_id,
        status=args.get("status"),
        overdue_only=args.get("overdue_only", "").lower() in ("1", "true", "yes"),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@health_safety_bp.route("/<int:incident_id>/actions", methods=["POST"])
@_token_required
def add_action(incident_id: int):
    data = _data()
    try:
        row = data.add_action(incident_id, _body())
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@health_safety_bp.route("/actions/<int:action_id>", methods=["GET"])
@_token_required
def get_action(action_id: int):
    data = _data()
    row = data.get_action(action_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@health_safety_bp.route("/actions/<int:action_id>", methods=["PUT"])
@_token_required
def update_action(action_id: int):
    data = _data()
    if data.get_action(action_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        row = data.update_action(action_id, _body())
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@health_safety_bp.route("/actions/<int:action_id>/complete", methods=["PUT"])
@_token_required
def complete_action(action_id: int):
    data = _data()
    if data.get_action(action_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        row = data.complete_action(
            action_id, completed_on=_body().get("completed_on"))
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@health_safety_bp.route("/actions/<int:action_id>", methods=["DELETE"])
@_token_required
def delete_action(action_id: int):
    data = _data()
    if not data.delete_action(action_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


# ── Summary ────────────────────────────────────────────────────────

@health_safety_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    data = _data()
    return jsonify(_dump(data.summary()))
