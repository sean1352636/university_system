"""REST API for Primary Absence Requests."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

absence_requests_bp = Blueprint("pri_absence_requests", __name__, url_prefix="/api/absence-requests")


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
    from education_system.systems.primary.domain.pastoral.absence_requests import (
        absence_requests as data,
    )
    return data


@absence_requests_bp.route("", methods=["GET"])
@absence_requests_bp.route("/", methods=["GET"])
@_token_required
def list_absence_requests():
    data = _data()
    args = request.args
    kwargs = {}
    for key in ("pupil_id", "status", "category", "authorisation",
                "year_group", "from_date", "to_date"):
        val = args.get(key)
        if val:
            kwargs[key] = val
    if args.get("pending_only", "").lower() in ("1", "true", "yes"):
        kwargs["pending_only"] = True
    try:
        rows = data.list_requests(**kwargs)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@absence_requests_bp.route("/summary", methods=["GET"])
@_token_required
def summary_absence_requests():
    data = _data()
    args = request.args
    try:
        result = data.cohort_summary(
            from_date=args.get("from_date") or None,
            to_date=args.get("to_date") or None,
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)


@absence_requests_bp.route("/<int:request_id>", methods=["GET"])
@_token_required
def get_absence_request(request_id):
    data = _data()
    rec = data.get(request_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@absence_requests_bp.route("", methods=["POST"])
@absence_requests_bp.route("/", methods=["POST"])
@_token_required
def create_absence_request():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@absence_requests_bp.route("/<int:request_id>", methods=["PUT"])
@_token_required
def update_absence_request(request_id):
    data = _data()
    if data.get(request_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update(request_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@absence_requests_bp.route("/<int:request_id>", methods=["DELETE"])
@_token_required
def delete_absence_request(request_id):
    data = _data()
    if not data.delete(request_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "request_id": request_id})
