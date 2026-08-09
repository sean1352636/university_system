"""REST API for Primary SEND (Special Educational Needs and Disabilities)."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

send_bp = Blueprint("pri_send", __name__, url_prefix="/api/send")


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
    from education_system.systems.primary.domain.pastoral.send import send as data
    return data


# ── SEND records ────────────────────────────────────────────────

@send_bp.route("", methods=["GET"])
@send_bp.route("/", methods=["GET"])
@_token_required
def list_records():
    data = _data()
    args = request.args
    kwargs = {}
    for key in ("year_group", "academic_year", "provision_stage",
                "primary_need", "status", "pupil_id"):
        val = args.get(key)
        if val:
            kwargs[key] = val
    try:
        rows = data.list_records(**kwargs)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@send_bp.route("/<int:send_id>", methods=["GET"])
@_token_required
def get_record(send_id: int):
    rec = _data().get(send_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@send_bp.route("", methods=["POST"])
@send_bp.route("/", methods=["POST"])
@_token_required
def create_record():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.upsert(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@send_bp.route("/<int:send_id>", methods=["PUT"])
@_token_required
def update_record(send_id: int):
    data = _data()
    existing = data.get(send_id)
    if existing is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    # upsert keys on (pupil_id, academic_year); preserve identity of record.
    payload.setdefault("pupil_id", existing.pupil_id)
    payload.setdefault("academic_year", existing.academic_year)
    try:
        rec = data.upsert(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@send_bp.route("/<int:send_id>", methods=["DELETE"])
@_token_required
def delete_record(send_id: int):
    if not _data().delete(send_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "send_id": send_id})


@send_bp.route("/<int:send_id>/summary", methods=["GET"])
@_token_required
def record_summary(send_id: int):
    data = _data()
    try:
        summary = data.record_summary(send_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(_dump(summary))


@send_bp.route("/cohort-summary", methods=["GET"])
@_token_required
def cohort_summary():
    data = _data()
    args = request.args
    try:
        summary = data.cohort_summary(
            year_group=args.get("year_group") or None,
            academic_year=args.get("academic_year") or None,
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(summary))


@send_bp.route("/overdue-reviews", methods=["GET"])
@_token_required
def overdue_reviews():
    rows = _data().overdue_reviews(request.args.get("today") or None)
    return jsonify({"items": _dump(rows), "count": len(rows)})


# ── Reviews ─────────────────────────────────────────────────────

@send_bp.route("/<int:send_id>/reviews", methods=["GET"])
@_token_required
def list_reviews(send_id: int):
    rows = _data().list_reviews(send_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@send_bp.route("/reviews/<int:review_id>", methods=["GET"])
@_token_required
def get_review(review_id: int):
    rev = _data().get_review(review_id)
    if rev is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rev))


@send_bp.route("/reviews", methods=["POST"])
@_token_required
def create_review():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        rev = data.add_review(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rev)), 201


@send_bp.route("/reviews/<int:review_id>", methods=["DELETE"])
@_token_required
def delete_review(review_id: int):
    if not _data().delete_review(review_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "review_id": review_id})
