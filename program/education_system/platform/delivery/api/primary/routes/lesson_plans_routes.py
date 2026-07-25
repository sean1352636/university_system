"""REST API for Primary Lesson Plans."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

lesson_plans_bp = Blueprint("pri_lesson_plans", __name__, url_prefix="/api/lesson-plans")


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
    from education_system.systems.primary.domain.academics.lesson_plans import (
        lesson_plans as data,
    )
    return data


@lesson_plans_bp.route("", methods=["GET"])
@lesson_plans_bp.route("/", methods=["GET"])
@_token_required
def list_lesson_plans():
    data = _data()
    args = request.args
    try:
        subject_id = args.get("subject_id", type=int)
        rows = data.list_plans(
            year_group=args.get("year_group"),
            subject_id=subject_id,
            teacher=args.get("teacher"),
            status=args.get("status"),
            date_from=args.get("date_from"),
            date_to=args.get("date_to"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@lesson_plans_bp.route("/summary", methods=["GET"])
@_token_required
def lesson_plans_summary():
    data = _data()
    return jsonify(data.status_counts())


@lesson_plans_bp.route("/<int:plan_id>", methods=["GET"])
@_token_required
def get_lesson_plan(plan_id):
    data = _data()
    rec = data.get(plan_id)
    if rec is None:
        return jsonify({"error": f"No lesson plan #{plan_id}"}), 404
    return jsonify(_dump(rec))


@lesson_plans_bp.route("", methods=["POST"])
@lesson_plans_bp.route("/", methods=["POST"])
@_token_required
def create_lesson_plan():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@lesson_plans_bp.route("/<int:plan_id>", methods=["PUT"])
@_token_required
def update_lesson_plan(plan_id):
    data = _data()
    if data.get(plan_id) is None:
        return jsonify({"error": f"No lesson plan #{plan_id}"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update(plan_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@lesson_plans_bp.route("/<int:plan_id>", methods=["DELETE"])
@_token_required
def delete_lesson_plan(plan_id):
    data = _data()
    if not data.delete(plan_id):
        return jsonify({"error": f"No lesson plan #{plan_id}"}), 404
    return jsonify({"deleted": True, "plan_id": plan_id})
