"""REST API for Primary Visitors."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

visitors_bp = Blueprint("pri_visitors", __name__, url_prefix="/api/visitors")


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
    from education_system.primarysch_system.modules.domain.visitors import (
        visitors as data,
    )
    return data


@visitors_bp.route("", methods=["GET"])
@visitors_bp.route("/", methods=["GET"])
@_token_required
def list_visitors():
    data = _data()
    args = request.args
    kwargs: dict = {}
    for key in ("visitor_type", "status", "host_staff_id",
                "name_like", "org_like", "date_from", "date_to"):
        val = args.get(key)
        if val:
            kwargs[key] = val
    for flag in ("on_site_only", "overdue_only", "today_only",
                 "no_show_only", "safeguarding_only"):
        if args.get(flag, "").lower() in ("1", "true", "yes"):
            kwargs[flag] = True
    rows = data.list_visitors(**kwargs)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@visitors_bp.route("/summary", methods=["GET"])
@_token_required
def visitors_summary():
    data = _data()
    return jsonify(_dump(data.summary()))


@visitors_bp.route("/<int:visitor_id>", methods=["GET"])
@_token_required
def get_visitor(visitor_id: int):
    data = _data()
    obj = data.get_visitor(visitor_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj))


@visitors_bp.route("", methods=["POST"])
@visitors_bp.route("/", methods=["POST"])
@_token_required
def create_visitor():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.create_visitor(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj)), 201


@visitors_bp.route("/<int:visitor_id>", methods=["PUT"])
@_token_required
def update_visitor(visitor_id: int):
    data = _data()
    if data.get_visitor(visitor_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.update_visitor(visitor_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@visitors_bp.route("/<int:visitor_id>", methods=["DELETE"])
@_token_required
def delete_visitor(visitor_id: int):
    data = _data()
    if not data.delete_visitor(visitor_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "visitor_id": visitor_id})
