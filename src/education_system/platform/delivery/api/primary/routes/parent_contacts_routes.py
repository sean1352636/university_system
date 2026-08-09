"""REST API for Primary Parent / Guardian Contacts."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

parent_contacts_bp = Blueprint("pri_parent_contacts", __name__, url_prefix="/api/parent-contacts")


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
    from education_system.systems.primary.domain.operations.communications.parent_contacts import (
        parent_contacts as data,
    )
    return data


def _truthy(v) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on")


@parent_contacts_bp.route("", methods=["GET"])
@parent_contacts_bp.route("/", methods=["GET"])
@_token_required
def list_contacts():
    data = _data()
    args = request.args
    try:
        rows = data.list_contacts(
            student_id=args.get("student_id"),
            relationship=args.get("relationship"),
            primary_only=_truthy(args.get("primary_only", "")),
            emergency_only=_truthy(args.get("emergency_only", "")),
            receives_only=_truthy(args.get("receives_only", "")),
        )
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@parent_contacts_bp.route("/search", methods=["GET"])
@_token_required
def search_contacts():
    data = _data()
    rows = data.search_contacts(request.args.get("q", ""))
    return jsonify({"items": _dump(rows), "count": len(rows)})


@parent_contacts_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    data = _data()
    return jsonify(_dump(data.summary()))


@parent_contacts_bp.route("/<int:contact_id>", methods=["GET"])
@_token_required
def get_contact(contact_id: int):
    data = _data()
    obj = data.get_contact(contact_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj))


@parent_contacts_bp.route("", methods=["POST"])
@parent_contacts_bp.route("/", methods=["POST"])
@_token_required
def create_contact():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.create_contact(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(obj)), 201


@parent_contacts_bp.route("/<int:contact_id>", methods=["PUT"])
@_token_required
def update_contact(contact_id: int):
    data = _data()
    if data.get_contact(contact_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.update_contact(contact_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(obj))


@parent_contacts_bp.route("/<int:contact_id>/primary", methods=["POST"])
@_token_required
def set_primary(contact_id: int):
    data = _data()
    if data.get_contact(contact_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        obj = data.set_primary(contact_id)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(obj))


@parent_contacts_bp.route("/<int:contact_id>", methods=["DELETE"])
@_token_required
def delete_contact(contact_id: int):
    data = _data()
    if not data.delete_contact(contact_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})
