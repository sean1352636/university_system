"""REST API for Primary Pupil Support (support plans & reviews)."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

pupil_support_bp = Blueprint("pri_pupil_support", __name__, url_prefix="/api/pupil-support")


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
    from education_system.systems.primary.domain.pastoral.pupil_support import (
        pupil_support as data,
    )
    return data


# ── Support plans ───────────────────────────────────────────────

@pupil_support_bp.route("", methods=["GET"])
@pupil_support_bp.route("/", methods=["GET"])
@_token_required
def list_plans():
    data = _data()
    args = request.args
    try:
        rows = data.list_plans(
            pupil_id=args.get("pupil_id"),
            year_group=args.get("year_group"),
            academic_year=args.get("academic_year"),
            plan_type=args.get("plan_type"),
            status=args.get("status"),
            priority=args.get("priority"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@pupil_support_bp.route("/<int:plan_id>", methods=["GET"])
@_token_required
def get_plan(plan_id: int):
    rec = _data().get_plan(plan_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@pupil_support_bp.route("", methods=["POST"])
@pupil_support_bp.route("/", methods=["POST"])
@_token_required
def create_plan():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create_plan(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@pupil_support_bp.route("/<int:plan_id>", methods=["PUT"])
@_token_required
def update_plan(plan_id: int):
    data = _data()
    if data.get_plan(plan_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update_plan(plan_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@pupil_support_bp.route("/<int:plan_id>", methods=["DELETE"])
@_token_required
def delete_plan(plan_id: int):
    if not _data().delete_plan(plan_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


@pupil_support_bp.route("/<int:plan_id>/summary", methods=["GET"])
@_token_required
def plan_summary(plan_id: int):
    data = _data()
    try:
        result = data.plan_summary(plan_id)
    except data.ValidationError:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(result))


# ── Reviews ─────────────────────────────────────────────────────

@pupil_support_bp.route("/<int:plan_id>/reviews", methods=["GET"])
@_token_required
def list_reviews(plan_id: int):
    data = _data()
    if data.get_plan(plan_id) is None:
        return jsonify({"error": "Not found"}), 404
    rows = data.list_reviews(plan_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@pupil_support_bp.route("/reviews/<int:review_id>", methods=["GET"])
@_token_required
def get_review(review_id: int):
    rec = _data().get_review(review_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@pupil_support_bp.route("/reviews", methods=["POST"])
@_token_required
def add_review():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.add_review(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@pupil_support_bp.route("/reviews/<int:review_id>", methods=["DELETE"])
@_token_required
def delete_review(review_id: int):
    if not _data().delete_review(review_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


# ── Cohort & overdue (read-only) ────────────────────────────────

@pupil_support_bp.route("/cohort-summary", methods=["GET"])
@_token_required
def cohort_summary():
    args = request.args
    result = _data().cohort_summary(
        year_group=args.get("year_group"),
        academic_year=args.get("academic_year"),
    )
    return jsonify(_dump(result))


@pupil_support_bp.route("/overdue-reviews", methods=["GET"])
@_token_required
def overdue_reviews():
    rows = _data().overdue_reviews(today=request.args.get("today"))
    return jsonify({"items": _dump(rows), "count": len(rows)})
