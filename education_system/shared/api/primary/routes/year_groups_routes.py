"""REST API for Primary Year Groups."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

year_groups_bp = Blueprint("pri_year_groups", __name__, url_prefix="/api/year-groups")


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


@year_groups_bp.route("", methods=["GET"])
@year_groups_bp.route("/", methods=["GET"])
@_token_required
def list_year_groups():
    from education_system.primarysch_system.modules.domain.year_groups import (
        year_groups as data,
    )
    rows = data.list_all()
    return jsonify({"items": _dump(rows), "count": len(rows)})


@year_groups_bp.route("/summary", methods=["GET"])
@_token_required
def year_group_counts():
    from education_system.primarysch_system.modules.domain.year_groups import (
        year_groups as data,
    )
    return jsonify(data.pupil_counts())


@year_groups_bp.route("/<year_group>", methods=["GET"])
@_token_required
def get_year_group(year_group):
    from education_system.primarysch_system.modules.domain.year_groups import (
        year_groups as data,
    )
    rec = data.get(year_group)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@year_groups_bp.route("", methods=["POST"])
@year_groups_bp.route("/", methods=["POST"])
@_token_required
def create_year_group():
    from education_system.primarysch_system.modules.domain.year_groups import (
        year_groups as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.upsert(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@year_groups_bp.route("/<year_group>", methods=["PUT"])
@_token_required
def update_year_group(year_group):
    from education_system.primarysch_system.modules.domain.year_groups import (
        year_groups as data,
    )
    payload = request.get_json(silent=True) or {}
    payload["year_group"] = year_group
    try:
        rec = data.upsert(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@year_groups_bp.route("/<year_group>", methods=["DELETE"])
@_token_required
def delete_year_group(year_group):
    from education_system.primarysch_system.modules.domain.year_groups import (
        year_groups as data,
    )
    if not data.delete(year_group):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "year_group": year_group})
