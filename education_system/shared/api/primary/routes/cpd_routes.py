"""REST API for Primary CPD (Continuing Professional Development)."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

cpd_bp = Blueprint("pri_cpd", __name__, url_prefix="/api/cpd")


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
    from education_system.primarysch_system.modules.domain.cpd import cpd as data
    return data


# ── Activities ───────────────────────────────────────────────────────

@cpd_bp.route("/activities", methods=["GET"])
@cpd_bp.route("/activities/", methods=["GET"])
@_token_required
def list_activities():
    data = _data()
    rows = data.list_activities()
    return jsonify({"items": _dump(rows), "count": len(rows)})


@cpd_bp.route("/activities/<int:activity_id>", methods=["GET"])
@_token_required
def get_activity(activity_id: int):
    data = _data()
    obj = data.get_activity(activity_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj))


@cpd_bp.route("/activities", methods=["POST"])
@cpd_bp.route("/activities/", methods=["POST"])
@_token_required
def create_activity():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.create_activity(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj)), 201


@cpd_bp.route("/activities/<int:activity_id>", methods=["PUT"])
@_token_required
def update_activity(activity_id: int):
    data = _data()
    if data.get_activity(activity_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.update_activity(activity_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@cpd_bp.route("/activities/<int:activity_id>", methods=["DELETE"])
@_token_required
def delete_activity(activity_id: int):
    data = _data()
    if not data.delete_activity(activity_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


# ── Records ──────────────────────────────────────────────────────────

@cpd_bp.route("/records", methods=["GET"])
@cpd_bp.route("/records/", methods=["GET"])
@_token_required
def list_records():
    data = _data()
    rows = data.list_records()
    return jsonify({"items": _dump(rows), "count": len(rows)})


@cpd_bp.route("/records/<int:record_id>", methods=["GET"])
@_token_required
def get_record(record_id: int):
    data = _data()
    obj = data.get_record(record_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj))


@cpd_bp.route("/records", methods=["POST"])
@cpd_bp.route("/records/", methods=["POST"])
@_token_required
def create_record():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.create_record(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj)), 201


@cpd_bp.route("/records/<int:record_id>", methods=["PUT"])
@_token_required
def update_record(record_id: int):
    data = _data()
    if data.get_record(record_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.update_record(record_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@cpd_bp.route("/records/<int:record_id>", methods=["DELETE"])
@_token_required
def delete_record(record_id: int):
    data = _data()
    if not data.delete_record(record_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


# ── Summary ──────────────────────────────────────────────────────────

@cpd_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    data = _data()
    return jsonify(_dump(data.summary()))
