"""REST API for Nursery Newsletters.

Exposes CRUD plus a publish action over setting-wide parent newsletters.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

newsletters_bp = Blueprint("nsy_newsletters", __name__, url_prefix="/api/newsletters")


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


@newsletters_bp.route("", methods=["GET"])
@newsletters_bp.route("/", methods=["GET"])
@_token_required
def list_newsletters():
    from education_system.systems.nursery.domain.operations.communications.newsletters import newsletters as data

    rows = data.list_newsletters()
    return jsonify({"items": _dump(rows), "count": len(rows)})


@newsletters_bp.route("/<newsletter_id>", methods=["GET"])
@_token_required
def get_newsletter(newsletter_id):
    from education_system.systems.nursery.domain.operations.communications.newsletters import newsletters as data

    row = data.get_newsletter(newsletter_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@newsletters_bp.route("", methods=["POST"])
@newsletters_bp.route("/", methods=["POST"])
@_token_required
def create_newsletter():
    from education_system.systems.nursery.domain.operations.communications.newsletters import newsletters as data

    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_newsletter(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row)), 201


@newsletters_bp.route("/<newsletter_id>", methods=["PUT"])
@_token_required
def update_newsletter(newsletter_id):
    from education_system.systems.nursery.domain.operations.communications.newsletters import newsletters as data

    if data.get_newsletter(newsletter_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_newsletter(newsletter_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row))


@newsletters_bp.route("/<newsletter_id>", methods=["DELETE"])
@_token_required
def delete_newsletter(newsletter_id):
    from education_system.systems.nursery.domain.operations.communications.newsletters import newsletters as data

    if not data.delete_newsletter(newsletter_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "newsletter_id": newsletter_id})


@newsletters_bp.route("/<newsletter_id>/publish", methods=["POST"])
@_token_required
def publish_newsletter(newsletter_id):
    from education_system.systems.nursery.domain.operations.communications.newsletters import newsletters as data

    payload = request.get_json(silent=True) or {}
    try:
        row = data.publish_newsletter(newsletter_id, payload.get("published_date"))
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row))
