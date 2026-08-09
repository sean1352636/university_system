"""REST API for Primary Teaching Assistants."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

teaching_assistants_bp = Blueprint(
    "pri_teaching_assistants", __name__, url_prefix="/api/teaching-assistants"
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
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj


def _data():
    from education_system.systems.primary.domain.staff.teaching_assistants import (
        teaching_assistants as data,
    )
    return data


def _as_bool(val):
    if isinstance(val, str):
        return val.strip().lower() in ("1", "true", "yes", "on")
    return bool(val)


@teaching_assistants_bp.route("", methods=["GET"])
@teaching_assistants_bp.route("/", methods=["GET"])
@_token_required
def list_teaching_assistants():
    data = _data()
    args = request.args
    kwargs = {}
    if "role" in args:
        kwargs["role"] = args.get("role")
    if "active_only" in args:
        kwargs["active_only"] = _as_bool(args.get("active_only"))
    if "search" in args:
        kwargs["search"] = args.get("search")
    if "needs_dbs" in args:
        kwargs["needs_dbs"] = _as_bool(args.get("needs_dbs"))
    if "needs_safeguarding" in args:
        kwargs["needs_safeguarding"] = _as_bool(args.get("needs_safeguarding"))
    try:
        rows = data.list_all(**kwargs)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@teaching_assistants_bp.route("/summary", methods=["GET"])
@_token_required
def teaching_assistants_summary():
    data = _data()
    return jsonify(data.summary())


@teaching_assistants_bp.route("/<int:ta_id>", methods=["GET"])
@_token_required
def get_teaching_assistant(ta_id):
    data = _data()
    rec = data.get(ta_id)
    if rec is None:
        return jsonify({"error": f"No TA #{ta_id}"}), 404
    return jsonify(_dump(rec))


@teaching_assistants_bp.route("", methods=["POST"])
@teaching_assistants_bp.route("/", methods=["POST"])
@_token_required
def create_teaching_assistant():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec)), 201


@teaching_assistants_bp.route("/<int:ta_id>", methods=["PUT"])
@_token_required
def update_teaching_assistant(ta_id):
    data = _data()
    if data.get(ta_id) is None:
        return jsonify({"error": f"No TA #{ta_id}"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update(ta_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec))


@teaching_assistants_bp.route("/<int:ta_id>/toggle-active", methods=["POST"])
@_token_required
def toggle_active_teaching_assistant(ta_id):
    data = _data()
    try:
        rec = data.toggle_active(ta_id)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify(_dump(rec))


@teaching_assistants_bp.route("/<int:ta_id>", methods=["DELETE"])
@_token_required
def delete_teaching_assistant(ta_id):
    data = _data()
    if not data.delete(ta_id):
        return jsonify({"error": f"No TA #{ta_id}"}), 404
    return jsonify({"deleted": True, "ta_id": ta_id})
