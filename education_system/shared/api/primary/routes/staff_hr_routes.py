"""REST API for Primary Staff HR."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

staff_hr_bp = Blueprint("pri_staff_hr", __name__, url_prefix="/api/staff-hr")


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
    from education_system.primarysch_system.modules.domain.staff_hr import (
        staff_hr as data,
    )
    return data


def _body() -> dict:
    return request.get_json(silent=True) or {}


# ── HR records ────────────────────────────────────────────────

@staff_hr_bp.route("", methods=["GET"])
@staff_hr_bp.route("/", methods=["GET"])
@_token_required
def list_records():
    data = _data()
    rows = data.list_records()
    return jsonify({"items": _dump(rows), "count": len(rows)})


@staff_hr_bp.route("/<int:record_id>", methods=["GET"])
@_token_required
def get_record(record_id: int):
    data = _data()
    row = data.get_record(record_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@staff_hr_bp.route("", methods=["POST"])
@staff_hr_bp.route("/", methods=["POST"])
@_token_required
def create_record():
    data = _data()
    try:
        row = data.create_record(_body())
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@staff_hr_bp.route("/<int:record_id>", methods=["PUT"])
@_token_required
def update_record(record_id: int):
    data = _data()
    if data.get_record(record_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        row = data.update_record(record_id, _body())
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@staff_hr_bp.route("/<int:record_id>", methods=["DELETE"])
@_token_required
def delete_record(record_id: int):
    data = _data()
    if not data.delete_record(record_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


# ── HR events ─────────────────────────────────────────────────

@staff_hr_bp.route("/events", methods=["GET"])
@_token_required
def list_events():
    data = _data()
    rows = data.list_events()
    return jsonify({"items": _dump(rows), "count": len(rows)})


@staff_hr_bp.route("/events/<int:event_id>", methods=["GET"])
@_token_required
def get_event(event_id: int):
    data = _data()
    row = data.get_event(event_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@staff_hr_bp.route("/events", methods=["POST"])
@_token_required
def create_event():
    data = _data()
    try:
        row = data.create_event(_body())
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@staff_hr_bp.route("/events/<int:event_id>", methods=["PUT"])
@_token_required
def update_event(event_id: int):
    data = _data()
    if data.get_event(event_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        row = data.update_event(event_id, _body())
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@staff_hr_bp.route("/events/<int:event_id>", methods=["DELETE"])
@_token_required
def delete_event(event_id: int):
    data = _data()
    if not data.delete_event(event_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


# ── Summary ───────────────────────────────────────────────────

@staff_hr_bp.route("/summary", methods=["GET"])
@_token_required
def get_summary():
    data = _data()
    return jsonify(_dump(data.summary()))
