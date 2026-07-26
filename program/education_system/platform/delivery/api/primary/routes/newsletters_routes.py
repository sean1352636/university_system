"""REST API for Primary Newsletters."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

newsletters_bp = Blueprint("pri_newsletters", __name__, url_prefix="/api/newsletters")


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
    from education_system.systems.primary.domain.operations.communications.newsletters import (
        newsletters as data,
    )
    return data


@newsletters_bp.route("", methods=["GET"])
@newsletters_bp.route("/", methods=["GET"])
@_token_required
def list_newsletters():
    data = _data()
    try:
        rows = data.list_newsletters(
            academic_year=request.args.get("academic_year"),
            status=request.args.get("status"),
            audience=request.args.get("audience"),
            target_year_group=request.args.get("target_year_group"),
            search=request.args.get("search"),
        )
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@newsletters_bp.route("/summary", methods=["GET"])
@_token_required
def newsletter_summary():
    data = _data()
    return jsonify(_dump(data.summary()))


@newsletters_bp.route("/<int:newsletter_id>", methods=["GET"])
@_token_required
def get_newsletter(newsletter_id: int):
    data = _data()
    rec = data.get(newsletter_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@newsletters_bp.route("", methods=["POST"])
@newsletters_bp.route("/", methods=["POST"])
@_token_required
def create_newsletter():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec)), 201


@newsletters_bp.route("/<int:newsletter_id>", methods=["PUT"])
@_token_required
def update_newsletter(newsletter_id: int):
    data = _data()
    if data.get(newsletter_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update(newsletter_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec))


@newsletters_bp.route("/<int:newsletter_id>", methods=["DELETE"])
@_token_required
def delete_newsletter(newsletter_id: int):
    data = _data()
    if not data.delete(newsletter_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "newsletter_id": newsletter_id})


@newsletters_bp.route("/<int:newsletter_id>/publish", methods=["POST"])
@_token_required
def publish_newsletter(newsletter_id: int):
    data = _data()
    if data.get(newsletter_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.publish(newsletter_id, published_on=payload.get("published_on"))
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec))


@newsletters_bp.route("/<int:newsletter_id>/revert", methods=["POST"])
@_token_required
def revert_newsletter(newsletter_id: int):
    data = _data()
    if data.get(newsletter_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        rec = data.revert_to_draft(newsletter_id)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec))


@newsletters_bp.route("/<int:newsletter_id>/archive", methods=["POST"])
@_token_required
def archive_newsletter(newsletter_id: int):
    data = _data()
    if data.get(newsletter_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        rec = data.archive(newsletter_id)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec))
