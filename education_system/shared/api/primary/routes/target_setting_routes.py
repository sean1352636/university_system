"""REST API for Primary Target Setting."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

target_setting_bp = Blueprint("pri_target_setting", __name__, url_prefix="/api/target-setting")


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
    if isinstance(obj, tuple):
        return [_dump(o) for o in obj]
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj


def _data():
    from education_system.primarysch_system.modules.domain.target_setting import (
        target_setting as data,
    )
    return data


@target_setting_bp.route("", methods=["GET"])
@target_setting_bp.route("/", methods=["GET"])
@_token_required
def list_targets():
    data = _data()
    kwargs = {}
    for key in ("academic_year", "subject", "status", "pupil_id", "year_group"):
        val = request.args.get(key)
        if val:
            kwargs[key] = val
    try:
        rows = data.list_targets(**kwargs)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    items = [{"target": _dump(t), "pupil": _dump(p)} for t, p in rows]
    return jsonify({"items": items, "count": len(items)})


@target_setting_bp.route("/<int:target_id>", methods=["GET"])
@_token_required
def get_target(target_id: int):
    data = _data()
    rec = data.get(target_id)
    if rec is None:
        return jsonify({"error": f"No target #{target_id}"}), 404
    return jsonify(_dump(rec))


@target_setting_bp.route("", methods=["POST"])
@target_setting_bp.route("/", methods=["POST"])
@_token_required
def create_target():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@target_setting_bp.route("/<int:target_id>", methods=["PUT"])
@_token_required
def update_target(target_id: int):
    data = _data()
    payload = request.get_json(silent=True) or {}
    if data.get(target_id) is None:
        return jsonify({"error": f"No target #{target_id}"}), 404
    try:
        rec = data.update(target_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@target_setting_bp.route("/<int:target_id>/status", methods=["PUT"])
@_token_required
def set_target_status(target_id: int):
    data = _data()
    payload = request.get_json(silent=True) or {}
    if data.get(target_id) is None:
        return jsonify({"error": f"No target #{target_id}"}), 404
    new_status = (payload.get("status") or "").strip()
    try:
        rec = data.set_status(target_id, new_status)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@target_setting_bp.route("/<int:target_id>", methods=["DELETE"])
@_token_required
def delete_target(target_id: int):
    data = _data()
    if not data.delete(target_id):
        return jsonify({"error": f"No target #{target_id}"}), 404
    return jsonify({"deleted": True, "target_id": target_id})


@target_setting_bp.route("/pupil/<pupil_id>", methods=["GET"])
@_token_required
def list_for_pupil(pupil_id: str):
    data = _data()
    try:
        rows = data.list_for_pupil(pupil_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@target_setting_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    data = _data()
    kwargs = {}
    for key in ("academic_year", "subject"):
        val = request.args.get(key)
        if val:
            kwargs[key] = val
    return jsonify(data.summary(**kwargs))


@target_setting_bp.route("/years", methods=["GET"])
@_token_required
def known_years():
    data = _data()
    rows = data.known_years()
    return jsonify({"items": _dump(rows), "count": len(rows)})


@target_setting_bp.route("/subjects", methods=["GET"])
@_token_required
def known_subjects():
    data = _data()
    rows = data.known_subjects()
    return jsonify({"items": _dump(rows), "count": len(rows)})
