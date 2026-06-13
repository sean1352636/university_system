"""REST API for Primary To-Do."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

todo_bp = Blueprint("pri_todo", __name__, url_prefix="/api/todo")


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
    from education_system.primarysch_system.modules.domain.todo import todo as data
    return data


@todo_bp.route("", methods=["GET"])
@todo_bp.route("/", methods=["GET"])
@_token_required
def list_todos():
    data = _data()
    args = request.args
    kwargs = {}
    for key in ("status", "owner", "assignee", "priority", "category",
                "due_on", "due_by"):
        val = args.get(key)
        if val:
            kwargs[key] = val
    if args.get("open_only", "").lower() in ("1", "true", "yes"):
        kwargs["open_only"] = True
    if args.get("overdue_only", "").lower() in ("1", "true", "yes"):
        kwargs["overdue_only"] = True
    try:
        rows = data.list_todos(**kwargs)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@todo_bp.route("/search", methods=["GET"])
@_token_required
def search_todos():
    data = _data()
    q = request.args.get("q", "")
    rows = data.search_todos(q)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@todo_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    data = _data()
    owner = request.args.get("owner") or None
    return jsonify(_dump(data.summary(owner=owner)))


@todo_bp.route("/<int:todo_id>", methods=["GET"])
@_token_required
def get_todo(todo_id: int):
    data = _data()
    row = data.get_todo(todo_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@todo_bp.route("", methods=["POST"])
@todo_bp.route("/", methods=["POST"])
@_token_required
def create_todo():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_todo(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@todo_bp.route("/<int:todo_id>", methods=["PUT"])
@_token_required
def update_todo(todo_id: int):
    data = _data()
    if data.get_todo(todo_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_todo(todo_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@todo_bp.route("/<int:todo_id>", methods=["DELETE"])
@_token_required
def delete_todo(todo_id: int):
    data = _data()
    if not data.delete_todo(todo_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "todo_id": todo_id})
