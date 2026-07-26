"""REST API for Primary Progress Tracking (reviews & targets)."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

progress_bp = Blueprint("pri_progress", __name__, url_prefix="/api/progress")


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
    from education_system.systems.primary.domain.assessment.progress import (
        progress as data,
    )
    return data


# ── Reviews ──────────────────────────────────────────────────────

@progress_bp.route("", methods=["GET"])
@progress_bp.route("/", methods=["GET"])
@_token_required
def list_reviews():
    data = _data()
    args = request.args
    try:
        rows = data.list_reviews(
            student_id=args.get("student_id"),
            period=args.get("period"),
            academic_year=args.get("academic_year"),
            status=args.get("status"),
            risk_level=args.get("risk_level"),
            reviewer_staff_id=args.get("reviewer_staff_id"),
            active_only=args.get("active_only", "").lower()
            in ("1", "true", "yes"),
        )
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@progress_bp.route("/summary", methods=["GET"])
@_token_required
def review_summary():
    data = _data()
    return jsonify(_dump(data.summary(
        overdue_window_today=request.args.get("today"))))


@progress_bp.route("/<int:review_id>", methods=["GET"])
@_token_required
def get_review(review_id: int):
    data = _data()
    row = data.get_review(review_id)
    if row is None:
        return jsonify({"error": "Review not found"}), 404
    return jsonify(_dump(row))


@progress_bp.route("", methods=["POST"])
@progress_bp.route("/", methods=["POST"])
@_token_required
def create_review():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_review(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row)), 201


@progress_bp.route("/<int:review_id>", methods=["PUT"])
@_token_required
def update_review(review_id: int):
    data = _data()
    if data.get_review(review_id) is None:
        return jsonify({"error": "Review not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_review(review_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row))


@progress_bp.route("/<int:review_id>", methods=["DELETE"])
@_token_required
def delete_review(review_id: int):
    data = _data()
    try:
        ok = data.delete_review(review_id)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    if not ok:
        return jsonify({"error": "Review not found"}), 404
    return jsonify({"deleted": True, "review_id": review_id})


# ── Targets ──────────────────────────────────────────────────────

@progress_bp.route("/targets", methods=["GET"])
@_token_required
def list_targets():
    data = _data()
    args = request.args
    review_id = args.get("review_id", type=int)
    try:
        rows = data.list_targets(
            review_id=review_id,
            student_id=args.get("student_id"),
            status=args.get("status"),
            area=args.get("area"),
            open_only=args.get("open_only", "").lower()
            in ("1", "true", "yes"),
            due_before=args.get("due_before"),
        )
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@progress_bp.route("/targets/<int:target_id>", methods=["GET"])
@_token_required
def get_target(target_id: int):
    data = _data()
    row = data.get_target(target_id)
    if row is None:
        return jsonify({"error": "Target not found"}), 404
    return jsonify(_dump(row))


@progress_bp.route("/<int:review_id>/targets", methods=["POST"])
@_token_required
def add_target(review_id: int):
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        row = data.add_target(review_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row)), 201


@progress_bp.route("/targets/<int:target_id>", methods=["PUT"])
@_token_required
def update_target(target_id: int):
    data = _data()
    if data.get_target(target_id) is None:
        return jsonify({"error": "Target not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_target(target_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row))


@progress_bp.route("/targets/<int:target_id>", methods=["DELETE"])
@_token_required
def delete_target(target_id: int):
    data = _data()
    ok = data.delete_target(target_id)
    if not ok:
        return jsonify({"error": "Target not found"}), 404
    return jsonify({"deleted": True, "target_id": target_id})
