"""REST API for Primary Subjects."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

subjects_bp = Blueprint("pri_subjects", __name__, url_prefix="/api/subjects")


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


@subjects_bp.route("", methods=["GET"])
@subjects_bp.route("/", methods=["GET"])
@_token_required
def list_subjects():
    from education_system.systems.primary.domain.academics.subjects import subjects as data

    key_stage = request.args.get("key_stage")
    qualification = request.args.get("qualification")
    active_only = request.args.get("active_only", "").lower() in ("1", "true", "yes")
    try:
        rows = data.list_all(
            key_stage=key_stage,
            qualification=qualification,
            active_only=active_only,
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@subjects_bp.route("/summary", methods=["GET"])
@_token_required
def subjects_summary():
    from education_system.systems.primary.domain.academics.subjects import subjects as data

    return jsonify(data.counts())


@subjects_bp.route("/<int:subject_id>", methods=["GET"])
@_token_required
def get_subject(subject_id: int):
    from education_system.systems.primary.domain.academics.subjects import subjects as data

    rec = data.get(subject_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@subjects_bp.route("", methods=["POST"])
@subjects_bp.route("/", methods=["POST"])
@_token_required
def create_subject():
    from education_system.systems.primary.domain.academics.subjects import subjects as data

    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@subjects_bp.route("/<int:subject_id>", methods=["PUT"])
@_token_required
def update_subject(subject_id: int):
    from education_system.systems.primary.domain.academics.subjects import subjects as data

    if data.get(subject_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update(subject_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@subjects_bp.route("/<int:subject_id>", methods=["DELETE"])
@_token_required
def delete_subject(subject_id: int):
    from education_system.systems.primary.domain.academics.subjects import subjects as data

    try:
        ok = data.delete(subject_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    if not ok:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "subject_id": subject_id})
