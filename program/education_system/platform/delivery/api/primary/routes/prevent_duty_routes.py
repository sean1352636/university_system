"""REST API for Primary Prevent Duty (radicalisation referrals)."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

prevent_duty_bp = Blueprint("pri_prevent_duty", __name__, url_prefix="/api/prevent-duty")


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
    from education_system.systems.primary.domain.safeguarding.prevent_duty import (
        prevent_duty as data,
    )
    return data


@prevent_duty_bp.route("", methods=["GET"])
@prevent_duty_bp.route("/", methods=["GET"])
@_token_required
def list_referrals():
    data = _data()
    args = request.args
    kwargs = {}
    for key in ("pupil_id", "status", "risk_level", "concern_type",
                "pathway", "from_date", "to_date"):
        val = args.get(key)
        if val:
            kwargs[key] = val
    if args.get("open_only", "").lower() in ("1", "true", "yes"):
        kwargs["open_only"] = True
    try:
        rows = data.list_referrals(**kwargs)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@prevent_duty_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    data = _data()
    args = request.args
    kwargs = {}
    if args.get("from_date"):
        kwargs["from_date"] = args.get("from_date")
    if args.get("to_date"):
        kwargs["to_date"] = args.get("to_date")
    try:
        result = data.cohort_summary(**kwargs)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)


@prevent_duty_bp.route("/<int:referral_id>", methods=["GET"])
@_token_required
def get_referral(referral_id: int):
    data = _data()
    rec = data.get(referral_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@prevent_duty_bp.route("", methods=["POST"])
@prevent_duty_bp.route("/", methods=["POST"])
@_token_required
def create_referral():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@prevent_duty_bp.route("/<int:referral_id>", methods=["PUT"])
@_token_required
def update_referral(referral_id: int):
    data = _data()
    if data.get(referral_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update(referral_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@prevent_duty_bp.route("/<int:referral_id>", methods=["DELETE"])
@_token_required
def delete_referral(referral_id: int):
    data = _data()
    if not data.delete(referral_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "referral_id": referral_id})
