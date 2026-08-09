"""REST API for Primary Assets (fixed-asset register + maintenance log)."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

assets_bp = Blueprint("pri_assets", __name__, url_prefix="/api/assets")


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
        return {f.name: _dump(getattr(obj, f.name))
                for f in dataclasses.fields(obj)}
    if isinstance(obj, tuple):
        return [_dump(o) for o in obj]
    if isinstance(obj, dict):
        return {k: _dump(v) for k, v in obj.items()}
    return obj


def _data():
    from education_system.systems.primary.domain.operations.assets import (
        assets as data,
    )
    return data


def _payload() -> dict:
    return request.get_json(silent=True) or {}


# ── Assets ────────────────────────────────────────────────────────

@assets_bp.route("", methods=["GET"])
@assets_bp.route("/", methods=["GET"])
@_token_required
def list_assets():
    data = _data()
    args = request.args
    try:
        rows = data.list_assets(
            category=args.get("category"),
            status=args.get("status"),
            location=args.get("location"),
            custodian_id=args.get("custodian_id"),
            condition=args.get("condition"),
            search=args.get("search"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@assets_bp.route("/views", methods=["GET"])
@_token_required
def list_views():
    data = _data()
    args = request.args
    try:
        rows = data.list_views(
            category=args.get("category"),
            status=args.get("status"),
            location=args.get("location"),
            custodian_id=args.get("custodian_id"),
            condition=args.get("condition"),
            search=args.get("search"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@assets_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    data = _data()
    return jsonify(_dump(data.summary()))


@assets_bp.route("/<int:asset_id>", methods=["GET"])
@_token_required
def get_asset(asset_id: int):
    data = _data()
    obj = data.get_asset(asset_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj))


@assets_bp.route("/<int:asset_id>/view", methods=["GET"])
@_token_required
def view_asset(asset_id: int):
    data = _data()
    obj = data.view_asset(asset_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj))


@assets_bp.route("", methods=["POST"])
@assets_bp.route("/", methods=["POST"])
@_token_required
def create_asset():
    data = _data()
    try:
        obj = data.create_asset(_payload())
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj)), 201


@assets_bp.route("/<int:asset_id>", methods=["PUT"])
@_token_required
def update_asset(asset_id: int):
    data = _data()
    if data.get_asset(asset_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        obj = data.update_asset(asset_id, _payload())
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@assets_bp.route("/<int:asset_id>/status", methods=["PUT"])
@_token_required
def set_status(asset_id: int):
    data = _data()
    if data.get_asset(asset_id) is None:
        return jsonify({"error": "Not found"}), 404
    status = _payload().get("status")
    try:
        obj = data.set_status(asset_id, status)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@assets_bp.route("/<int:asset_id>", methods=["DELETE"])
@_token_required
def delete_asset(asset_id: int):
    data = _data()
    if not data.delete_asset(asset_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


# ── Maintenance ───────────────────────────────────────────────────

@assets_bp.route("/maintenance", methods=["GET"])
@_token_required
def list_maintenance():
    data = _data()
    args = request.args
    asset_id = args.get("asset_id", type=int)
    try:
        rows = data.list_maintenance(
            asset_id=asset_id,
            service_type=args.get("service_type"),
            outcome=args.get("outcome"),
            date_from=args.get("date_from"),
            date_to=args.get("date_to"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@assets_bp.route("/maintenance/<int:maintenance_id>", methods=["GET"])
@_token_required
def get_maintenance(maintenance_id: int):
    data = _data()
    obj = data.get_maintenance(maintenance_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj))


@assets_bp.route("/<int:asset_id>/maintenance", methods=["POST"])
@_token_required
def add_maintenance(asset_id: int):
    data = _data()
    try:
        obj = data.add_maintenance(asset_id, _payload())
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj)), 201


@assets_bp.route("/maintenance/<int:maintenance_id>", methods=["PUT"])
@_token_required
def update_maintenance(maintenance_id: int):
    data = _data()
    if data.get_maintenance(maintenance_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        obj = data.update_maintenance(maintenance_id, _payload())
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@assets_bp.route("/maintenance/<int:maintenance_id>", methods=["DELETE"])
@_token_required
def delete_maintenance(maintenance_id: int):
    data = _data()
    if not data.delete_maintenance(maintenance_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})
