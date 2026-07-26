"""REST API for Primary Receipts."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

receipts_bp = Blueprint("pri_receipts", __name__, url_prefix="/api/receipts")


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
    from education_system.systems.primary.domain.finance.receipts import receipts as data
    return data


def _bool(v) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on")


@receipts_bp.route("", methods=["GET"])
@receipts_bp.route("/", methods=["GET"])
@_token_required
def list_receipts():
    data = _data()
    try:
        rows = data.list_receipts(
            student_id=request.args.get("student_id"),
            status=request.args.get("status"),
            method=request.args.get("method"),
            date_from=request.args.get("date_from"),
            date_to=request.args.get("date_to"),
            issued_only=_bool(request.args.get("issued_only")),
            voided_only=_bool(request.args.get("voided_only")),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@receipts_bp.route("/search", methods=["GET"])
@_token_required
def search_receipts():
    data = _data()
    rows = data.search_receipts(request.args.get("q", ""))
    return jsonify({"items": _dump(rows), "count": len(rows)})


@receipts_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    data = _data()
    return jsonify(_dump(data.summary()))


@receipts_bp.route("/<int:receipt_id>", methods=["GET"])
@_token_required
def get_receipt(receipt_id: int):
    data = _data()
    row = data.get_receipt(receipt_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@receipts_bp.route("/<int:receipt_id>/view", methods=["GET"])
@_token_required
def view_receipt(receipt_id: int):
    data = _data()
    row = data.view_receipt(receipt_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@receipts_bp.route("/<int:receipt_id>/lines", methods=["GET"])
@_token_required
def list_lines(receipt_id: int):
    data = _data()
    if data.get_receipt(receipt_id) is None:
        return jsonify({"error": "Not found"}), 404
    rows = data.list_lines(receipt_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@receipts_bp.route("", methods=["POST"])
@receipts_bp.route("/", methods=["POST"])
@_token_required
def create_receipt():
    data = _data()
    payload = request.get_json(silent=True) or {}
    header = payload.get("header", payload)
    lines = payload.get("lines", [])
    try:
        row = data.create_receipt(header, lines)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@receipts_bp.route("/<int:receipt_id>", methods=["PUT"])
@_token_required
def update_receipt(receipt_id: int):
    data = _data()
    if data.get_receipt(receipt_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    header = payload.get("header", payload)
    lines = payload.get("lines", None)
    try:
        row = data.update_receipt(receipt_id, header, lines)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@receipts_bp.route("/<int:receipt_id>/issue", methods=["POST"])
@_token_required
def issue(receipt_id: int):
    data = _data()
    if data.get_receipt(receipt_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        row = data.issue(receipt_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@receipts_bp.route("/<int:receipt_id>/void", methods=["POST"])
@_token_required
def void_receipt(receipt_id: int):
    data = _data()
    if data.get_receipt(receipt_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.void_receipt(receipt_id, payload.get("reason", ""))
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@receipts_bp.route("/<int:receipt_id>", methods=["DELETE"])
@_token_required
def delete_receipt(receipt_id: int):
    data = _data()
    try:
        ok = data.delete_receipt(receipt_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    if not ok:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})
