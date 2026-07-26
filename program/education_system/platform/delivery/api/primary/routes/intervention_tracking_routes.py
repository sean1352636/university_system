"""REST API for Primary Intervention Tracking."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

intervention_tracking_bp = Blueprint(
    "pri_intervention_tracking", __name__,
    url_prefix="/api/intervention-tracking",
)


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
    if isinstance(obj, dict):
        return {k: _dump(v) for k, v in obj.items()}
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj


def _data():
    from education_system.systems.primary.domain.assessment.intervention_tracking import (
        intervention_tracking as data,
    )
    return data


# ── Interventions ────────────────────────────────────────────────

@intervention_tracking_bp.route("", methods=["GET"])
@intervention_tracking_bp.route("/", methods=["GET"])
@_token_required
def list_interventions():
    data = _data()
    args = request.args
    subject_id = args.get("subject_id")
    try:
        rows = data.list_interventions(
            year_group=args.get("year_group") or None,
            status=args.get("status") or None,
            intervention_type=args.get("intervention_type") or None,
            pupil_id=args.get("pupil_id") or None,
            subject_id=int(subject_id) if subject_id else None,
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except (TypeError, ValueError):
        return jsonify({"error": "subject_id must be an integer"}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@intervention_tracking_bp.route("/cohort-summary", methods=["GET"])
@_token_required
def cohort_summary():
    data = _data()
    try:
        result = data.cohort_summary(
            year_group=request.args.get("year_group") or None)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(result))


@intervention_tracking_bp.route("/<int:intervention_id>", methods=["GET"])
@_token_required
def get_intervention(intervention_id):
    data = _data()
    rec = data.get(intervention_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@intervention_tracking_bp.route("/<int:intervention_id>/summary",
                                methods=["GET"])
@_token_required
def intervention_summary(intervention_id):
    data = _data()
    try:
        result = data.intervention_summary(intervention_id)
    except data.ValidationError:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(result))


@intervention_tracking_bp.route("", methods=["POST"])
@intervention_tracking_bp.route("/", methods=["POST"])
@_token_required
def create_intervention():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@intervention_tracking_bp.route("/<int:intervention_id>", methods=["PUT"])
@_token_required
def update_intervention(intervention_id):
    data = _data()
    if data.get(intervention_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update(intervention_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@intervention_tracking_bp.route("/<int:intervention_id>", methods=["DELETE"])
@_token_required
def delete_intervention(intervention_id):
    data = _data()
    if not data.delete(intervention_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "intervention_id": intervention_id})


# ── Reviews ──────────────────────────────────────────────────────

@intervention_tracking_bp.route("/<int:intervention_id>/reviews",
                                methods=["GET"])
@_token_required
def list_reviews(intervention_id):
    data = _data()
    if data.get(intervention_id) is None:
        return jsonify({"error": "Not found"}), 404
    rows = data.list_reviews(intervention_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@intervention_tracking_bp.route("/<int:intervention_id>/reviews",
                                methods=["POST"])
@_token_required
def add_review(intervention_id):
    data = _data()
    payload = request.get_json(silent=True) or {}
    payload["intervention_id"] = intervention_id
    try:
        rec = data.add_review(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@intervention_tracking_bp.route("/reviews/<int:review_id>", methods=["GET"])
@_token_required
def get_review(review_id):
    data = _data()
    rec = data.get_review(review_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@intervention_tracking_bp.route("/reviews/<int:review_id>", methods=["DELETE"])
@_token_required
def delete_review(review_id):
    data = _data()
    if not data.delete_review(review_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "review_id": review_id})
