"""REST API for Primary Census / ILR."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

census_bp = Blueprint("pri_census", __name__, url_prefix="/api/census")


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


# ── Returns ───────────────────────────────────────────────

@census_bp.route("", methods=["GET"])
@census_bp.route("/", methods=["GET"])
@census_bp.route("/returns", methods=["GET"])
@_token_required
def list_returns():
    from education_system.systems.primary.domain.governance.compliance.census import census as data
    rows = data.list_returns()
    return jsonify({"items": _dump(rows), "count": len(rows)})


@census_bp.route("/returns/<int:return_id>", methods=["GET"])
@_token_required
def get_return(return_id):
    from education_system.systems.primary.domain.governance.compliance.census import census as data
    obj = data.get_return(return_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj))


@census_bp.route("", methods=["POST"])
@census_bp.route("/", methods=["POST"])
@census_bp.route("/returns", methods=["POST"])
@_token_required
def create_return():
    from education_system.systems.primary.domain.governance.compliance.census import census as data
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.create_return(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj)), 201


@census_bp.route("/returns/<int:return_id>", methods=["PUT"])
@_token_required
def update_return(return_id):
    from education_system.systems.primary.domain.governance.compliance.census import census as data
    if data.get_return(return_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.update_return(return_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@census_bp.route("/returns/<int:return_id>", methods=["DELETE"])
@_token_required
def delete_return(return_id):
    from education_system.systems.primary.domain.governance.compliance.census import census as data
    if not data.delete_return(return_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": return_id})


# ── Learner aims ──────────────────────────────────────────

@census_bp.route("/aims", methods=["GET"])
@_token_required
def list_aims():
    from education_system.systems.primary.domain.governance.compliance.census import census as data
    rows = data.list_aims()
    return jsonify({"items": _dump(rows), "count": len(rows)})


@census_bp.route("/aims/<int:aim_id>", methods=["GET"])
@_token_required
def get_aim(aim_id):
    from education_system.systems.primary.domain.governance.compliance.census import census as data
    obj = data.get_aim(aim_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj))


@census_bp.route("/aims", methods=["POST"])
@_token_required
def create_aim():
    from education_system.systems.primary.domain.governance.compliance.census import census as data
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.create_aim(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj)), 201


@census_bp.route("/aims/<int:aim_id>", methods=["PUT"])
@_token_required
def update_aim(aim_id):
    from education_system.systems.primary.domain.governance.compliance.census import census as data
    if data.get_aim(aim_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.update_aim(aim_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@census_bp.route("/aims/<int:aim_id>", methods=["DELETE"])
@_token_required
def delete_aim(aim_id):
    from education_system.systems.primary.domain.governance.compliance.census import census as data
    if not data.delete_aim(aim_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": aim_id})


# ── Summary ───────────────────────────────────────────────

@census_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    from education_system.systems.primary.domain.governance.compliance.census import census as data
    return jsonify(_dump(data.summary()))
