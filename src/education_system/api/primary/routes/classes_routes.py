"""REST API for Primary Classes."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

classes_bp = Blueprint("pri_classes", __name__, url_prefix="/api/classes")


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


@classes_bp.route("", methods=["GET"])
@classes_bp.route("/", methods=["GET"])
@_token_required
def list_classes():
    from education_system.systems.primary.domain.academics.classes import classes as data
    year_group = request.args.get("year_group") or None
    active_only = request.args.get("active_only", "").lower() in ("1", "true", "yes")
    try:
        rows = data.list_all(year_group=year_group, active_only=active_only)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@classes_bp.route("/summary", methods=["GET"])
@_token_required
def summary_classes():
    from education_system.systems.primary.domain.academics.classes import classes as data
    return jsonify(data.counts())


@classes_bp.route("/<int:class_id>", methods=["GET"])
@_token_required
def get_class(class_id: int):
    from education_system.systems.primary.domain.academics.classes import classes as data
    rec = data.get(class_id)
    if rec is None:
        return jsonify({"error": f"No class #{class_id}"}), 404
    return jsonify(_dump(rec))


@classes_bp.route("/<int:class_id>/pupils", methods=["GET"])
@_token_required
def class_pupils(class_id: int):
    from education_system.systems.primary.domain.academics.classes import classes as data
    rec = data.get(class_id)
    if rec is None:
        return jsonify({"error": f"No class #{class_id}"}), 404
    rows = data.pupils_in_class(rec.name)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@classes_bp.route("", methods=["POST"])
@classes_bp.route("/", methods=["POST"])
@_token_required
def create_class():
    from education_system.systems.primary.domain.academics.classes import classes as data
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@classes_bp.route("/<int:class_id>", methods=["PUT"])
@_token_required
def update_class(class_id: int):
    from education_system.systems.primary.domain.academics.classes import classes as data
    if data.get(class_id) is None:
        return jsonify({"error": f"No class #{class_id}"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update(class_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@classes_bp.route("/<int:class_id>/toggle-active", methods=["POST"])
@_token_required
def toggle_class_active(class_id: int):
    from education_system.systems.primary.domain.academics.classes import classes as data
    if data.get(class_id) is None:
        return jsonify({"error": f"No class #{class_id}"}), 404
    try:
        rec = data.toggle_active(class_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@classes_bp.route("/<int:class_id>", methods=["DELETE"])
@_token_required
def delete_class(class_id: int):
    from education_system.systems.primary.domain.academics.classes import classes as data
    try:
        ok = data.delete(class_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    if not ok:
        return jsonify({"error": f"No class #{class_id}"}), 404
    return jsonify({"deleted": True, "class_id": class_id})
