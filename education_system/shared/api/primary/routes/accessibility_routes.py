"""REST API for Primary Accessibility Arrangements."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

accessibility_bp = Blueprint("pri_accessibility", __name__, url_prefix="/api/accessibility")


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
    from education_system.primarysch_system.modules.domain.accessibility import (
        accessibility as data,
    )
    return data


@accessibility_bp.route("", methods=["GET"])
@accessibility_bp.route("/", methods=["GET"])
@_token_required
def list_arrangements():
    data = _data()
    args = request.args
    kwargs = {}
    for key in ("pupil_id", "year_group", "arrangement_type", "status", "category"):
        val = args.get(key)
        if val is not None and val != "":
            kwargs[key] = val
    exam_only = args.get("exam_only")
    if exam_only is not None and exam_only != "":
        kwargs["exam_only"] = exam_only.lower() in ("1", "true", "yes")
    try:
        rows = data.list_arrangements(**kwargs)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@accessibility_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    data = _data()
    year_group = request.args.get("year_group") or None
    try:
        return jsonify(data.cohort_summary(year_group=year_group))
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400


@accessibility_bp.route("/<int:arrangement_id>", methods=["GET"])
@_token_required
def get_arrangement(arrangement_id):
    data = _data()
    rec = data.get(arrangement_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@accessibility_bp.route("", methods=["POST"])
@accessibility_bp.route("/", methods=["POST"])
@_token_required
def create_arrangement():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@accessibility_bp.route("/<int:arrangement_id>", methods=["PUT"])
@_token_required
def update_arrangement(arrangement_id):
    data = _data()
    if data.get(arrangement_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update(arrangement_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@accessibility_bp.route("/<int:arrangement_id>", methods=["DELETE"])
@_token_required
def delete_arrangement(arrangement_id):
    data = _data()
    if not data.delete(arrangement_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "arrangement_id": arrangement_id})
