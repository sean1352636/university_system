"""REST API for Primary Transport."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

transport_bp = Blueprint("pri_transport", __name__, url_prefix="/api/transport")


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


# ── Routes ──────────────────────────────────────────────────────────

@transport_bp.route("/routes", methods=["GET"])
@transport_bp.route("/routes/", methods=["GET"])
@_token_required
def list_routes():
    from education_system.primarysch_system.modules.domain.transport import (
        transport as data,
    )
    rows = data.list_routes()
    return jsonify({"items": _dump(rows), "count": len(rows)})


@transport_bp.route("/routes/<int:route_id>", methods=["GET"])
@_token_required
def get_route(route_id: int):
    from education_system.primarysch_system.modules.domain.transport import (
        transport as data,
    )
    obj = data.get_route(route_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj))


@transport_bp.route("/routes", methods=["POST"])
@transport_bp.route("/routes/", methods=["POST"])
@_token_required
def create_route():
    from education_system.primarysch_system.modules.domain.transport import (
        transport as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.create_route(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj)), 201


@transport_bp.route("/routes/<int:route_id>", methods=["PUT"])
@_token_required
def update_route(route_id: int):
    from education_system.primarysch_system.modules.domain.transport import (
        transport as data,
    )
    if data.get_route(route_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.update_route(route_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@transport_bp.route("/routes/<int:route_id>", methods=["DELETE"])
@_token_required
def delete_route(route_id: int):
    from education_system.primarysch_system.modules.domain.transport import (
        transport as data,
    )
    if not data.delete_route(route_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "route_id": route_id})


# ── Arrangements ────────────────────────────────────────────────────

@transport_bp.route("", methods=["GET"])
@transport_bp.route("/", methods=["GET"])
@_token_required
def list_arrangements():
    from education_system.primarysch_system.modules.domain.transport import (
        transport as data,
    )
    rows = data.list_arrangements()
    return jsonify({"items": _dump(rows), "count": len(rows)})


@transport_bp.route("/<int:arrangement_id>", methods=["GET"])
@_token_required
def get_arrangement(arrangement_id: int):
    from education_system.primarysch_system.modules.domain.transport import (
        transport as data,
    )
    obj = data.get_arrangement(arrangement_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj))


@transport_bp.route("", methods=["POST"])
@transport_bp.route("/", methods=["POST"])
@_token_required
def create_arrangement():
    from education_system.primarysch_system.modules.domain.transport import (
        transport as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.create_arrangement(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj)), 201


@transport_bp.route("/<int:arrangement_id>", methods=["PUT"])
@_token_required
def update_arrangement(arrangement_id: int):
    from education_system.primarysch_system.modules.domain.transport import (
        transport as data,
    )
    if data.get_arrangement(arrangement_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.update_arrangement(arrangement_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@transport_bp.route("/<int:arrangement_id>", methods=["DELETE"])
@_token_required
def delete_arrangement(arrangement_id: int):
    from education_system.primarysch_system.modules.domain.transport import (
        transport as data,
    )
    if not data.delete_arrangement(arrangement_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "arrangement_id": arrangement_id})


# ── Summary ─────────────────────────────────────────────────────────

@transport_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    from education_system.primarysch_system.modules.domain.transport import (
        transport as data,
    )
    return jsonify(_dump(data.summary()))
