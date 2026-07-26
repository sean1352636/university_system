"""REST API for Primary Funding (streams & learner allocations)."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

funding_bp = Blueprint("pri_funding", __name__, url_prefix="/api/funding")


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


# ── Streams ───────────────────────────────────────────────

@funding_bp.route("", methods=["GET"])
@funding_bp.route("/", methods=["GET"])
@_token_required
def list_streams():
    from education_system.systems.primary.domain.finance.funding import funding as data
    rows = data.list_streams()
    return jsonify({"items": _dump(rows), "count": len(rows)})


@funding_bp.route("/<int:stream_id>", methods=["GET"])
@_token_required
def get_stream(stream_id: int):
    from education_system.systems.primary.domain.finance.funding import funding as data
    obj = data.get_stream(stream_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj))


@funding_bp.route("", methods=["POST"])
@funding_bp.route("/", methods=["POST"])
@_token_required
def create_stream():
    from education_system.systems.primary.domain.finance.funding import funding as data
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.create_stream(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj)), 201


@funding_bp.route("/<int:stream_id>", methods=["PUT"])
@_token_required
def update_stream(stream_id: int):
    from education_system.systems.primary.domain.finance.funding import funding as data
    if data.get_stream(stream_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.update_stream(stream_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@funding_bp.route("/<int:stream_id>", methods=["DELETE"])
@_token_required
def delete_stream(stream_id: int):
    from education_system.systems.primary.domain.finance.funding import funding as data
    if not data.delete_stream(stream_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


# ── Allocations ───────────────────────────────────────────

@funding_bp.route("/allocations", methods=["GET"])
@_token_required
def list_allocations():
    from education_system.systems.primary.domain.finance.funding import funding as data
    rows = data.list_allocations()
    return jsonify({"items": _dump(rows), "count": len(rows)})


@funding_bp.route("/allocations/<int:allocation_id>", methods=["GET"])
@_token_required
def get_allocation(allocation_id: int):
    from education_system.systems.primary.domain.finance.funding import funding as data
    obj = data.get_allocation(allocation_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj))


@funding_bp.route("/allocations", methods=["POST"])
@_token_required
def create_allocation():
    from education_system.systems.primary.domain.finance.funding import funding as data
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.create_allocation(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj)), 201


@funding_bp.route("/allocations/<int:allocation_id>", methods=["PUT"])
@_token_required
def update_allocation(allocation_id: int):
    from education_system.systems.primary.domain.finance.funding import funding as data
    if data.get_allocation(allocation_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.update_allocation(allocation_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@funding_bp.route("/allocations/<int:allocation_id>", methods=["DELETE"])
@_token_required
def delete_allocation(allocation_id: int):
    from education_system.systems.primary.domain.finance.funding import funding as data
    if not data.delete_allocation(allocation_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


# ── Summary ───────────────────────────────────────────────

@funding_bp.route("/summary", methods=["GET"])
@_token_required
def get_summary():
    from education_system.systems.primary.domain.finance.funding import funding as data
    return jsonify(_dump(data.summary()))
