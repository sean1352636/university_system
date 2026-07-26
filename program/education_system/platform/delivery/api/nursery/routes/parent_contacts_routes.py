"""REST API for Nursery Parent Contacts.

Exposes CRUD over the parents / carers attached to each child.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

parent_contacts_bp = Blueprint("nsy_parent_contacts", __name__, url_prefix="/api/parent-contacts")


def _token_required(view):
    try:
        from education_system.platform.delivery.api.auth import token_required
        return token_required(view)
    except Exception:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            expected = os.environ.get("NURSERY_API_TOKEN")
            got = request.headers.get("X-Nursery-Token")
            if expected and got and got == expected:
                g.current_user = {"sub": "service", "role": "service"}
                return view(*args, **kwargs)
            return jsonify({"error": "Unauthorized"}), 401
        return wrapper


def _dump(obj):
    """Serialize a domain dataclass (or list of them) to JSON-safe data."""
    if isinstance(obj, list):
        return [_dump(o) for o in obj]
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj


@parent_contacts_bp.route("", methods=["GET"])
@parent_contacts_bp.route("/", methods=["GET"])
@_token_required
def list_contacts():
    from education_system.systems.nursery.domain.operations.communications.parent_contacts import (
        parent_contacts as data,
    )
    pupil_id = request.args.get("pupil_id")
    rows = data.list_contacts(pupil_id=pupil_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@parent_contacts_bp.route("/<contact_id>", methods=["GET"])
@_token_required
def get_contact(contact_id):
    from education_system.systems.nursery.domain.operations.communications.parent_contacts import (
        parent_contacts as data,
    )
    row = data.get_contact(contact_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@parent_contacts_bp.route("", methods=["POST"])
@parent_contacts_bp.route("/", methods=["POST"])
@_token_required
def create_contact():
    from education_system.systems.nursery.domain.operations.communications.parent_contacts import (
        parent_contacts as data,
    )
    try:
        row = data.create_contact(request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row)), 201


@parent_contacts_bp.route("/<contact_id>", methods=["PUT"])
@_token_required
def update_contact(contact_id):
    from education_system.systems.nursery.domain.operations.communications.parent_contacts import (
        parent_contacts as data,
    )
    try:
        row = data.update_contact(contact_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        msg = str(e)
        if "No parent contact with id" in msg:
            return jsonify({"error": msg}), 404
        return jsonify({"error": msg}), 400
    return jsonify(_dump(row))


@parent_contacts_bp.route("/<contact_id>", methods=["DELETE"])
@_token_required
def delete_contact(contact_id):
    from education_system.systems.nursery.domain.operations.communications.parent_contacts import (
        parent_contacts as data,
    )
    if not data.delete_contact(contact_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "contact_id": contact_id})
