"""REST API for Nursery Prevent Duty.

Exposes CRUD over Prevent Duty safeguarding records plus a summary endpoint.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

prevent_duty_bp = Blueprint("nsy_prevent_duty", __name__, url_prefix="/api/prevent-duty")


def _token_required(view):
    try:
        from education_system.shared.api.auth import token_required
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


@prevent_duty_bp.route("", methods=["GET"])
@prevent_duty_bp.route("/", methods=["GET"])
@_token_required
def list_records():
    from education_system.nursery_system.modules.domain.prevent_duty.prevent_duty import (
        list_records as _list,
    )
    status = request.args.get("status") or None
    rows = _list(status=status)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@prevent_duty_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    from education_system.nursery_system.modules.domain.prevent_duty.prevent_duty import (
        summary as _summary,
    )
    return jsonify(_summary())


@prevent_duty_bp.route("/<record_id>", methods=["GET"])
@_token_required
def get_record(record_id):
    from education_system.nursery_system.modules.domain.prevent_duty.prevent_duty import (
        get_record as _get,
    )
    rec = _get(record_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@prevent_duty_bp.route("", methods=["POST"])
@prevent_duty_bp.route("/", methods=["POST"])
@_token_required
def create_record():
    from education_system.nursery_system.modules.domain.prevent_duty.prevent_duty import (
        ValidationError,
        create_record as _create,
    )
    try:
        rec = _create(request.get_json(silent=True) or {})
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec)), 201


@prevent_duty_bp.route("/<record_id>", methods=["PUT"])
@_token_required
def update_record(record_id):
    from education_system.nursery_system.modules.domain.prevent_duty.prevent_duty import (
        ValidationError,
        get_record as _get,
        update_record as _update,
    )
    if _get(record_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        rec = _update(record_id, request.get_json(silent=True) or {})
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec))


@prevent_duty_bp.route("/<record_id>", methods=["DELETE"])
@_token_required
def delete_record(record_id):
    from education_system.nursery_system.modules.domain.prevent_duty.prevent_duty import (
        delete_record as _delete,
    )
    if not _delete(record_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "record_id": record_id})
